"""ClaimPromoter：提升不变量（M3-006，v0.3.2 §1 / S2-4）。

- 仅 confidence=="cited" 且 alignment=="supports" 的 claim 可提升为 Fact
  （origin="promoted_claim"，status="frozen"）；partial NEVER 提升——其余
  组合（speculative / pending / unsupported）同样全拒，白名单式判定。
- 三字段回填：Fact.source_claim_id / Fact.promoted_from /
  Claim.promoted_fact_id（副本回填，输入不变）。
- fact_id 确定性（sha256(claim_id|deliverable_id) 前缀）——同输入重跑
  幂等（freeze_ledger M3-020 消费）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace

from flint.domain.models import Claim, Fact


@dataclass
class PromotionResult:
    facts: list[Fact] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)  # promoted_fact_id 回填副本


def fact_id_for(claim_id: str, deliverable_id: str) -> str:
    digest = hashlib.sha256(f"{claim_id}|{deliverable_id}".encode()).hexdigest()
    return f"fact-{digest[:12]}"


def promote_claims(
    claims: list[Claim], deliverable_id: str, next_version: int
) -> PromotionResult:
    result = PromotionResult()
    for claim in claims:
        if claim.confidence == "cited" and claim.alignment == "supports":
            fact_id = fact_id_for(claim.claim_id, deliverable_id)
            result.facts.append(
                Fact(
                    fact_id=fact_id,
                    statement=claim.text_span,
                    value=None,
                    unit=None,
                    citation_ids=list(claim.citation_ids),
                    status="frozen",
                    origin="promoted_claim",
                    created_in_version=next_version,
                    source_claim_id=claim.claim_id,
                    promoted_from=deliverable_id,
                )
            )
            result.claims.append(replace(claim, promoted_fact_id=fact_id))
        else:
            result.claims.append(replace(claim))
    return result
