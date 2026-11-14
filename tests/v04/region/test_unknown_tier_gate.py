"""REGION-03 验收：unknown-tier 判定前置门。

acceptance:
  ① 仅 unknown 证据支撑时判 A/B 被门拒（独立于评分公式）
  ② 门为 verdict 前置检查，评分权重不动（K3）

B2 后半: unknown 权威度的证据 NEVER 满足判 A/B 的必要条件。
这是一个独立的布尔前置门，在评分公式之前拦截，评分权重本身不动（K3 待调参）。
"""
from __future__ import annotations

from flint.region.tier_gate import check_tier_gate

# ── ① 仅 unknown 时门拒 ──────────────────────────────────────

def test_all_unknown_blocks_verdict_a() -> None:
    """全部 unknown → 判 A 被拒。"""
    result = check_tier_gate(
        tiers=["unknown", "unknown", "unknown"],
        proposed_verdict="A",
    )
    assert result.blocked is True
    assert "unknown" in result.reason.lower()


def test_all_unknown_blocks_verdict_b() -> None:
    """全部 unknown → 判 B 被拒。"""
    result = check_tier_gate(
        tiers=["unknown", "unknown"],
        proposed_verdict="B",
    )
    assert result.blocked is True


def test_all_unknown_allows_verdict_c() -> None:
    """C 和 D 不受此门约束——unknown 只阻断 A/B。"""
    result = check_tier_gate(
        tiers=["unknown"],
        proposed_verdict="C",
    )
    assert result.blocked is False


def test_all_unknown_allows_verdict_d() -> None:
    result = check_tier_gate(
        tiers=["unknown", "unknown"],
        proposed_verdict="D",
    )
    assert result.blocked is False


def test_mixed_tiers_with_one_known_allows_a() -> None:
    """至少一条非 unknown 证据 → A 放行。"""
    result = check_tier_gate(
        tiers=["unknown", "mainstream", "unknown"],
        proposed_verdict="A",
    )
    assert result.blocked is False


def test_mixed_tiers_with_one_known_allows_b() -> None:
    result = check_tier_gate(
        tiers=["unknown", "community"],
        proposed_verdict="B",
    )
    assert result.blocked is False


def test_all_known_tiers_allow_a() -> None:
    result = check_tier_gate(
        tiers=["official", "mainstream", "industry"],
        proposed_verdict="A",
    )
    assert result.blocked is False


# ── ② 门与评分独立 ───────────────────────────────────────────

def test_gate_does_not_carry_score_or_weight() -> None:
    """门只返回 blocked/reason，NEVER 携带评分或权重——评分权重不动（K3）。"""
    result = check_tier_gate(tiers=["unknown"], proposed_verdict="A")
    assert not hasattr(result, "score"), "门 NEVER 携带评分"
    assert not hasattr(result, "weight"), "门 NEVER 携带权重"


def test_gate_module_references_no_scoring_symbol() -> None:
    """独立性要在**源码层**成立，不只是结果对象上没有 score 属性。

    只断言 `not hasattr(result, "score")` 是不够的：门内部完全可以读评分、
    按分数决定 blocked，而结果对象照样干净。K3 未决（authority 轴权重待 owner），
    门 NEVER 碰评分——这条由源码扫描守着。
    （本条为并发会话产出被本会话复核时补强，见 docs/trace/REGION-03.md）
    """
    import inspect

    import flint.region.tier_gate as gate_module

    source = inspect.getsource(gate_module)
    for forbidden in ("EvidenceScore", "strength", "axis", ".score", "weight"):
        assert forbidden not in source, (
            f"门里出现了评分相关符号 {forbidden!r}：门在评分之前，两者 NEVER 互相干涉")


def test_gate_is_independent_of_evidence_count() -> None:
    """门看的是 tier 构成，不是证据数量——100 条 unknown 也过不了。"""
    result = check_tier_gate(
        tiers=["unknown"] * 100,
        proposed_verdict="A",
    )
    assert result.blocked is True


# ── 边界 ─────────────────────────────────────────────────────

def test_empty_tiers_blocks_a_and_b() -> None:
    """没有任何证据支撑 → 更不应该判 A/B。"""
    assert check_tier_gate(tiers=[], proposed_verdict="A").blocked is True
    assert check_tier_gate(tiers=[], proposed_verdict="B").blocked is True


def test_empty_tiers_allows_c_and_d() -> None:
    assert check_tier_gate(tiers=[], proposed_verdict="C").blocked is False
    assert check_tier_gate(tiers=[], proposed_verdict="D").blocked is False
