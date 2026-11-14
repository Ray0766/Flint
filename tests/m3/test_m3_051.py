"""M3-051 acceptance tests: revalidation run = full gate1 rerun.

Acceptance (tasks.json M3-051):
  - verdict_shift only from a full gate1_analysis rerun
    (VerdictShift.rerun_analysis_id mandatory; test_verdict_shift_requires_rerun)
  - no heuristic shift path (code-face single-construction-site assertion)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flint.domain.models import VerdictShift
from flint.jobs.gate1 import build_offline_deps
from flint.revalidate.run import build_shift, rerun_verdict

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_verdict_shift_requires_rerun() -> None:
    """E9 点名不变量：无 rerun_analysis_id 不存在 verdict_shift。"""
    with pytest.raises(ValueError, match="rerun_analysis_id"):
        build_shift("C_opportunity", "B_red_ocean", rerun_analysis_id="")
    shift = build_shift("C_opportunity", "B_red_ocean", rerun_analysis_id="job-rerun-1")
    assert isinstance(shift, VerdictShift)
    assert shift.old == "C_opportunity" and shift.new == "B_red_ocean"
    assert shift.rerun_analysis_id == "job-rerun-1"


def test_rerun_produces_shift_only_on_change() -> None:
    deps = build_offline_deps(dsn="postgresql://unused", repo_root=REPO_ROOT)
    outcome = rerun_verdict(
        deps, keywords=["固态电池", "钠离子电池"], locale="zh-CN",
        old_verdict="C_opportunity", rerun_analysis_id="job-rerun-2",
    )
    assert outcome.new_verdict == "B_red_ocean", "offline scenario lands B"
    assert outcome.shift is not None
    assert outcome.shift.rerun_analysis_id == "job-rerun-2"

    same = rerun_verdict(
        deps, keywords=["固态电池", "钠离子电池"], locale="zh-CN",
        old_verdict="B_red_ocean", rerun_analysis_id="job-rerun-3",
    )
    assert same.shift is None, "no change, no shift"
    assert same.new_verdict == "B_red_ocean"


def test_single_construction_site_no_heuristic_path() -> None:
    """代码面断言：全仓 VerdictShift 构造点唯一（系统内只有一套判定逻辑）。"""
    sites = []
    for path in (REPO_ROOT / "flint").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "VerdictShift(" in text:
            sites.append(str(path.relative_to(REPO_ROOT)))
    assert sites == ["flint\\revalidate\\run.py"] or sites == [
        "flint/revalidate/run.py"
    ], sites
