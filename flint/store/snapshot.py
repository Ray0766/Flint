"""SnapshotStore：检索快照 180 天保留（M2-007，F2 / 技术方案 E2）。

- put/get 以 bytes 为契约（冻结协议）；snapshot_id 回填
  GenerationRecord.retrieval_snapshot_id，任一 Deliverable 可回放复现。
- cleanup_expired 只清 created_at 距今 >180 天的行（周任务入口）；
  唯一例外 RedactionRecord（审9）归 M3 干预层。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import uuid4

import asyncpg

RETENTION_DAYS: Final[int] = 180


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return f"snap-{uuid4().hex}"


class PgSnapshotStore:
    """冻结协议 SnapshotStore 的 PostgreSQL 实现（async 面，先例 M1-033/034）。"""

    def __init__(
        self,
        dsn: str,
        id_factory: Callable[[], str] = _default_id,
        now: Callable[[], datetime] = _utcnow,
        retention_days: int = RETENTION_DAYS,
    ) -> None:
        self._dsn = dsn
        self._id_factory = id_factory
        self._now = now
        self._retention_days = retention_days

    async def put(self, payload: bytes) -> str:
        snapshot_id = self._id_factory()
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO snapshots (snapshot_id, payload, created_at) "
                "VALUES ($1, $2, $3)",
                snapshot_id, payload, self._now(),
            )
        finally:
            await conn.close()
        return snapshot_id

    async def get(self, snapshot_id: str) -> bytes:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT payload FROM snapshots WHERE snapshot_id = $1", snapshot_id
            )
        finally:
            await conn.close()
        if row is None:
            raise KeyError(f"unknown snapshot: {snapshot_id}")
        payload: bytes = row["payload"]
        return payload

    async def cleanup_expired(self) -> int:
        cutoff = self._now() - timedelta(days=self._retention_days)
        conn = await asyncpg.connect(self._dsn)
        try:
            status = await conn.execute(
                "DELETE FROM snapshots WHERE created_at < $1", cutoff
            )
        finally:
            await conn.close()
        return int(status.split()[-1])
