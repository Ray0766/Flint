"""LineageResult 组装、落库与血缘审计视图（M1-029，v0.4 + owner 决策清单）。

- build_lineage_result：五步产物 → 冻结 LineageResult。决策①②：复活簇只记
  RevivedEvent（keyword_ids 取当日 assignments），不再重复出 ContinuedEvent。
- save_lineage_result：append-only 双写 lineage_results + lineage_audit
  （决策⑥：每条 event 引用的全部簇 ID 摊开成行，自带 event 拷贝）。
- fetch_cluster_lineage / export_cluster_lineage_yaml：任一簇按日序拉全链；
  yaml 导出即标注工具（M1-038）的输入。
- prune_expired（决策⑤ 路 A）：全量重批记录只留最近 keep_days 个自然日；
  关系边永久留在 clusters 表血缘字段，不受清理影响。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, Final

import asyncpg
import yaml

from flint.domain.models import (
    CentroidDriftAudit,
    ContinuedEvent,
    LineageEvent,
    LineageResult,
    MergedEvent,
    NewClusterEvent,
    RevivedEvent,
    SplitEvent,
)
from flint.lineage.s23 import LineageDecision

_EVENT_TYPES: Final[dict[str, type]] = {
    "continued": ContinuedEvent,
    "split": SplitEvent,
    "merged": MergedEvent,
    "new": NewClusterEvent,
    "revived": RevivedEvent,
}


def build_lineage_result(
    lineage_id: str,
    day: date,
    assignments: dict[str, list[str]],
    revived_cluster_ids: list[str],
    decisions: list[LineageDecision],
    naming_degraded: dict[str, bool],
    dormant_cluster_ids: list[str],
    drift_audits: list[CentroidDriftAudit],
    tau_match: float,
    tau_link: float,
    dormant_after_days: int,
    generated_at: datetime,
) -> LineageResult:
    events: list[LineageEvent] = []
    revived = set(revived_cluster_ids)
    for cluster_id in sorted(assignments):
        if cluster_id in revived:
            continue  # 决策①：复活簇不重复出 ContinuedEvent
        events.append(
            ContinuedEvent(
                kind="continued",
                cluster_id=cluster_id,
                keyword_ids=list(assignments[cluster_id]),
            )
        )
    for cluster_id in sorted(revived):
        events.append(
            RevivedEvent(
                kind="revived",
                cluster_id=cluster_id,
                keyword_ids=list(assignments.get(cluster_id, [])),
            )
        )
    for decision in decisions:
        if decision.kind == "split":
            events.append(
                SplitEvent(
                    kind="split",
                    new_cluster_id=decision.new_cluster_id,
                    parent_cluster_ids=list(decision.parent_cluster_ids),
                    keyword_ids=list(decision.keyword_ids),
                )
            )
        elif decision.kind == "merge":
            events.append(
                MergedEvent(
                    kind="merged",
                    new_cluster_id=decision.new_cluster_id,
                    merged_cluster_ids=list(decision.parent_cluster_ids),
                    keyword_ids=list(decision.keyword_ids),
                )
            )
        else:
            events.append(
                NewClusterEvent(
                    kind="new",
                    cluster_id=decision.new_cluster_id,
                    parent_cluster_ids=list(decision.parent_cluster_ids),
                    keyword_ids=list(decision.keyword_ids),
                    naming_degraded=naming_degraded.get(
                        decision.new_cluster_id, False
                    ),
                )
            )
    return LineageResult(
        lineage_id=lineage_id,
        day=day,
        events=events,
        dormant_cluster_ids=list(dormant_cluster_ids),
        drift_audits=list(drift_audits),
        tau_match=tau_match,
        tau_link=tau_link,
        dormant_after_days=dormant_after_days,
        generated_at=generated_at,
    )


def serialize_events(events: list[LineageEvent]) -> str:
    return json.dumps([asdict(e) for e in events], ensure_ascii=False)


def deserialize_events(blob: str) -> list[LineageEvent]:
    result: list[LineageEvent] = []
    for payload in json.loads(blob):
        cls = _EVENT_TYPES.get(payload.get("kind"))
        if cls is None:
            raise ValueError(f"unknown lineage event kind: {payload.get('kind')!r}")
        result.append(cls(**payload))
    return result


def _audit_rows(result: LineageResult) -> list[tuple[str, date, int, str, str, str, str]]:
    """决策⑥：摊开每条 event 引用的全部簇 ID；dormant 以合成行入审计
    （event_index=-1），使「任一簇可查完整血缘链」含休眠转换。"""
    rows: list[tuple[str, date, int, str, str, str, str]] = []

    def add(index: int, kind: str, cluster_id: str, role: str, event: dict[str, Any]) -> None:
        rows.append(
            (
                result.lineage_id,
                result.day,
                index,
                kind,
                cluster_id,
                role,
                json.dumps(event, ensure_ascii=False),
            )
        )

    for i, event in enumerate(result.events):
        payload = asdict(event)
        if isinstance(event, ContinuedEvent | RevivedEvent):
            add(i, event.kind, event.cluster_id, "subject", payload)
        elif isinstance(event, SplitEvent):
            add(i, event.kind, event.new_cluster_id, "subject", payload)
            for parent in event.parent_cluster_ids:
                add(i, event.kind, parent, "parent", payload)
        elif isinstance(event, MergedEvent):
            add(i, event.kind, event.new_cluster_id, "subject", payload)
            for old in event.merged_cluster_ids:
                add(i, event.kind, old, "merged", payload)
        else:
            add(i, event.kind, event.cluster_id, "subject", payload)
            for parent in event.parent_cluster_ids:
                add(i, event.kind, parent, "parent", payload)
    for cluster_id in result.dormant_cluster_ids:
        add(-1, "dormant", cluster_id, "subject", {"kind": "dormant", "cluster_id": cluster_id})
    return rows


async def save_lineage_result_on(
    conn: asyncpg.Connection, result: LineageResult
) -> None:
    """Connection-scoped variant: caller owns the transaction boundary
    (M1-040：cluster_lineage 步全体写入与 job_steps 记录同事务)。"""
    await conn.execute(
        "INSERT INTO lineage_results (lineage_id, day, events, "
        "dormant_cluster_ids, drift_audits, tau_match, tau_link, "
        "dormant_after_days, generated_at) "
        "VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6, $7, $8, $9)",
        result.lineage_id,
        result.day,
        serialize_events(result.events),
        json.dumps(result.dormant_cluster_ids, ensure_ascii=False),
        json.dumps([asdict(a) for a in result.drift_audits], ensure_ascii=False),
        result.tau_match,
        result.tau_link,
        result.dormant_after_days,
        result.generated_at,
    )
    await conn.executemany(
        "INSERT INTO lineage_audit (lineage_id, day, event_index, "
        "event_kind, cluster_id, role, event) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)",
        _audit_rows(result),
    )


async def save_lineage_result(dsn: str, result: LineageResult) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO lineage_results (lineage_id, day, events, "
                "dormant_cluster_ids, drift_audits, tau_match, tau_link, "
                "dormant_after_days, generated_at) "
                "VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb, $6, $7, $8, $9)",
                result.lineage_id,
                result.day,
                serialize_events(result.events),
                json.dumps(result.dormant_cluster_ids, ensure_ascii=False),
                json.dumps([asdict(a) for a in result.drift_audits], ensure_ascii=False),
                result.tau_match,
                result.tau_link,
                result.dormant_after_days,
                result.generated_at,
            )
            await conn.executemany(
                "INSERT INTO lineage_audit (lineage_id, day, event_index, "
                "event_kind, cluster_id, role, event) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)",
                _audit_rows(result),
            )
    finally:
        await conn.close()


async def fetch_cluster_lineage(dsn: str, cluster_id: str) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT lineage_id, day, event_index, event_kind, role, event "
            "FROM lineage_audit WHERE cluster_id = $1 "
            "ORDER BY day, event_index",
            cluster_id,
        )
    finally:
        await conn.close()
    return [
        {
            "lineage_id": r["lineage_id"],
            "day": r["day"],
            "event_index": r["event_index"],
            "event_kind": r["event_kind"],
            "role": r["role"],
            "event": json.loads(r["event"]),
        }
        for r in rows
    ]


async def export_cluster_lineage_yaml(dsn: str, cluster_id: str) -> str:
    chain = await fetch_cluster_lineage(dsn, cluster_id)
    payload = {
        "cluster_id": cluster_id,
        "timeline": [
            {
                "day": row["day"].isoformat(),
                "event_kind": row["event_kind"],
                "role": row["role"],
                "event": row["event"],
            }
            for row in chain
        ],
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


async def prune_expired(dsn: str, today: date, keep_days: int = 15) -> int:
    """决策⑤ 路 A：只留最近 keep_days 个自然日的重批记录（audit 行随
    ondelete CASCADE 一并清）。返回删除的批次数。"""
    cutoff = today.fromordinal(today.toordinal() - keep_days)
    conn = await asyncpg.connect(dsn)
    try:
        status = await conn.execute(
            "DELETE FROM lineage_results WHERE day <= $1", cutoff
        )
    finally:
        await conn.close()
    return int(status.split()[-1])
