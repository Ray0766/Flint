"""C 档规则（M2-036，四必要条件+否定条件；审1）。

四必要条件（任一不满足 → 按顺序落到下一档）：
1. refute 检索已执行且 hit_rate >= θ_rel；
2. 竞品扫描覆盖达标（M2-033 判定）；
3. >=1 条 stage="verdict" 对齐通过的支持证据——支持证据缺席是缺口
   （不降 D）；已提交的关键证据对齐未过才 demote_to_d（绝不带病判定）；
4. 否定条件：无 strength ∈ {strong, unknown} 的竞品——unknown 阻断 C
   是刻意保守（判错 C 代价 > 判错 A/D），NEVER 当 weak 放行。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from flint.align.stage1 import DEFAULT_K_CAP, LLMCitationAligner, align_key_evidence
from flint.competitor.coverage import CoverageResult
from flint.domain.models import Competitor, Doc
from flint.retrieval.relevance import THETA_REL

FailedCondition = Literal[
    "refute_not_executed",
    "refute_hit_rate_below_theta",
    "coverage_not_met",
    "no_aligned_support",
    "strong_or_unknown_competitor",
]


@dataclass
class RuleCResult:
    satisfied: bool
    failed_conditions: list[FailedCondition] = field(default_factory=list)
    demote_to_d: bool = False
    support_doc_ids: list[str] = field(default_factory=list)
    blocking_competitors: list[str] = field(default_factory=list)


def evaluate_rule_c(
    aligner: LLMCitationAligner,
    support_pairs: list[tuple[str, Doc]],
    refute_executed: bool,
    refute_hit_rate: float,
    coverage: CoverageResult,
    competitors: list[Competitor],
    theta: float = THETA_REL,
    k_cap: int = DEFAULT_K_CAP,
) -> RuleCResult:
    result = RuleCResult(satisfied=False)
    if not refute_executed:
        result.failed_conditions.append("refute_not_executed")
    elif refute_hit_rate < theta:
        result.failed_conditions.append("refute_hit_rate_below_theta")
    if not coverage.covered:
        result.failed_conditions.append("coverage_not_met")
    if not support_pairs:
        result.failed_conditions.append("no_aligned_support")
    else:
        alignment = align_key_evidence(aligner, support_pairs, k_cap)
        if alignment.demote_to_d:
            result.demote_to_d = True
            result.failed_conditions.append("no_aligned_support")
        else:
            result.support_doc_ids = [
                doc_id
                for _claim, doc_id, verdict in alignment.checked
                if verdict == "supports"
            ]
    blocking = [c.name for c in competitors if c.strength in ("strong", "unknown")]
    if blocking:
        result.blocking_competitors = blocking
        result.failed_conditions.append("strong_or_unknown_competitor")
    result.satisfied = not result.failed_conditions
    return result
