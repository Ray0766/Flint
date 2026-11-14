"""M2-047 acceptance tests: missed-D rate (<=10%).

Acceptance (tasks.json M2-047):
  - report of cases with retrievable evidence judged D anyway
  - >10% exits 1 (PDD 0.3.1 section-7 M2 line)
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from eval.gate1 import run_eval
from eval.missed_d import MAX_MISSED_RATE, main, missed_d_report

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"


def load_results() -> list:
    cases = json.loads(ASSET.read_text(encoding="utf-8"))["cases"]
    return run_eval(cases)


def test_line_is_10_percent() -> None:
    assert MAX_MISSED_RATE == 0.10


def test_perfect_run_zero_missed() -> None:
    report = missed_d_report(load_results())
    assert report["retrievable_cases"] == 15, "15 non-D gold cases"
    assert report["missed_rate"] == 0.0
    assert report["missed_d"] == []


def test_tampered_predictions_trip_the_line() -> None:
    results = load_results()
    tampered = []
    flipped = 0
    for result in results:
        if result.expected_verdict != "D_insufficient" and flipped < 3:
            tampered.append(replace(result, predicted_verdict="D_insufficient"))
            flipped += 1
        else:
            tampered.append(result)
    report = missed_d_report(tampered)
    assert report["missed_rate"] == 3 / 15
    assert report["missed_rate"] > MAX_MISSED_RATE
    assert len(report["missed_d"]) == 3


def test_cli_exit_codes(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["missed_rate"] == 0.0
    assert main(["--max", "-0.1"]) == 1, "impossible line proves exit path"
