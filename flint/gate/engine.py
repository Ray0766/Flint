"""判定顺序引擎（M2-038；审2 顺序写死 A>B>C>D + all_satisfied）。

- 顺序 NEVER 参数化：VERDICT_ORDER 常量写死；四类条件不互斥，展示最高
  优先者，all_satisfied 记录全部命中档位（A+B 同时满足 → 展示 A、可展开 B，
  不记录会丢信息且无法复盘判定分歧）。
- 任一 stage="verdict" 对齐 demote（rule A/C 上报）→ 全档位作废、落 D
  （绝不带病判定）。
- 落 D MUST 携带非空 GapHint 清单（M2-037 派生）；空清单在此抛错。
- constraints_checked 摊平三规则的评估痕迹，供 VerdictShift 重跑复盘。
"""
from __future__ import annotations

from typing import Final

from flint.domain.models import JSON, Competitor, GapHint, Verdict, VerdictResult
from flint.gate.rule_a import RuleAResult
from flint.gate.rule_b import RuleBResult
from flint.gate.rule_c import RuleCResult

VERDICT_ORDER: Final[tuple[Verdict, ...]] = (
    "A_infeasible",
    "B_red_ocean",
    "C_opportunity",
    "D_insufficient",
)


def decide(
    rule_a: RuleAResult,
    rule_b: RuleBResult,
    rule_c: RuleCResult,
    gaps: list[GapHint],
    competitors: list[Competitor],
    rationale_fact_ids: list[str] | None = None,
) -> VerdictResult:
    demoted = rule_a.demote_to_d or rule_c.demote_to_d
    satisfied_by_tier: dict[Verdict, bool] = {
        "A_infeasible": rule_a.satisfied and not demoted,
        "B_red_ocean": rule_b.satisfied and not demoted,
        "C_opportunity": rule_c.satisfied and not demoted,
        "D_insufficient": False,
    }
    all_satisfied: list[Verdict] = [v for v in VERDICT_ORDER if satisfied_by_tier[v]]
    if not all_satisfied:
        all_satisfied = ["D_insufficient"]
    verdict: Verdict = all_satisfied[0]
    if verdict == "D_insufficient" and not gaps:
        raise ValueError("verdict D requires a non-empty gap list (audit 8)")
    if verdict == "A_infeasible":
        key_citation_ids = list(rule_a.refute_doc_ids)
    elif verdict == "C_opportunity":
        key_citation_ids = list(rule_c.support_doc_ids)
    else:
        key_citation_ids = []
    constraints_checked: JSON = {
        "order": list(VERDICT_ORDER),
        "demoted_by_alignment": demoted,
        "rule_a": {
            "satisfied": rule_a.satisfied,
            "used_user_evidence_only": rule_a.used_user_evidence_only,
            "blocked_pending_optin": rule_a.blocked_pending_optin,
        },
        "rule_b": {
            "satisfied": rule_b.satisfied,
            "by_count": rule_b.by_count,
            "by_strength": rule_b.by_strength,
            "reachable_count": rule_b.reachable_count,
            "strong_names": list(rule_b.strong_names),
        },
        "rule_c": {
            "satisfied": rule_c.satisfied,
            "failed_conditions": list(rule_c.failed_conditions),
            "blocking_competitors": list(rule_c.blocking_competitors),
        },
        "gap_count": len(gaps),
    }
    return VerdictResult(
        verdict=verdict,
        all_satisfied=all_satisfied,
        key_citation_ids=key_citation_ids,
        rationale_fact_ids=list(rationale_fact_ids or []),
        competitors=competitors,
        constraints_checked=constraints_checked,
    )
