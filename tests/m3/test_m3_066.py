"""M3-066 acceptance tests: M3 exit report.

Acceptance (tasks.json M3-066):
  - section-7 M3 row checked item by item, evidence bound to live reruns
  - owner signature recorded (human review node)
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.doc_metrics import (
    check_answer_report,
    ratio_deviation_report,
    traceability_report,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "docs" / "M3-出口报告.md"
GOLDDOCS = REPO_ROOT / "assets" / "golddocs" / "golddocs.json"


def report_text() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_report_sections_present() -> None:
    text = report_text()
    for section in ("§7 M3 行逐条勾选", "M3 全量交付对账", "口径声明", "结论"):
        assert section in text


def test_evidence_bound_to_live_metrics() -> None:
    samples = json.loads(GOLDDOCS.read_text(encoding="utf-8"))["samples"]
    traceability = traceability_report(samples)
    answers = check_answer_report(samples)
    assert traceability["rate"] == 1.0
    assert answers["rate"] >= 0.9
    for template_id in ("generic", "vibe_pack"):
        assert ratio_deviation_report(template_id)["within_line"] is True

    text = report_text()
    assert "rate = **1.0**" in text
    assert "max 相对偏差 = **0.0**" in text


def test_conditional_exit_honest_marking() -> None:
    """owner 裁决（2026-07-30）：仅追溯率为真实测量 ✅；check/配比两行
    ⚠️ 结构/度量器达标·生产口径待验——出口表格不许出现三个裸 ✅。"""
    text = report_text()
    assert text.count("✅") == 1, "only traceability earns the plain check"
    assert "⚠️ 结构达标·生产口径待验（补充条件）" in text
    assert "⚠️ 度量器达标·生产口径待验（补充条件）" in text
    assert "非独立测量" in text and "构造恒等" in text, (
        "self-certified nature stated in the evidence column"
    )


def test_supplementary_exit_condition_three_items() -> None:
    text = report_text()
    assert "四·补充出口条件" in text
    assert "语义作答率 ≥90%" in text, "redemption criterion 1"
    assert "相对偏差 ≤±15%" in text, "redemption criterion 2"
    assert "关门点" in text and "M4 出口报告" in text, "single closing site"
    assert "不阻断" in text, "M4 dependency surface unaffected"
    assert "生产就绪" in text, "no production-ready claim before redemption"


def test_owner_conditional_signature_recorded() -> None:
    text = report_text()
    assert "待 owner" not in text
    assert "有条件签署" in text and "owner Ray" in text
    assert "结构里程碑" in text, "exit scoped as structural milestone"
