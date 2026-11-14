"""M2-007 acceptance tests: SnapshotStore (180-day retention).

Acceptance (tasks.json M2-007):
  - put/get byte-level roundtrip; snapshot_id channel ready for GenerationRecord
  - expiry sweep deletes only rows older than 180 days (boundary test)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from flint.store.snapshot import PgSnapshotStore

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-m2007-%'")
        finally:
            await conn.close()

    run(wipe())


def make_store(counter: list[int]) -> PgSnapshotStore:
    def next_id() -> str:
        counter[0] += 1
        return f"snap-m2007-{counter[0]}"

    return PgSnapshotStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def test_put_get_byte_roundtrip() -> None:
    store = make_store([0])
    payload = "检索快照：固态电池 20 篇".encode() + b"\x00\xff\x01"
    snapshot_id = run(store.put(payload))
    assert snapshot_id == "snap-m2007-1", "id channel for GenerationRecord"
    assert run(store.get(snapshot_id)) == payload


def test_get_missing_raises() -> None:
    store = make_store([0])
    with pytest.raises(KeyError):
        run(store.get("snap-m2007-ghost"))


def test_expiry_sweeps_only_beyond_180_days() -> None:
    counter = [0]
    fresh_store = make_store(counter)
    id_179 = run(
        PgSnapshotStore(
            dsn=DSN, id_factory=lambda: "snap-m2007-179d",
            now=lambda: NOW - timedelta(days=179),
        ).put(b"still retained")
    )
    id_181 = run(
        PgSnapshotStore(
            dsn=DSN, id_factory=lambda: "snap-m2007-181d",
            now=lambda: NOW - timedelta(days=181),
        ).put(b"expired")
    )
    removed = run(fresh_store.cleanup_expired())
    assert removed == 1
    assert run(fresh_store.get(id_179)) == b"still retained"
    with pytest.raises(KeyError):
        run(fresh_store.get(id_181))
