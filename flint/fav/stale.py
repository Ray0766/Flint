"""FAV-02：收藏快照 stale 打标 + 双动作（查看当时版本 / 更新到最新）。

## 两个动作是一对

「更新到最新」若直接覆盖，「查看当时版本」就没有数据可看了——而用户按下更新时
并不知道那是一次不可撤销的擦除。所以旧值进历史，且保留**每一次**旧值：
只留上一次的话，「当时版本」最远只能回到昨天，可用户想回的是**他收藏那天**看到的东西。

## stale 只能由统一口径置 True（§6-H1）

冻结件 `Favorite` 的 docstring 写死这一条，本模块照做：判定转调 HOTSPOT-06 的
适配器（它 import 自 contracts 通道），本模块**一行比对逻辑都不写**，
更 NEVER 按时间戳推断新鲜度——按时间戳推断看起来总是对的：三个月前的收藏
「显然」旧了，可事实一个字没变时那个标记只让用户白重跑一次；而昨天的收藏
也可能因一次事实移除而彻底失效。新旧只有账本说了算。

## 快照没记账本版本时报错，NEVER 猜

悄悄放过的话，界面会告诉用户「这份收藏是最新的」，而我们根本没能力知道。

端点口径（沿用 FAV-01/FAV-05 的落法：函数即端点语义，路由随 E2 接线）：
`POST /favorites/{id}/refresh-snapshot` → `refresh_snapshot`。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from flint.analysis.stale_adapter import DiffChannel, analysis_stale
from flint.fav.store import FavoriteStoreLike

_LEDGER_VERSION_KEY = "ledger_version"
_FACT_IDS_KEY = "fact_ids"


class StaleNotEvaluated(Exception):
    """快照里没有判新旧所需的信息，故本次**没有**做出判定。"""

    def __init__(self, favorite_id: str, missing: str) -> None:
        super().__init__(
            f"收藏 {favorite_id} 的快照缺 {missing}：无从判断新旧，"
            "NEVER 猜一个版本、更 NEVER 悄悄标成不陈旧"
        )
        self.missing = missing


@dataclass(frozen=True)
class HistoryEntry:
    snapshot: dict[str, Any]
    replaced_at: datetime


@dataclass
class SnapshotHistoryStore:
    """被替换掉的旧快照，按替换时间顺序保留。内存实现；SQL 实现随 E2 接入。"""

    _rows: dict[str, list[HistoryEntry]] = field(default_factory=dict)

    def append(self, favorite_id: str, entry: HistoryEntry) -> None:
        self._rows.setdefault(favorite_id, []).append(
            HistoryEntry(
                snapshot=copy.deepcopy(entry.snapshot), replaced_at=entry.replaced_at,
            )
        )

    def entries(self, favorite_id: str) -> list[HistoryEntry]:
        """返回**副本**：改返回值 NEVER 影响库里那份（FAV-01 同款口径）。"""
        return [
            HistoryEntry(snapshot=copy.deepcopy(e.snapshot), replaced_at=e.replaced_at)
            for e in self._rows.get(favorite_id, [])
        ]


def _owned(store: FavoriteStoreLike, favorite_id: str, owner: Any) -> Any:
    row = store.get(favorite_id)
    if row is None:
        raise KeyError(f"unknown favorite: {favorite_id}")
    if row.owner.kind != owner.kind or row.owner.id != owner.id:
        raise PermissionError(
            f"收藏 {favorite_id} 不属于当前用户（越权，NEVER 静默跳过）"
        )
    return row


def evaluate_snapshot_stale(
    store: FavoriteStoreLike,
    *,
    favorite_id: str,
    owner: Any,
    project_id: str,
    current_version: int,
    diff_channel: DiffChannel,
) -> Any:
    """按 §6-H1 统一口径判这份收藏是否陈旧，并把结果落库。"""
    row = _owned(store, favorite_id, owner)
    snapshot = row.evidence_snapshot or {}
    taken_at = snapshot.get(_LEDGER_VERSION_KEY)
    if taken_at is None:
        raise StaleNotEvaluated(favorite_id, _LEDGER_VERSION_KEY)
    cited = snapshot.get(_FACT_IDS_KEY)
    if cited is None:
        raise StaleNotEvaluated(favorite_id, _FACT_IDS_KEY)

    verdict = analysis_stale(
        diff_channel, project_id=project_id, analysed_at_version=int(taken_at),
        current_version=current_version, cited_fact_ids=cited,
    )
    updated = replace(row, snapshot_stale=verdict.stale)
    store.put(updated)
    return store.get(favorite_id)


def refresh_snapshot(
    store: FavoriteStoreLike,
    history: SnapshotHistoryStore,
    *,
    favorite_id: str,
    owner: Any,
    fresh_snapshot: dict[str, Any],
    now: datetime,
) -> Any:
    """更新到最新（`POST /favorites/{id}/refresh-snapshot`）。旧值进历史，NEVER 覆盖丢弃。"""
    if not fresh_snapshot:
        raise ValueError(
            "fresh_snapshot NEVER 为空：用空快照覆盖等于把一份有内容的收藏刷成空壳"
        )
    row = _owned(store, favorite_id, owner)
    if row.evidence_snapshot == fresh_snapshot:
        return store.get(favorite_id)          # 没有旧值可留，历史里多一条只会误导

    history.append(
        favorite_id,
        HistoryEntry(snapshot=copy.deepcopy(row.evidence_snapshot), replaced_at=now),
    )
    # 就地派生副本（NEVER 重建实体：重建会丢掉 created_at 这种收藏时点字段，
    # 而「查看当时版本」正靠它说明那是哪一天的东西），故此处不需要 model 入参。
    updated = replace(
        row, evidence_snapshot=copy.deepcopy(fresh_snapshot), snapshot_stale=False,
    )
    store.put(updated)
    return store.get(favorite_id)


def original_snapshot(
    store: FavoriteStoreLike, history: SnapshotHistoryStore, *, favorite_id: str,
) -> dict[str, Any]:
    """查看当时版本：刷新过就是历史里最早那份，没刷新过就是现在这份（NEVER 空）。"""
    entries = history.entries(favorite_id)
    if entries:
        return entries[0].snapshot
    row = store.get(favorite_id)
    if row is None:
        raise KeyError(f"unknown favorite: {favorite_id}")
    snapshot: dict[str, Any] = row.evidence_snapshot
    return snapshot
