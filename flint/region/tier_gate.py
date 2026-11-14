"""REGION-03：unknown-tier 判定前置门（B2 后半）。

仅 unknown 权威度的证据 NEVER 满足判 A/B 的必要条件——
这是一个独立的布尔前置门，在评分公式之前拦截。

## 为什么是前置门而不是评分权重

评分权重是连续量：把 unknown 的权重调低只会让总分低一点，
遇上数量多的 unknown 证据还是能凑出高分通过 A/B 门槛——
那等于让「不知道权威性」的证据靠堆数量冒充高质量。
前置门是布尔量：没有一条非 unknown 证据就直接挡住，堆数量无效。
权重待 K3 调参，本门与它无关。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

_GATED_VERDICTS = frozenset({"A", "B"})


@dataclass(frozen=True)
class TierGateResult:
    """前置门结果。只有 blocked/reason，NEVER 携带评分或权重（K3 待调参）。"""

    blocked: bool
    reason: str


def check_tier_gate(
    *, tiers: Sequence[str], proposed_verdict: str
) -> TierGateResult:
    """检查 authority_tier 构成是否满足提议判定的必要条件。

    - 提议判定为 A 或 B 时：至少一条证据的 tier 不是 unknown 才放行。
    - 提议判定为 C 或 D 时：无条件放行（unknown 只阻断 A/B）。
    """
    if proposed_verdict not in _GATED_VERDICTS:
        return TierGateResult(blocked=False, reason="")

    has_known = any(t != "unknown" for t in tiers)
    if has_known:
        return TierGateResult(blocked=False, reason="")

    return TierGateResult(
        blocked=True,
        reason=(
            f"判 {proposed_verdict} 被 unknown-tier 前置门拒绝: "
            "全部证据的 authority_tier 均为 unknown, "
            "NEVER 满足判 A/B 的必要条件 [B2]"
        ),
    )
