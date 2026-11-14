"""相对参照答作率门槛（owner 裁决 @2026-07-30，选型依据 @2026-07-30-b 更正）：
绝对 0.90 线作废（出处已断，系旧自评考法所定）；相对门槛函数 relative_answer_
gate 保留作**内部参考工具**（不再作免费档选型的过/不过依据）。免费档默认
= qwen3.6:27b，依据**权威中文能力榜**（非内部覆盖门）。原始分数一律不改
（semantic_answer_report 恒 report_only）；GATE_RATIO 恒 0.85，NEVER 倒推。
"""
from __future__ import annotations

from eval.semantic_answers import (
    GATE_RATIO,
    REFERENCE_RATE_UNIFIED_JUDGE,
    RelativeAnswerGate,
    relative_answer_gate,
)


def test_reference_and_ratio_provenance() -> None:
    # 参照=claude-sonnet-5 统一判官 bank v1.0（出处 unified_judge trail 112/258）
    assert REFERENCE_RATE_UNIFIED_JUDGE == 0.434
    assert 0.0 < GATE_RATIO < 1.0


def test_gemma_passes_coverage_gate_but_is_not_the_default() -> None:
    # 事实：gemma4:31b 统一判官 0.395 过覆盖门（0.395≥0.369）。但覆盖门已
    # 降级为**内部参考**，非选型依据——免费档默认改 qwen3.6（权威中文榜依据，
    # owner 裁决 @2026-07-30-b）。此测只锁门函数数学，不代表选型。
    g = relative_answer_gate(0.395)
    assert isinstance(g, RelativeAnswerGate)
    assert g.passed is True
    assert g.required == REFERENCE_RATE_UNIFIED_JUDGE * GATE_RATIO
    assert abs(g.proportion_of_reference - 0.395 / 0.434) < 1e-9


def test_qwen_default_fails_coverage_gate_selection_decoupled() -> None:
    # 反倒推不变量：免费档默认 = qwen3.6:27b（权威中文榜依据），其内部覆盖
    # 统一判官 0.357 **不过**覆盖门（0.357 < 0.369）。选型与覆盖门**解耦**——
    # 默认模型未过门却当选，证依据是权威榜非覆盖门；NEVER 为让 qwen 过门而
    # 调低 GATE_RATIO（倒推=作弊，明令禁止）。
    assert relative_answer_gate(0.357).passed is False


def test_gate_ratio_not_reverse_engineered() -> None:
    # GATE_RATIO 恒 0.85，NEVER 为让免费档默认（qwen 0.357）过门而下调。
    # 若被倒推到 <= 0.357/0.434≈0.822 才能让 qwen 过——此断言当场抓红。
    assert GATE_RATIO == 0.85
    qwen_proportion = 0.357 / 0.434
    assert GATE_RATIO > qwen_proportion  # 门线高于 qwen 占比 → qwen 确不过


def test_absolute_090_is_void() -> None:
    # 参考工具下 0.395 远低于旧 0.90 绝对线，但相对参照下过门
    # → 证 0.90 已作废、绝对线不再沿用（此为门函数事实，非选型判定）
    old_absolute_line = 0.90
    a_free_rate = 0.395
    assert a_free_rate < old_absolute_line  # 旧绝对线下会不达标
    assert relative_answer_gate(a_free_rate).passed is True  # 新相对参照下过


def test_boundary_at_required() -> None:
    req = REFERENCE_RATE_UNIFIED_JUDGE * GATE_RATIO
    assert relative_answer_gate(req).passed is True
    assert relative_answer_gate(req - 0.001).passed is False


def test_zero_reference_no_divzero() -> None:
    g = relative_answer_gate(0.4, reference_rate=0.0)
    assert g.proportion_of_reference == 0.0
    assert g.passed is False
