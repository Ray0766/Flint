"""M4-017 acceptance tests: build-time early validation.

Acceptance (tasks.json M4-017):
  - S3/S5 outputs validated at build time inside the proposal job
    (validators moved one stage earlier, E5)
  - failure -> per-chapter GapHint, error surfaces one stage early
"""
from __future__ import annotations

import pytest

from flint.domain.models import TaskSpec
from flint.registry.batch import BatchItem, BatchReport
from flint.spec.early_validate import early_validate

pytestmark = pytest.mark.compose


def ai_card(task_id: str, cycles: float, deps: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=["repo"], outputs=["mod"],
        acceptance=["a"], depends_on=deps, milestone="M1",
        estimate_days=None, estimate_cycles=cycles, oneshot=True,
        verify_cmd="pytest x", context_refs=["S3"], review_gate=False,
    )


def clean_report() -> BatchReport:
    return BatchReport(
        items=[], total=1, existing=1, missing=[], pass_rate=1.0,
        available=True,
    )


def down_report() -> BatchReport:
    item = BatchItem(
        package="httpx", ecosystem="pypi", state="unavailable",
        status=None, detail="503",
    )
    return BatchReport(
        items=[item], total=1, existing=0, missing=[], pass_rate=0.0,
        available=False,
    )


def test_clean_build_passes_both_chapters() -> None:
    result = early_validate([ai_card("T-1", 1, [])], clean_report())
    assert result.ok is True
    assert result.s3_gap is None and result.s5_gap is None
    assert result.violations == []


def test_s5_shape_failure_gets_chapter_gaphint() -> None:
    result = early_validate([ai_card("T-1", 3.0, ["ghost"])], clean_report())
    assert result.ok is False
    assert result.s5_gap is not None and "S5" in result.s5_gap.missing_what
    assert result.s3_gap is None, "chapters judged independently"
    assert all(v.startswith("S5: ") for v in result.violations)


def test_s3_registry_failure_gets_chapter_gaphint() -> None:
    result = early_validate([ai_card("T-1", 1, [])], down_report())
    assert result.ok is False
    assert result.s3_gap is not None and "S3" in result.s3_gap.missing_what
    assert result.s5_gap is None
    assert all(v.startswith("S3: ") for v in result.violations)


def test_both_failures_surface_together() -> None:
    result = early_validate([ai_card("T-1", 3.0, [])], down_report())
    assert result.s3_gap is not None and result.s5_gap is not None
    assert any(v.startswith("S3: ") for v in result.violations)
    assert any(v.startswith("S5: ") for v in result.violations), (
        "neither chapter masks the other"
    )
