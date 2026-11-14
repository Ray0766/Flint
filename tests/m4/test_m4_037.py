"""M4-037 acceptance tests: trial findings backfill loop.

Acceptance (tasks.json M4-037):
  - trial-discovered pack defects backfilled into generator/validator
    (closed-loop record)
  - after backfill, three packs regenerated and re-run all green
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eval.pack_integrity import run_pack_integrity_eval
from fixtures._generate_trial_specs import generate_all
from harness.spec_trial import run_trials

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
TRIALS = REPO_ROOT / "assets" / "trial_specs"
FINDINGS = (REPO_ROOT / "docs" / "trial-findings.md").read_text(encoding="utf-8")


def test_findings_loop_recorded_and_closed() -> None:
    assert "F-1" in FINDINGS and "single-source" in FINDINGS
    assert "校验器侧" in FINDINGS, "defect side identified"
    assert "closed" in FINDINGS
    assert "open findings：0" in FINDINGS
    assert "append-only" in FINDINGS, "loop stays open for future findings"


def test_backfill_target_actually_carries_the_fix() -> None:
    source = (REPO_ROOT / "eval" / "pack_integrity.py").read_text(
        encoding="utf-8"
    )
    assert "## S5 " in source, "S5-region scoping present in validator"


def test_regenerate_and_rerun_all_green() -> None:
    generate_all()
    for name in ("one", "two", "three"):
        payload = (TRIALS / name / "pack.zip").read_bytes()
        integrity = run_pack_integrity_eval(payload)
        assert integrity.all_ok, (name, [r for r in integrity.rows if not r.ok])
    outcome = run_trials(TRIALS)
    overall = outcome["overall"]
    assert overall.rate == 1.0  # type: ignore[union-attr]
    results = outcome["results"]
    assert all(r.schedulable for r in results)  # type: ignore[union-attr]
