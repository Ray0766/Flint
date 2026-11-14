"""M2-045 acceptance tests: gold-set eval (precision/recall).

Acceptance (tasks.json M2-045):
  - per-case verdicts compared against gold; precision/recall report
  - below configured lines exits 1; X/Y configurable (owner initial values
    pending, S4 Open Question on file)
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.gate1 import below_lines, main, metrics, run_eval

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"


def load_cases() -> list[dict]:
    return list(json.loads(ASSET.read_text(encoding="utf-8"))["cases"])


def test_gold_set_scores_perfectly_on_rules_engine() -> None:
    results = run_eval(load_cases())
    assert len(results) == 20
    wrong = [r for r in results if not r.verdict_match]
    assert wrong == [], [
        (r.case_id, r.expected_verdict, r.predicted_verdict, r.failed_conditions)
        for r in wrong
    ]
    assert all(r.all_satisfied_match for r in results), [
        (r.case_id, r.expected_all, r.predicted_all)
        for r in results
        if not r.all_satisfied_match
    ]


def test_metrics_report_shape() -> None:
    report = metrics(run_eval(load_cases()))
    assert report["cases"] == 20
    assert report["macro_precision"] == 1.0
    assert report["macro_recall"] == 1.0
    assert report["verdict_accuracy"] == 1.0
    for tier in ("A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"):
        assert report["per_tier"][tier]["tp"] == 5
        assert report["per_tier"][tier]["fp"] == 0


def test_lines_configurable_and_enforced() -> None:
    report = metrics(run_eval(load_cases()))
    assert below_lines(report, None, None) is False, "no lines -> report only"
    assert below_lines(report, 0.9, 0.9) is False

    degraded = dict(report)
    degraded["macro_precision"] = 0.85
    assert below_lines(degraded, 0.9, None) is True, "below X -> fail"
    degraded2 = dict(report)
    degraded2["macro_recall"] = 0.7
    assert below_lines(degraded2, None, 0.9) is True, "below Y -> fail"


def test_cli_exit_codes(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--min-precision", "0.9", "--min-recall", "0.9"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["macro_precision"] == 1.0

    assert main(["--min-precision", "1.1"]) == 1, "unreachable line proves exit path"
