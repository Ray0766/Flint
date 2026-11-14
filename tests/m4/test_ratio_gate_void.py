"""配比 ≤0.15 硬门作废（owner 裁决 @2026-07-30-c）：依外部权威（精确控长度
超当前 SOTA——LIFEBench GPT-4 精确命中 ≤5%~43%；LongWriter 长度变异 31.6%）
判定 ≤0.15 绝对线不现实，改为「经修复环尽力控长度、不作 M4 硬阻塞」。

诚实红线（本测锁）：① 参考线 0.15 NEVER 倒推到自家数（本方 worst 全 >0.15
→ 系依证据作废不现实的线，非调到刚好过）；② tokens↔汉字单位 bug 登记为
独立卫生项，升回硬门前 MUST 先修（不得掩盖）。原始配比数一律不改。
"""
from __future__ import annotations

from pathlib import Path

from eval.real_ratio import RATIO_DEVIATION_LINE, RATIO_HARD_GATE_VOIDED


def test_ratio_line_unchanged_not_reverse_engineered() -> None:
    # 参考线恒 0.15，NEVER 为「过」而倒推到自家数
    assert RATIO_DEVIATION_LINE == 0.15
    # 本方实测 worst（qwen 关环 / gemma 关环 / Claude 开环）全 > 0.15
    # → 是「依证据作废不现实的线」，不是「调到刚好过」
    for our_worst in (0.589, 0.243, 0.206):
        assert our_worst > RATIO_DEVIATION_LINE


def test_ratio_hard_gate_voided_best_effort() -> None:
    # ② 不作 M4 硬阻塞——修复环尽力而为（best-effort）
    assert RATIO_HARD_GATE_VOIDED is True


def test_unit_bug_registered_for_gate_revival() -> None:
    # tokens↔汉字单位 bug 登记为独立卫生项（问题单）；日后若把②升回硬门
    # MUST 先修——本断言防「掩盖」（登记被删则红）
    issue = Path("docs/v0.4-问题单.md").read_text(encoding="utf-8")
    assert "tokens" in issue.lower()
    assert "汉字" in issue
