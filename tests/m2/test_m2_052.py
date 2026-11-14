"""M2-052 acceptance tests: M2 exit report.

Acceptance (tasks.json M2-052):
  - section-7 M2 row checked item by item: precision/recall/consistency/
    missed-rate evidence on file
  - X/Y line values decided by owner and recorded (human review node)
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.alignment import run_alignment_eval
from eval.gate1 import metrics, run_eval
from eval.missed_d import missed_d_report

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "docs" / "M2-出口报告.md"
ASSET = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"


def report_text() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_report_exists_with_required_sections() -> None:
    text = report_text()
    for section in (
        "§7 M2 行逐条勾选", "M2 全量交付对账", "X/Y 线值裁决", "遗留与挂账",
    ):
        assert section in text, f"missing section: {section}"


def test_evidence_numbers_match_live_eval() -> None:
    """报告里的四项实测数字必须与评测面即时复跑一致（证据不许过期）。"""
    cases = json.loads(ASSET.read_text(encoding="utf-8"))["cases"]
    results = run_eval(cases)
    report = metrics(results)
    alignment = run_alignment_eval(cases)
    missed = missed_d_report(results)

    assert report["macro_precision"] == 1.0
    assert report["macro_recall"] == 1.0
    assert alignment["consistency"] == 1.0
    assert missed["missed_rate"] == 0.0

    text = report_text()
    assert "macro precision = **1.0**" in text
    assert "macro recall = **1.0**" in text
    assert "consistency = **1.0**" in text
    assert "missed_rate = **0.0**" in text


def test_all_four_rows_checked() -> None:
    assert report_text().count("✅") == 4, "all four section-7 rows checked"


def test_owner_xy_decision_recorded() -> None:
    text = report_text()
    assert "待裁决" not in text, "human review node: decision must be recorded"
    assert "裁决：X = " in text and "Y = " in text
    assert "owner Ray" in text, "decision attributed to the owner"
