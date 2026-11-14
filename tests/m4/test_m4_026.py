"""M4-026 acceptance tests: dag eval panorama.

Acceptance (tasks.json M4-026):
  - five constructed violation classes (cycle/orphan/dangling/dual-unit/
    coverage) all detected
  - clean DAG zero false positives
"""
from __future__ import annotations

import pytest

from eval.dag import build_cases, run_dag_eval

pytestmark = pytest.mark.compose


def test_five_violation_classes_all_detected() -> None:
    report = run_dag_eval()
    assert report.expected_detections == 5
    assert report.detected == 5, [
        r for r in report.rows if r.expect_fragment and not r.hit
    ]
    names = {r.name for r in report.rows if r.expect_fragment}
    assert names == {
        "cycle", "orphan", "dangling-dep", "dual-unit-leak",
        "verify-coverage-gap",
    }


def test_clean_dag_zero_false_positives() -> None:
    report = run_dag_eval()
    clean = next(r for r in report.rows if r.expect_fragment is None)
    assert clean.hit and clean.error_count == 0
    assert report.false_positives == 0


def test_expectation_carried_by_construction() -> None:
    cases = build_cases()
    assert len(cases) == 6
    for case in cases:
        if case.expect_fragment is not None:
            assert case.expect_fragment, "violation cases carry a fragment"
