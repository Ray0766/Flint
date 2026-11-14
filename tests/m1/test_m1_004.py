"""M1-004 acceptance tests: job tables migration (jobs / job_steps / job_events).

Acceptance (tasks.json M1-004):
  - unique index on job_events(job_id, seq)
  - serialization round-trip passes for all six JobCheckpoint kinds
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import (
    AnalysisCheckpoint,
    DraftCheckpoint,
    IngestCheckpoint,
    JobCheckpoint,
    PricebookScanCheckpoint,
    RevalidationCheckpoint,
    SpecExportCheckpoint,
)
from flint.jobs.checkpoints import deserialize_checkpoint, serialize_checkpoint

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

SIX_CHECKPOINTS: list[JobCheckpoint] = [
    AnalysisCheckpoint(
        kind="gate1_analysis",
        executed_query_ids=["q1", "q2"],
        phase="judge",
        draft_claim_ids=["cl-1"],
    ),
    DraftCheckpoint(kind="draft", completed_section_ids=["s1", "s2"], ledger_version=3),
    IngestCheckpoint(kind="daily_ingest", day=date(2026, 7, 23), sources_done=["weibo"]),
    RevalidationCheckpoint(
        kind="revalidation", target_deliverable_id="d-9", checked_sources=["papers"]
    ),
    PricebookScanCheckpoint(kind="pricebook_scan", scanned_until_entry="pe-42"),
    SpecExportCheckpoint(
        kind="spec_export", validated_packages=["httpx"], task_ids_done=["T-1"]
    ),
]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── checkpoint serialization (pure) ───────────────────────


@pytest.mark.parametrize("checkpoint", SIX_CHECKPOINTS, ids=lambda c: c.kind)
def test_six_checkpoint_kinds_roundtrip(checkpoint: JobCheckpoint) -> None:
    blob = serialize_checkpoint(checkpoint)
    assert isinstance(blob, str)
    restored = deserialize_checkpoint(blob)
    assert restored == checkpoint
    assert type(restored) is type(checkpoint)


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValueError, match="unknown checkpoint kind"):
        deserialize_checkpoint('{"kind": "made_up"}')


# ── migration schema (DB) ─────────────────────────────────


@pytest.fixture(scope="module")
def migrated() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, f"alembic upgrade failed:\n{result.stderr}"


@pytest.mark.compose
def test_three_job_tables_exist(migrated: None) -> None:
    async def tables() -> set[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            return {r["tablename"] for r in rows}
        finally:
            await conn.close()

    assert {"jobs", "job_steps", "job_events"} <= run(tables())


@pytest.mark.compose
def test_job_events_seq_unique_index_enforced(migrated: None) -> None:
    async def attempt() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM job_events WHERE job_id = 'm1004-j'")
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
                "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
                "VALUES ('m1004-j', 'daily_ingest', '{\"kind\":\"org\",\"id\":\"sys\"}', "
                "'queued', 0, 0, 0, false, 'u-sys', now(), now()) "
                "ON CONFLICT (job_id) DO NOTHING"
            )
            await conn.execute(
                "INSERT INTO job_events (job_id, seq, ts, payload) "
                "VALUES ('m1004-j', 1, now(), '{\"kind\":\"status\",\"state\":\"queued\"}')"
            )
            await conn.execute(
                "INSERT INTO job_events (job_id, seq, ts, payload) "
                "VALUES ('m1004-j', 1, now(), '{\"kind\":\"status\",\"state\":\"queued\"}')"
            )
        finally:
            await conn.close()

    with pytest.raises(asyncpg.UniqueViolationError):
        run(attempt())
