"""M4-044 acceptance tests: M4 exit report (signed-closure honesty).

Acceptance (tasks.json M4-044):
  - §7 M4 row checked with evidence; Z ruling recorded (awaiting owner)
  - MUST: production-caliber verification section vs M3 exit carried
    conditions, closed — exit invalid until closed

状态迁移（owner 裁决 @2026-07-30 系列 → 监管口头授权签字 @2026-07-30）：
草案 →（①②携带条件依外部权威证据了结）→ **owner 经监管口头授权签字、M4 关闭**。
本测把「待签断言」替换为「已签+关门断言」，但**加固而非放松**诚实不变量：
①② 由原始绝对线**作废**（非达成）、签字确认接受**真实经过**（坏消息齐全）、
NEVER「生产就绪」宣称、NEVER 假装达成原始线。历史（v3 数字、旧「未关门」
叙述）append-only 保留仍可断言在场；签字系口头授权、来源如实标注（S2-10）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = (REPO_ROOT / "docs" / "M4-出口报告.md").read_text(encoding="utf-8")


def test_production_section_present_conditions_closed_by_void() -> None:
    assert "生产口径验证" in DOC
    # ①② 携带条件已了结——方式 = 原始绝对线依外部权威证据判定不现实而作废
    # （NON-achievement）；签字文件必含真实经过
    assert "依外部权威证据" in DOC and "作废" in DOC
    assert "NEVER 假装达成" in DOC, "signature doc: never pretend lines met"
    # owner 原始硬性要求原样保留（历史）：该条未过则 M4 出口不成立
    assert "M4 出口不成立" in DOC


def test_v3_measured_results_stated_with_numbers() -> None:
    """Ruling 1-1: the four measured numbers MUST appear with verdicts."""
    for number in ("0.442", "0.523", "0.212", "0.233"):
        assert number in DOC, f"measured value {number} missing from report"
    assert "双线均不达标" in DOC
    assert "assets/prod_caliber/qwen3_30b.json" in DOC, "trail pointer"
    assert "历史批次" in DOC and "不作为产品指标" in DOC
    assert "保留不删" in DOC, "reproducibility: kept, never deleted"
    assert "真实运行待 owner 四供给" not in DOC, (
        "stale claim removed: the real run HAS happened"
    )


def test_signed_and_closed_no_production_ready_claim() -> None:
    """签字已落（监管口头授权）+ M4 关闭；但坏消息与诚实红线加固不放松。"""
    assert "签字栏" in DOC
    # 签字已记录：来源如实（口头授权，非 owner 亲键）+ 日期 + S2-10 确认
    assert "口头授权" in DOC, "signature provenance stated truthfully"
    assert "2026-07-30" in DOC and "owner" in DOC and "签字" in DOC
    assert "S2-10" in DOC, "human-confirm touchpoint attributed"
    # M4 关闭已宣告（里程碑收口）
    assert "M4 关闭" in DOC or "M4 里程碑关闭" in DOC
    # 已不再宣称「待签/唯一剩余关门动作」——签字这一动作已完成
    assert "待签——唯一剩余关门动作" not in DOC, (
        "pending-signature claim must be gone after signing"
    )
    # 诚实：免费档 best-effort（非绝对质量保证）；坏消息在场
    assert "best-effort" in DOC
    # 签字确认接受真实经过——坏消息四项齐全
    for bad_news in ("原始线", "单位 bug", "未修"):
        assert bad_news in DOC, f"bad news '{bad_news}' must remain present"
    banned_claim = re.compile(r"(?<!「)生产就绪(?!」)")
    assert not banned_claim.search(DOC), (
        "「生产就绪」only as quoted ban wording, never as a claim"
    )


def test_section7_rows_with_z_awaiting_owner() -> None:
    for row in ("DAG 校验 0 例外", "registry 校验 100%", "一次通过率对 Z",
                "导出门禁三与"):
        assert row in DOC
    assert "Z 线初值待 owner 裁决" in DOC


def test_owner_checklist_converged() -> None:
    assert "Q-004 四供给" in DOC
    assert "NEVER 会话内传递" in DOC
    assert "S2-10" in DOC
    assert "出口签字" in DOC
