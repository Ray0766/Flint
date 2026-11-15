"""M2-040 acceptance tests: gate1_analysis orchestration (checkpoint + SSE).

Acceptance (tasks.json M2-040):
  - plan -> retrieve -> judge -> validate resumes via AnalysisCheckpoint
  - kill -9 rerun artifacts diff empty and SSE event sequence complete

Plus one filed follow-up from the M2-039 review: the third VerdictCallOutcome
invariant branch (failed without reason) gets its case here (non-compose).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import AnalysisCheckpoint, GenerationRecord
from flint.gate.no_guess import VerdictCallOutcome
from flint.jobs.checkpoints import deserialize_checkpoint
from flint.jobs.gate1 import STEP_ORDER, build_offline_deps, run_gate1

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
KEYWORDS = ["固态电池", "钠离子电池"]

WIPE_SQL = [
    "DELETE FROM job_events WHERE job_id LIKE 'm2040-%'",
    "DELETE FROM job_steps WHERE job_id LIKE 'm2040-%'",
    "DELETE FROM jobs WHERE job_id LIKE 'm2040-%'",
    "DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-m2040-%'",
]

EXPECTED_EVENTS = [
    ("status", "retrieving"),
    ("step", "plan", "start"), ("step", "plan", "end"),
    ("step", "retrieve", "start"), ("step", "retrieve", "end"),
    ("status", "judging"),
    ("step", "judge", "start"), ("step", "judge", "end"),
    ("status", "validating"),
    ("step", "validate", "start"), ("step", "validate", "end"),
    ("status", "done"),
]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


async def _fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(DSN)
    try:
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


async def _artifacts(job_id: str) -> dict[str, Any]:
    """Job-id-independent artifact view: snapshot payloads by content,
    step records by content (checkpoints carry no job-specific data)."""
    conn = await asyncpg.connect(DSN)
    try:
        snaps = await conn.fetch(
            "SELECT payload FROM snapshots WHERE snapshot_id LIKE 'snap-m2040-%' "
            "ORDER BY payload"
        )
        steps = await conn.fetch(
            "SELECT name, state, snapshot_ref FROM job_steps WHERE job_id = $1 "
            "ORDER BY step_index",
            job_id,
        )
        state = await conn.fetchval(
            "SELECT state FROM jobs WHERE job_id = $1", job_id
        )
        return {
            "snapshots": [bytes(r["payload"]) for r in snaps],
            "steps": [(r["name"], r["state"], r["snapshot_ref"]) for r in steps],
            "state": state,
        }
    finally:
        await conn.close()


def _event_shape(payload: dict[str, Any]) -> tuple[str, ...]:
    if payload["kind"] == "status":
        return ("status", payload["state"])
    return ("step", payload["step_name"], payload["phase"])


async def _events(job_id: str) -> list[tuple[int, tuple[str, ...]]]:
    rows = await _fetch(
        "SELECT seq, payload FROM job_events WHERE job_id = $1 ORDER BY seq", job_id
    )
    return [(r["seq"], _event_shape(json.loads(r["payload"]))) for r in rows]


def _verdict_payload(artifacts: dict[str, Any]) -> dict[str, Any]:
    for payload in artifacts["snapshots"]:
        parsed = json.loads(payload.decode("utf-8"))
        if isinstance(parsed, dict) and "verdict" in parsed:
            return parsed
    raise AssertionError("no verdict snapshot found")


@pytest.fixture(autouse=True)
def clean_slate(request: pytest.FixtureRequest) -> None:
    # NARROW-03: only the compose tests touch the database; CI's unit stage has none.
    if request.node.get_closest_marker("compose") is None:
        return
    run(_sql(WIPE_SQL))


def gate1(job_id: str) -> Any:
    deps = build_offline_deps(dsn=DSN, repo_root=REPO_ROOT)
    return run(run_gate1(job_id=job_id, keywords=KEYWORDS, locale="zh-CN", deps=deps))


@pytest.mark.compose
def test_uninterrupted_run_full_chain() -> None:
    gate1("m2040-solo")
    artifacts = run(_artifacts("m2040-solo"))
    assert artifacts["state"] == "done"
    assert [s[0] for s in artifacts["steps"]] == STEP_ORDER

    phases = []
    for _name, state, ref in artifacts["steps"]:
        assert state == "done"
        checkpoint = deserialize_checkpoint(ref)
        assert isinstance(checkpoint, AnalysisCheckpoint)
        phases.append(checkpoint.phase)
    assert phases == ["retrieve", "judge", "validate", "validate"]

    final = deserialize_checkpoint(artifacts["steps"][-1][2])
    assert final.executed_query_ids, "all planned queries recorded"
    assert final.draft_claim_ids, "draft claims recorded"

    verdict = _verdict_payload(artifacts)
    assert verdict["verdict"] == "B_red_ocean", "3 reachable moderate vendors"
    assert verdict["all_satisfied"] == ["B_red_ocean", "C_opportunity"]
    assert len(verdict["competitors"]) == 3


@pytest.mark.compose
def test_sse_event_sequence_complete() -> None:
    gate1("m2040-sse")
    events = run(_events("m2040-sse"))
    seqs = [seq for seq, _shape in events]
    assert seqs == list(range(1, len(EXPECTED_EVENTS) + 1)), "gapless monotonic seq"
    assert [shape for _seq, shape in events] == EXPECTED_EVENTS


@pytest.mark.compose
def test_kill9_resume_diff_empty_and_events_complete() -> None:
    gate1("m2040-ref")
    reference = run(_artifacts("m2040-ref"))

    run(_sql(WIPE_SQL))
    env = dict(os.environ, FLINT_TEST_DSN=DSN, PYTHONIOENCODING="utf-8")
    proc = subprocess.run(
        [
            sys.executable, "-m", "flint.jobs.gate1",
            "--dsn", DSN,
            "--job-id", "m2040-crash",
            "--keywords", ",".join(KEYWORDS),
            "--locale", "zh-CN",
            "--crash-after", "retrieve",
            "--offline",  # 生产默认已切真实源；CI 恢复冒烟走合成占位（S2-7 零联网）

        ],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=600, check=False,
    )
    assert proc.returncode == 137, f"driver must die hard: {proc.stdout}\n{proc.stderr}"

    steps = run(
        _fetch(
            "SELECT name, snapshot_ref FROM job_steps WHERE job_id = 'm2040-crash' "
            "ORDER BY step_index"
        )
    )
    assert [s["name"] for s in steps] == ["plan", "retrieve"]
    checkpoint = deserialize_checkpoint(steps[-1]["snapshot_ref"])
    assert isinstance(checkpoint, AnalysisCheckpoint)
    assert checkpoint.phase == "judge", "resume enters at judge"
    assert checkpoint.executed_query_ids

    gate1("m2040-crash")
    resumed_steps = run(
        _fetch(
            "SELECT name FROM job_steps WHERE job_id = 'm2040-crash' "
            "ORDER BY step_index"
        )
    )
    names = [s["name"] for s in resumed_steps]
    assert names == STEP_ORDER, "completed steps never rerun"

    resumed = run(_artifacts("m2040-crash"))
    assert resumed == reference, "artifacts diff empty vs uninterrupted run"

    events = run(_events("m2040-crash"))
    seqs = [seq for seq, _shape in events]
    assert seqs == list(range(1, len(EXPECTED_EVENTS) + 1)), "no seq gap across crash"
    assert [shape for _seq, shape in events] == EXPECTED_EVENTS


@pytest.mark.compose
def test_rerun_after_done_is_noop() -> None:
    gate1("m2040-idem")
    first = run(_artifacts("m2040-idem"))
    gate1("m2040-idem")
    assert run(_artifacts("m2040-idem")) == first


def test_no_guess_failed_without_reason_invariant() -> None:
    """Filed from M2-039 review: third invariant branch."""
    record = GenerationRecord(
        record_id="r1", deliverable_id="d1", job_id="j1", prompt_version="v1",
        model="m", params={}, retrieval_snapshot_id="s1", ledger_version=None,
        pricebook_version=None, user_evidence_verdict_optin=False,
        ts=datetime(2026, 7, 28, tzinfo=UTC), cost=0.0,
    )
    with pytest.raises(ValueError, match="explanation"):
        VerdictCallOutcome(
            payload=None, failed=True, failure_reason=None, record=record
        )
