"""M3-052 acceptance tests: revalidation report is detect-only.

Acceptance (tasks.json M3-052):
  - run produces a comparison report entity; ledger/deliverable untouched (D6)
  - report carries pre/post verdicts and evidence references
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from flint.domain.models import RevalidationReport
from flint.jobs.gate1 import build_offline_deps
from flint.revalidate.report import build_report

REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def test_report_detect_only_with_shift() -> None:
    deps = build_offline_deps(dsn="postgresql://unused", repo_root=REPO_ROOT)
    report = build_report(
        deps=deps, report_id="rvr-1", deliverable_id="d-1",
        keywords=["固态电池", "钠离子电池"], locale="zh-CN",
        old_verdict="C_opportunity", rerun_analysis_id="job-r1",
        known_paper_ids=set(), known_competitor_names=set(),
        old_heat={"total": 10.0}, new_heat={"total": 14.0},
        trigger="scheduled", generated_at=NOW,
    )
    assert isinstance(report, RevalidationReport)
    assert report.accepted is None, "detect-only: nothing applied yet"
    assert report.verdict_shift is not None
    assert report.verdict_shift.old == "C_opportunity"
    assert report.verdict_shift.new == "B_red_ocean"
    assert report.verdict_shift.rerun_analysis_id == "job-r1"
    assert report.new_competitors, "offline scenario surfaces three vendors"
    assert report.heat_shift == {"total": {"old": 10.0, "new": 14.0}}
    assert report.trigger == "scheduled"


def test_known_entities_not_reported_as_new() -> None:
    deps = build_offline_deps(dsn="postgresql://unused", repo_root=REPO_ROOT)
    first = build_report(
        deps=deps, report_id="rvr-2", deliverable_id="d-1",
        keywords=["固态电池"], locale="zh-CN",
        old_verdict="B_red_ocean", rerun_analysis_id="job-r2",
        known_paper_ids=set(), known_competitor_names=set(),
        old_heat={}, new_heat={}, trigger="user", generated_at=NOW,
    )
    second = build_report(
        deps=deps, report_id="rvr-3", deliverable_id="d-1",
        keywords=["固态电池"], locale="zh-CN",
        old_verdict="B_red_ocean", rerun_analysis_id="job-r3",
        known_paper_ids=set(first.new_papers),
        known_competitor_names=set(first.new_competitors),
        old_heat={}, new_heat={}, trigger="user", generated_at=NOW,
    )
    assert second.new_papers == [], "already-known papers filtered"
    assert second.new_competitors == [], "already-known competitors filtered"
    assert second.verdict_shift is None
