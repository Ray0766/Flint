"""M1-034 acceptance tests: JobEventStream (monotonic seq + replay).

Acceptance (tasks.json M1-034):
  - replay(after_seq) back-fills correctly
  - the disconnect/reconnect integration case passes
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from flint.domain.models import (
    JobEvent,
    JobFailedEvent,
    PartialBlockEvent,
    StatusChanged,
    StepEvent,
)
from flint.jobs.events import PgJobEventStream, SeqRegression

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
T0 = datetime(2026, 7, 23, 9, 0, 0, tzinfo=UTC)
JOB_ID = "m1034-job"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def seeded_job() -> None:
    async def setup() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'm1034-%'")
            await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'm1034-%'")
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ($1, 'daily_ingest', '{\"kind\":\"org\",\"id\":\"sys\"}', "
                "'queued', 0, 0, 0, false, 'u-sys', $2, $2)",
                JOB_ID,
                T0,
            )
        finally:
            await conn.close()

    run(setup())


def stream() -> PgJobEventStream:
    return PgJobEventStream(dsn=DSN)


def test_append_assigns_monotonic_seq() -> None:
    s = stream()
    e1 = run(s.append(JOB_ID, StatusChanged(kind="status", state="retrieving"), ts=T0))
    e2 = run(s.append(JOB_ID, StepEvent(kind="step", step_name="weibo", phase="start", cost=None), ts=T0 + timedelta(seconds=1)))
    e3 = run(s.append(JOB_ID, PartialBlockEvent(kind="partial_block", block_id="b-1"), ts=T0 + timedelta(seconds=2)))
    assert [e1.seq, e2.seq, e3.seq] == [1, 2, 3]


def test_emit_rejects_stale_or_duplicate_seq() -> None:
    s = stream()
    run(s.append(JOB_ID, StatusChanged(kind="status", state="retrieving"), ts=T0))
    stale = JobEvent(
        job_id=JOB_ID, seq=1, ts=T0, payload=JobFailedEvent(kind="failed", reason="x")
    )
    with pytest.raises(SeqRegression):
        run(s.emit(stale))


def test_replay_after_seq_backfills_exact_tail() -> None:
    s = stream()
    payloads = [
        StatusChanged(kind="status", state="retrieving"),
        StepEvent(kind="step", step_name="gtrends", phase="start", cost=None),
        StepEvent(kind="step", step_name="gtrends", phase="end", cost=0.1),
        StatusChanged(kind="status", state="done"),
    ]
    for i, p in enumerate(payloads):
        run(s.append(JOB_ID, p, ts=T0 + timedelta(seconds=i)))

    tail = run(s.replay(JOB_ID, after_seq=2))
    assert [e.seq for e in tail] == [3, 4]
    assert tail[0].payload == payloads[2]
    assert tail[1].payload == payloads[3]
    assert run(s.replay(JOB_ID, after_seq=4)) == []
    full = run(s.replay(JOB_ID, after_seq=0))
    assert [e.seq for e in full] == [1, 2, 3, 4]


def test_payload_union_roundtrips_all_four_kinds() -> None:
    s = stream()
    payloads = [
        StatusChanged(kind="status", state="judging"),
        StepEvent(kind="step", step_name="arxiv", phase="end", cost=0.05),
        PartialBlockEvent(kind="partial_block", block_id="b-9"),
        JobFailedEvent(kind="failed", reason="upstream 503"),
    ]
    for i, p in enumerate(payloads):
        run(s.append(JOB_ID, p, ts=T0 + timedelta(seconds=i)))
    replayed = run(s.replay(JOB_ID, after_seq=0))
    assert [e.payload for e in replayed] == payloads
    for event, expected in zip(replayed, payloads):
        assert type(event.payload) is type(expected)


def test_disconnect_reconnect_integration() -> None:
    """A consumer reads through seq 2, drops, misses live events 3..5, then
    reconnects with Last-Event-ID=2: replay must hand back exactly 3..5 and
    the stitched log equals the full ordered stream (D8 semantics)."""
    s = stream()
    for i in range(1, 6):
        run(
            s.append(
                JOB_ID,
                PartialBlockEvent(kind="partial_block", block_id=f"b-{i}"),
                ts=T0 + timedelta(seconds=i),
            )
        )

    seen_before_drop = run(s.replay(JOB_ID, after_seq=0))[:2]
    last_event_id = seen_before_drop[-1].seq
    assert last_event_id == 2

    backfill = run(s.replay(JOB_ID, after_seq=last_event_id))
    stitched = seen_before_drop + backfill
    assert [e.seq for e in stitched] == [1, 2, 3, 4, 5]
    full = run(s.replay(JOB_ID, after_seq=0))
    assert stitched == full


def test_streams_isolated_per_job() -> None:
    async def second_job() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ('m1034-other', 'daily_ingest', "
                "'{\"kind\":\"org\",\"id\":\"sys\"}', 'queued', 0, 0, 0, false, "
                "'u-sys', $1, $1)",
                T0,
            )
        finally:
            await conn.close()

    run(second_job())
    s = stream()
    run(s.append(JOB_ID, StatusChanged(kind="status", state="retrieving"), ts=T0))
    e = run(s.append("m1034-other", StatusChanged(kind="status", state="retrieving"), ts=T0))
    assert e.seq == 1, "seq is per-job, not global"
    assert len(run(s.replay("m1034-other", after_seq=0))) == 1
