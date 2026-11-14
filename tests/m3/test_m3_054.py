"""M3-054 acceptance tests: conflict -> whole-job rerun.

Acceptance (tasks.json M3-054):
  - accept hitting LedgerVersionConflict -> whole job invalidated and rerun
    (audit-4 third path)
  - rerun rebuilds a fresh report on the new version (old report marked
    superseded)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import RevalidationReport
from flint.jobs.gate1 import build_offline_deps
from flint.ledger.store import PgLedgerStore
from flint.revalidate.retry import accept_with_whole_job_rerun

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM facts WHERE ledger_id IN "
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3054-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3054-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def store() -> PgLedgerStore:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3054-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def report(report_id: str) -> RevalidationReport:
    return RevalidationReport(
        report_id=report_id, deliverable_id="d-1", new_papers=[],
        new_competitors=[], heat_shift={}, verdict_shift=None,
        trigger="scheduled", generated_at=NOW, accepted=None,
    )


def test_conflict_invalidates_and_reruns_whole_job() -> None:
    s = store()
    run(s.derive("m3054-p1", 0, "initial", {"add": []}))
    run(s.derive("m3054-p1", 1, "inject_evidence", {"add": []}))  # 并发前进到 v2

    deps = build_offline_deps(dsn=DSN, repo_root=REPO_ROOT)
    outcome = run(accept_with_whole_job_rerun(
        store=s, deps=deps, project_id="m3054-p1",
        stale_report=report("rvr-old"), stale_expected_version=1,
        keywords=["固态电池"], locale="zh-CN", old_verdict="B_red_ocean",
        rerun_report_id="rvr-new", rerun_analysis_id="job-rerun-9",
        changes={"add": []}, blocks=[], now=NOW,
    ))
    assert outcome.reran is True, "conflict path taken"
    assert outcome.superseded_report_id == "rvr-old"
    assert outcome.fresh_report.report_id == "rvr-new"
    assert outcome.fresh_report.accepted is None, (
        "fresh report is detect-only again: user re-accepts on the new state"
    )
    assert outcome.applied is None, "no silent apply after conflict"


def test_no_conflict_applies_directly() -> None:
    s = store()
    run(s.derive("m3054-p2", 0, "initial", {"add": []}))
    deps = build_offline_deps(dsn=DSN, repo_root=REPO_ROOT)
    outcome = run(accept_with_whole_job_rerun(
        store=s, deps=deps, project_id="m3054-p2",
        stale_report=report("rvr-1"), stale_expected_version=1,
        keywords=["固态电池"], locale="zh-CN", old_verdict="B_red_ocean",
        rerun_report_id="rvr-unused", rerun_analysis_id="job-x",
        changes={"add": []}, blocks=[], now=NOW,
    ))
    assert outcome.reran is False
    assert outcome.applied is not None
    assert outcome.applied.ledger.version == 2
