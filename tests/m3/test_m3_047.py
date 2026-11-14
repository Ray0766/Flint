"""M3-047 acceptance tests: EditEvent persistence (F3).

Acceptance (tasks.json M3-047):
  - all seven actions persist; edit_text on a system block flips
    user_modified
  - before/after snapshots survive round trip
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.compose.blocks import PgBlockStore, is_protected
from flint.domain.models import Block, EditEvent, HeadingContent
from flint.intervene.edits import PgEditService

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)

ACTIONS = ["delete_claim", "edit_text", "remove_citation", "reorder",
           "choose_topic", "lock", "dispute"]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def setup() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM edit_events WHERE event_id LIKE 'm3047-%'"
            )
            await conn.execute("DELETE FROM blocks WHERE block_id LIKE 'm3047-%'")
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3047-%'"
            )
            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, "
                "version, supersedes, inputs, ledger_version, generation_record_id, "
                "stale_reasons, created_at, reproducible) VALUES ('m3047-d1', 'p-1', "
                "'report', 1, NULL, '[]'::jsonb, NULL, 'gr-1', '[]'::jsonb, $1, true)",
                NOW,
            )
        finally:
            await conn.close()

    run(setup())


def event(event_id: str, action: str, block_id: str | None = None,
          before: dict | None = None, after: dict | None = None) -> EditEvent:
    return EditEvent(
        event_id=event_id, deliverable_id="m3047-d1", section_id="s-1",
        block_id=block_id, action=action,  # type: ignore[arg-type]
        before=before, after=after, user_id="u-1", ts=NOW,
    )


def seed_block(block_id: str, author: str) -> None:
    store = PgBlockStore(dsn=DSN)
    run(store.save_tree("m3047-d1", [
        Block(
            block_id=block_id, deliverable_id="m3047-d1", section_id="s-1",
            order=0, type="heading",
            content=HeadingContent(kind="heading", level=1, text="t"),
            claim_ids=[], fact_ids=[], author=author,  # type: ignore[arg-type]
            revision=1, locked=False,
        )
    ]))


def test_all_seven_actions_persist_with_snapshots() -> None:
    service = PgEditService(dsn=DSN)
    for i, action in enumerate(ACTIONS):
        run(service.record(event(
            f"m3047-e{i}", action,
            before={"text": "旧"}, after={"text": "新"},
        )))
    loaded = run(service.events_for("m3047-d1"))
    assert [e.action for e in loaded] == ACTIONS
    assert all(e.before == {"text": "旧"} and e.after == {"text": "新"}
               for e in loaded), "snapshots round trip"


def test_edit_text_on_system_block_flips_user_modified() -> None:
    seed_block("m3047-b1", author="system")
    service = PgEditService(dsn=DSN)
    run(service.record(event("m3047-ex", "edit_text", block_id="m3047-b1")))
    tree = run(PgBlockStore(dsn=DSN).load_tree("m3047-d1"))
    assert tree[0].user_modified is True
    assert is_protected(tree[0]) is True, "flip enters the protection predicate"


def test_edit_text_on_user_block_no_flip_needed() -> None:
    seed_block("m3047-b2", author="user")
    service = PgEditService(dsn=DSN)
    run(service.record(event("m3047-ey", "edit_text", block_id="m3047-b2")))
    tree = run(PgBlockStore(dsn=DSN).load_tree("m3047-d1"))
    assert tree[0].user_modified is False, "author=user already protected"
    assert is_protected(tree[0]) is True


def test_bad_action_rejected_by_check() -> None:
    async def bad() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO edit_events (event_id, deliverable_id, section_id, "
                "block_id, action, before, after, user_id, ts) VALUES "
                "('m3047-bad', 'm3047-d1', NULL, NULL, 'vandalize', NULL, NULL, "
                "'u-1', $1)",
                NOW,
            )
        finally:
            await conn.close()

    with pytest.raises(asyncpg.CheckViolationError):
        run(bad())
