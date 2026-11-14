"""JobEventStream：seq 单调 + replay（M1-034，contracts/protocols.py#JobEventStream）。

- seq 按 job 单调递增（(job_id, seq) 唯一索引兜底），emit 拒绝回退/重复
  （SeqRegression）；append 原子取号（INSERT..SELECT MAX+1）。
- replay(job_id, after_seq)：Last-Event-ID 补发依据（D8）；断线重连 =
  先 GET /jobs/{id} 快照，再 replay 续流（E3）。SSE 传输层归 api（M2），
  本模块只负责流语义。
- payload 判别联合（StatusChanged/StepEvent/PartialBlockEvent/JobFailedEvent）
  JSONB 序列化，kind 表恢复精确类型（审16）。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, Final

import asyncpg

from flint.domain.models import (
    JobEvent,
    JobEventPayload,
    JobFailedEvent,
    PartialBlockEvent,
    StatusChanged,
    StepEvent,
)


# DESIGN-01 补一条：`design_delta`（`contracts_v04` 的 §9-P3 增量块）。
# 不补的话，设计台的块**写得进去、读不回来**——`_deserialize` 会在 replay 时抛
# 「unknown job event payload kind」，而那正是断线重连要走的那条路。
# 它从 `contracts_v04` 取（v0.4 additive 面），冻结件 `flint/domain/models` 一字不动。
def _design_delta_type() -> type:
    from contracts_v04.models_v04 import DesignDelta

    return DesignDelta


_PAYLOAD_TYPES: Final[dict[str, type]] = {
    "status": StatusChanged,
    "step": StepEvent,
    "partial_block": PartialBlockEvent,
    "failed": JobFailedEvent,
    "design_delta": _design_delta_type(),
}


class SeqRegression(Exception):
    def __init__(self, job_id: str, seq: int, current_max: int) -> None:
        super().__init__(
            f"job {job_id}: seq {seq} not after current max {current_max} "
            "(seq must increase monotonically)"
        )


def _serialize(payload: JobEventPayload) -> str:
    return json.dumps(asdict(payload), ensure_ascii=False)


def _deserialize(blob: str) -> JobEventPayload:
    data: dict[str, Any] = json.loads(blob)
    cls = _PAYLOAD_TYPES.get(data.get("kind", ""))
    if cls is None:
        raise ValueError(f"unknown job event payload kind: {data.get('kind')!r}")
    result: JobEventPayload = cls(**data)
    return result


class PgJobEventStream:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def append(
        self, job_id: str, payload: JobEventPayload, ts: datetime
    ) -> JobEvent:
        """Atomically assign the next seq and persist the event."""
        conn = await asyncpg.connect(self._dsn)
        try:
            seq: int = await conn.fetchval(
                "INSERT INTO job_events (job_id, seq, ts, payload) "
                "SELECT $1, COALESCE(MAX(seq), 0) + 1, $2, $3::jsonb "
                "FROM job_events WHERE job_id = $1 RETURNING seq",
                job_id,
                ts,
                _serialize(payload),
            )
        finally:
            await conn.close()
        return JobEvent(job_id=job_id, seq=seq, ts=ts, payload=payload)

    async def emit(self, event: JobEvent) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            current_max: int = await conn.fetchval(
                "SELECT COALESCE(MAX(seq), 0) FROM job_events WHERE job_id = $1",
                event.job_id,
            )
            if event.seq <= current_max:
                raise SeqRegression(event.job_id, event.seq, current_max)
            await conn.execute(
                "INSERT INTO job_events (job_id, seq, ts, payload) "
                "VALUES ($1, $2, $3, $4::jsonb)",
                event.job_id,
                event.seq,
                event.ts,
                _serialize(event.payload),
            )
        finally:
            await conn.close()

    async def replay(self, job_id: str, after_seq: int) -> list[JobEvent]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT job_id, seq, ts, payload FROM job_events "
                "WHERE job_id = $1 AND seq > $2 ORDER BY seq",
                job_id,
                after_seq,
            )
        finally:
            await conn.close()
        return [
            JobEvent(
                job_id=r["job_id"],
                seq=r["seq"],
                ts=r["ts"],
                payload=_deserialize(r["payload"]),
            )
            for r in rows
        ]
