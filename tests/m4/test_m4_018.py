"""M4-018 acceptance tests: registry eval panorama.

Acceptance (tasks.json M4-018):
  - exists/missing/unavailable/replaced four-state replay panorama
  - 100% pass semantics = all exist AND all locked
"""
from __future__ import annotations

import pytest

from eval.registry import full_pass, run_registry_eval
from flint.registry.batch import BatchReport

pytestmark = pytest.mark.compose


def test_four_state_panorama_all_green() -> None:
    report = run_registry_eval()
    names = [r.name for r in report.rows]
    for state in ("exists", "missing", "unavailable", "replaced"):
        assert state in names, f"state {state} missing from panorama"
    assert report.all_ok, [r for r in report.rows if not r.ok]


def test_full_pass_requires_locks_not_just_rate() -> None:
    clean = BatchReport(
        items=[], total=0, existing=0, missing=[], pass_rate=1.0,
        available=True,
    )
    assert full_pass(clean, []) is True, "empty set trivially locked"

    unavailable = BatchReport(
        items=[], total=1, existing=0, missing=[], pass_rate=1.0,
        available=False,
    )
    assert full_pass(unavailable, []) is False, "unavailable never full-pass"
