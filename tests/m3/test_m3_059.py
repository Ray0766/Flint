"""M3-059 acceptance tests: PartialBlockEvent progressive delivery.

Acceptance (tasks.json M3-059):
  - draft emits one PartialBlockEvent per block (seq continues the M1-034
    stream monotonically)
  - partial_output_ref updates per section for disconnect-resume reads (D8)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.compose.progressive import emit_partial_blocks
from flint.domain.models import Block, HeadingContent
from flint.jobs.events import PgJobEventStream

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
            await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'm3059-%'")
            await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'm3059-%'")
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, "
                "budget, cost_accum, cancel_requested, initiated_by, created_at, "
                "updated_at) VALUES ('m3059-j1', 'report', "
                "'{\"kind\":\"user\",\"id\":\"u-1\"}', 'drafting', 0, 0, 0, false, "
                "'u-1', $1, $1)",
                NOW,
            )
        finally:
            await conn.close()

    run(setup())


def block(block_id: str, section: str, order: int) -> Block:
    return Block(
        block_id=block_id, deliverable_id="d-1", section_id=section, order=order,
        type="heading", content=HeadingContent(kind="heading", level=1, text="t"),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
    )


def test_one_event_per_block_monotonic_and_ref_updates() -> None:
    events = PgJobEventStream(dsn=DSN)
    blocks = [
        block("b-1", "s-1", 0), block("b-2", "s-1", 1), block("b-3", "s-2", 0),
    ]

    async def scenario() -> None:
        refs = await emit_partial_blocks(
            DSN, events, job_id="m3059-j1", blocks=blocks,
            section_ref_factory=lambda section: f"partial-{section}", ts=NOW,
        )
        assert refs == ["partial-s-1", "partial-s-2"], "one ref per section"

        replay = await events.replay("m3059-j1", 0)
        assert [e.seq for e in replay] == [1, 2, 3], "monotonic gapless"
        payloads = [e.payload for e in replay]
        assert all(p.kind == "partial_block" for p in payloads)
        assert [p.block_id for p in payloads] == ["b-1", "b-2", "b-3"]  # type: ignore[union-attr]

        conn = await asyncpg.connect(DSN)
        try:
            ref: str = await conn.fetchval(
                "SELECT partial_output_ref FROM jobs WHERE job_id = 'm3059-j1'"
            )
        finally:
            await conn.close()
        assert ref == "partial-s-2", "latest section ref lands for resume reads"

    run(scenario())


def test_events_continue_after_existing_stream() -> None:
    from flint.domain.models import StatusChanged

    events = PgJobEventStream(dsn=DSN)

    async def scenario() -> None:
        await events.append(
            "m3059-j1", StatusChanged(kind="status", state="drafting"), ts=NOW
        )
        await emit_partial_blocks(
            DSN, events, job_id="m3059-j1", blocks=[block("b-9", "s-9", 0)],
            section_ref_factory=lambda section: f"partial-{section}", ts=NOW,
        )
        replay = await events.replay("m3059-j1", 0)
        assert [e.seq for e in replay] == [1, 2], "continues, never restarts"

    run(scenario())
