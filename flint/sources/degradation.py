"""单源降级机制（M1-015，技术方案 E6 行 1）。

- 语义：单热点源不可用**不阻断**当日采集——跳过该源、其余源照常；
  每次跳过写入 DegradationNote（落库通道经 DegradationStore 协议，
  SQL 实现待 M1-003 迁移解锁后接入，见 Q-001），并向卡片层提供
  缺口标注位文案「今日缺 {源} 数据」。
- 失败分类：429 → rate_limited；解析漂移 → parse_drift；其余抓取错误 →
  fetch_failed；配置停用 → disabled（同样留痕，数据缺口对用户可见）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Protocol

import asyncpg

from flint.domain.models import TrendItem
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError
from flint.sources.registry import SourceRegistry

DegradationReason = Literal[
    "rate_limited", "fetch_failed", "parse_drift", "disabled",
    # —— v0.4 只加不删（E6 降级矩阵注册点，DEC-003 允许的既有文件增量）——
    "no_region_sources",   # 该地区无可用源（K1 未决或全部停用）：当日该区无数据，其余区照常
    "fetch_denied_by_legal_status",  # 合规门拒绝抓取（restricted / unknown，REGION-07）
    # CN-07：**往返成了，而上游那天一条都没给**。
    #
    # 与 `fetch_failed` NEVER 合并：那一档说的是「没问到」，这一档说的是
    # 「问到了，答案是空的」——前者去查网络与端点，后者去看窗口与上游。
    # 与「不记」更 NEVER 合并：`CN-06` 那次 ghtrend 与 arxiv 结构上恒回 0 条，
    # 而回执照旧写 `ok`、`degradation_notes` 当日 0 行——
    # **盘上完全看不出这两源是空的**，广场少了两源也没有人会知道。
    "empty_result",
]


@dataclass(frozen=True)
class DegradationNote:
    day: date
    source_id: str
    reason: DegradationReason
    detail: str


class DegradationStore(Protocol):
    """DegradationNote 落库通道；单测用内存实现，SQL 实现随迁移层接入。"""

    def add(self, note: DegradationNote) -> None: ...

    def for_day(self, day: date) -> list[DegradationNote]: ...


async def persist_note_on(conn: asyncpg.Connection, note: DegradationNote) -> None:
    """落库通道（migration-0005；(day, source_id) 幂等 upsert）。"""
    await conn.execute(
        "INSERT INTO degradation_notes (day, source_id, reason, detail) "
        "VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (day, source_id) DO UPDATE SET reason = EXCLUDED.reason, "
        "detail = EXCLUDED.detail",
        note.day, note.source_id, note.reason, note.detail,
    )


async def fetch_notes_on(conn: asyncpg.Connection, day: date) -> list[DegradationNote]:
    rows = await conn.fetch(
        "SELECT day, source_id, reason, detail FROM degradation_notes "
        "WHERE day = $1 ORDER BY source_id",
        day,
    )
    return [
        DegradationNote(
            day=r["day"], source_id=r["source_id"], reason=r["reason"], detail=r["detail"]
        )
        for r in rows
    ]


class InMemoryDegradationStore:
    def __init__(self) -> None:
        self._notes: list[DegradationNote] = []

    def add(self, note: DegradationNote) -> None:
        self._notes.append(note)

    def for_day(self, day: date) -> list[DegradationNote]:
        return [n for n in self._notes if n.day == day]


@dataclass
class DailyFetchResult:
    items: dict[str, list[TrendItem]] = field(default_factory=dict)
    notes: list[DegradationNote] = field(default_factory=list)


def fetch_all_sources(
    registry: SourceRegistry, day: date, store: DegradationStore
) -> DailyFetchResult:
    """Fetch every registered source for one day; a failing source degrades to a
    persisted DegradationNote instead of blocking the batch (E6 row 1)."""
    result = DailyFetchResult()
    for source_id in sorted(registry.source_ids()):
        if not registry.is_enabled(source_id):
            _note(result, store, day, source_id, "disabled", "disabled via feature flag")
            continue
        source = registry.create(source_id)
        try:
            result.items[source_id] = source.fetch_daily(day)
        except RateLimitedError as err:
            _note(result, store, day, source_id, "rate_limited", str(err))
        except ParseDrift as err:
            _note(result, store, day, source_id, "parse_drift", str(err))
        except SourceFetchError as err:
            _note(result, store, day, source_id, "fetch_failed", str(err))
    return result


def _note(
    result: DailyFetchResult,
    store: DegradationStore,
    day: date,
    source_id: str,
    reason: DegradationReason,
    detail: str,
) -> None:
    note = DegradationNote(day=day, source_id=source_id, reason=reason, detail=detail)
    result.notes.append(note)
    store.add(note)


def card_gap_annotations(notes: list[DegradationNote]) -> list[str]:
    """E6 row 1 user-facing copy for the evidence-card gap slot.

    FIX-12：**句子里 NEVER 有机器值**。改前拼的是
    `f"今日缺 {源} 数据（{n.reason}）"`——`rate_limited` / `parse_drift` /
    `fetch_failed` 会原样上屏，而它们是给机器看的。

    原因**没被丢掉**：`DegradationNote.reason` 本来就是结构化字段，
    调用方按它取标签即可（`DS-03` 的标签表就是干这个的）。
    在这里拼一句成型的话，前端就换不掉它。
    """
    return [f"今日缺 {n.source_id} 数据" for n in notes]
