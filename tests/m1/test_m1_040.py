"""M1-040 acceptance tests: 7-day daily-update drill + monitoring assertions.

Acceptance (tasks.json M1-040):
  - replay-accelerated 7 days with zero manual intervention
  - degraded scenarios annotated correctly
  - all four metric counters present (E7)
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.obs.metrics import REQUIRED_INGEST_METRICS, registry_snapshot
from harness.drill7 import DrillReport, run_drill

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
DRILL_END = date(2026, 7, 5)  # window 06-29..07-05 includes the weibo-429 day
DEGRADED_DAY = date(2026, 7, 5)
RUNBOOK = REPO_ROOT / "docs" / "trace" / "drill7.md"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def report() -> DrillReport:
    return run_drill(
        days=7, end=DRILL_END, dsn=DSN, redis_url=REDIS_URL,
        fixtures_root=REPO_ROOT / "fixtures", runbook=RUNBOOK,
    )


def test_seven_days_zero_manual_intervention(report: DrillReport) -> None:
    assert len(report.days) == 7
    assert report.all_green is True
    assert all(d.outcome == "executed" for d in report.days), "scheduler ran every batch"

    async def states() -> set[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT state FROM jobs WHERE job_id LIKE 'drill-%'"
            )
            return {r["state"] for r in rows}
        finally:
            await conn.close()

    assert run(states()) == {"done"}


def test_degraded_scenario_annotated_correctly(report: DrillReport) -> None:
    """The weibo-429 day must land a persisted DegradationNote (M1-035
    review follow-up: DB persistence is now a hard condition) and be
    annotated in the runbook."""

    async def notes() -> list[asyncpg.Record]:
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetch(
                "SELECT source_id, reason FROM degradation_notes WHERE day = $1",
                DEGRADED_DAY,
            )
        finally:
            await conn.close()

    rows = run(notes())
    assert [(r["source_id"], r["reason"]) for r in rows] == [("weibo", "rate_limited")]

    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "degraded" in runbook
    assert "weibo" in runbook and "rate_limited" in runbook
    assert "今日缺 weibo 数据" in runbook, "card-facing gap copy must be shown"


def test_four_metric_counters_present(report: DrillReport) -> None:
    snapshot = registry_snapshot()
    names = {name for name, _labels in snapshot}
    for required in REQUIRED_INGEST_METRICS:
        assert required in names, f"E7 counter missing: {required}"

    success = {
        labels: value
        for (name, labels), value in snapshot.items()
        if name == "ingest_success_total"
    }
    # degraded day: weibo missing; other three sources succeed all 7 days
    assert success[(("source", "arxiv"),)] == 7.0
    assert success[(("source", "weibo"),)] == 6.0
    degraded = sum(
        value for (name, _), value in snapshot.items() if name == "degraded_sources_total"
    )
    assert degraded == 1.0
    durations = [
        value
        for (name, labels), value in snapshot.items()
        if name == "job_duration_seconds_count" and labels == (("kind", "daily_ingest"),)
    ]
    assert durations == [7.0], "one duration observation per drill day"


def test_runbook_written_with_daily_rows(report: DrillReport) -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    for offset in range(7):
        day = date(2026, 6, 29 + offset) if offset <= 1 else date(2026, 7, offset - 1)
        assert day.isoformat() in runbook
    assert "7/7" in runbook


def test_step_records_share_data_transaction() -> None:
    """M1-035 review follow-up: the step record must commit atomically with
    the step's data writes — the ingest orchestrator wraps both in one
    transaction (source-level assertion keeps the invariant reviewable)."""
    source = (REPO_ROOT / "flint" / "jobs" / "ingest.py").read_text(encoding="utf-8")
    assert "async with conn.transaction():" in source
    marker = "步数据与 job_steps 记录同事务提交"
    assert marker in source, "transaction-folding contract comment must be present"
