"""M3-041 acceptance tests: lock (block/section).

Acceptance (tasks.json M3-041):
  - both lock scopes persist and enter the protection predicate
  - re-locking is idempotent; unlock stays an owner-semantics slot
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.compose.blocks import PgBlockStore, is_protected
from flint.domain.models import Block, HeadingContent
from flint.intervene.lock import PgLockService

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def setup() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM blocks WHERE block_id LIKE 'm3041-%'")
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3041-%'"
            )
            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, "
                "version, supersedes, inputs, ledger_version, generation_record_id, "
                "stale_reasons, created_at, reproducible) VALUES ('m3041-d1', 'p-1', "
                "'report', 1, NULL, '[]'::jsonb, NULL, 'gr-1', '[]'::jsonb, $1, true)",
                NOW,
            )
        finally:
            await conn.close()

    run(setup())


def make_block(block_id: str, section: str, order: int) -> Block:
    return Block(
        block_id=block_id, deliverable_id="m3041-d1", section_id=section,
        order=order, type="heading",
        content=HeadingContent(kind="heading", level=1, text=block_id),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
    )


def seed_tree() -> None:
    store = PgBlockStore(dsn=DSN)
    run(store.save_tree("m3041-d1", [
        make_block("m3041-b1", "s-1", 0),
        make_block("m3041-b2", "s-1", 1),
        make_block("m3041-b3", "s-2", 0),
    ]))


def test_block_lock_persists_into_protection() -> None:
    seed_tree()
    service = PgLockService(dsn=DSN)
    run(service.lock("m3041-b1", scope="block"))
    tree = run(PgBlockStore(dsn=DSN).load_tree("m3041-d1"))
    by_id = {b.block_id: b for b in tree}
    assert by_id["m3041-b1"].locked is True
    assert is_protected(by_id["m3041-b1"]) is True
    assert by_id["m3041-b2"].locked is False, "sibling untouched"


def test_section_lock_covers_all_blocks_in_section() -> None:
    seed_tree()
    service = PgLockService(dsn=DSN)
    run(service.lock("s-1", scope="section"))
    tree = run(PgBlockStore(dsn=DSN).load_tree("m3041-d1"))
    by_id = {b.block_id: b for b in tree}
    assert by_id["m3041-b1"].locked and by_id["m3041-b2"].locked
    assert by_id["m3041-b3"].locked is False, "other section untouched"


def test_relock_idempotent() -> None:
    seed_tree()
    service = PgLockService(dsn=DSN)
    run(service.lock("m3041-b1", scope="block"))
    run(service.lock("m3041-b1", scope="block"))
    tree = run(PgBlockStore(dsn=DSN).load_tree("m3041-d1"))
    locked = [b for b in tree if b.locked]
    assert [b.block_id for b in locked] == ["m3041-b1"]
    assert locked[0].revision == 1, "lock is a flag flip, not a rewrite"


def test_unknown_target_raises() -> None:
    service = PgLockService(dsn=DSN)
    with pytest.raises(KeyError):
        run(service.lock("m3041-ghost", scope="block"))
