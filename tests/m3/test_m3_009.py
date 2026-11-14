"""M3-009 acceptance tests: block tree store + revision + protection predicate.

Acceptance (tasks.json M3-009):
  - stable tree order (section + order) and monotonic revision
  - protection predicate (locked / author==user / user_modified) implemented
    at a single point
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.compose.blocks import (
    PROTECTED_SQL_PREDICATE,
    PgBlockStore,
    is_protected,
)
from flint.domain.models import Block, HeadingContent

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM blocks WHERE block_id LIKE 'm3009-%'")
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3009-%'"
            )
            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, "
                "version, supersedes, inputs, ledger_version, generation_record_id, "
                "stale_reasons, created_at, reproducible) VALUES ('m3009-d1', 'p-1', "
                "'report', 1, NULL, '[]'::jsonb, NULL, 'gr-1', '[]'::jsonb, $1, true) "
                "ON CONFLICT DO NOTHING",
                NOW,
            )
        finally:
            await conn.close()

    run(wipe())


def make_block(block_id: str, section: str, order: int, **overrides: Any) -> Block:
    base: dict[str, Any] = {
        "block_id": block_id, "deliverable_id": "m3009-d1", "section_id": section,
        "order": order, "type": "heading",
        "content": HeadingContent(kind="heading", level=1, text=block_id),
        "claim_ids": [], "fact_ids": [], "author": "system", "revision": 1,
        "locked": False,
    }
    base.update(overrides)
    return Block(**base)


def test_protection_predicate_single_point() -> None:
    assert is_protected(make_block("b", "s", 0)) is False
    assert is_protected(make_block("b", "s", 0, locked=True)) is True
    assert is_protected(make_block("b", "s", 0, author="user")) is True
    assert is_protected(make_block("b", "s", 0, user_modified=True)) is True
    for clause in ("locked", "author = 'user'", "user_modified"):
        assert clause in PROTECTED_SQL_PREDICATE, "SQL predicate mirrors the three"


def test_tree_order_stable_and_round_trip() -> None:
    store = PgBlockStore(dsn=DSN)
    blocks = [
        make_block("m3009-b3", "s-2", 0),
        make_block("m3009-b1", "s-1", 0),
        make_block("m3009-b2", "s-1", 1, author="user"),
    ]
    run(store.save_tree("m3009-d1", blocks))
    loaded = run(store.load_tree("m3009-d1"))
    assert [b.block_id for b in loaded] == ["m3009-b1", "m3009-b2", "m3009-b3"], (
        "section then order"
    )
    assert loaded[1].author == "user"
    assert loaded == sorted(blocks, key=lambda b: (b.section_id, b.order))


def test_revision_bump_monotonic_and_protected_untouched() -> None:
    store = PgBlockStore(dsn=DSN)
    run(store.save_tree("m3009-d1", [make_block("m3009-b1", "s-1", 0)]))
    bumped = run(
        store.replace_block(
            "m3009-b1",
            make_block("m3009-b1", "s-1", 0,
                       content=HeadingContent(kind="heading", level=2, text="v2")),
        )
    )
    assert bumped.revision == 2, "revision monotonic +1"
    reloaded = run(store.load_tree("m3009-d1"))
    assert reloaded[0].revision == 2
    content = reloaded[0].content
    assert isinstance(content, HeadingContent) and content.level == 2


def test_replace_protected_block_rejected() -> None:
    store = PgBlockStore(dsn=DSN)
    run(store.save_tree("m3009-d1", [make_block("m3009-b9", "s-1", 0, locked=True)]))
    with pytest.raises(PermissionError, match="protected"):
        run(
            store.replace_block(
                "m3009-b9", make_block("m3009-b9", "s-1", 0, locked=True)
            )
        )
