"""M4-022 acceptance tests: vibe quality gate.

Acceptance (tasks.json M4-022):
  - verify coverage = 100% hard gate (any ai card without verify_cmd = zero
    tolerance)
  - context over-budget task count = 0 (refs estimate <= 40k tokens)
"""
from __future__ import annotations

from flint.dag.quality_gate import (
    CONTEXT_BUDGET_TOKENS,
    estimate_context_tokens,
    vibe_quality_gate,
)
from flint.domain.models import TaskSpec


def task(task_id: str, verify_cmd: str | None = "pytest x",
         context_refs: list[str] | None = None) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=[], outputs=["x"],
        acceptance=["a"], depends_on=[], milestone="M1",
        estimate_cycles=1, oneshot=True, verify_cmd=verify_cmd,
        context_refs=context_refs if context_refs is not None else ["S3#选型"],
        review_gate=False,
    )


def test_clean_pack_passes() -> None:
    report = vibe_quality_gate([task("T-1"), task("T-2")])
    assert report.verify_coverage == 1.0
    assert report.over_budget_tasks == []
    assert report.passed is True


def test_missing_verify_zero_tolerance() -> None:
    report = vibe_quality_gate([task("T-1"), task("T-2", verify_cmd=None)])
    assert report.verify_coverage == 0.5
    assert report.passed is False
    assert any("T-2" in v for v in report.violations)


def test_context_budget_estimation_and_gate() -> None:
    modest = estimate_context_tokens(["S3#选型", "S2"])
    assert 0 < modest < CONTEXT_BUDGET_TOKENS

    heavy_refs = [f"技术方案-v1.1.md#E{i}" for i in range(1, 13)] * 4
    report = vibe_quality_gate([task("T-heavy", context_refs=heavy_refs)])
    assert report.over_budget_tasks == ["T-heavy"]
    assert report.passed is False


def test_empty_refs_flagged() -> None:
    report = vibe_quality_gate([task("T-1", context_refs=[])])
    assert any("context_refs" in v for v in report.violations)
    assert report.passed is False
