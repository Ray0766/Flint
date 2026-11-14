"""EvidenceScorer 装配与徽标（M2-027，审7 双尺 / 冻结协议 EvidenceScorer）。

- 按 doc.origin 自动选尺：retrieved → B4 族（paper 主式 / patent / news 变体 /
  其余 kind 走通用式：时效 60 + 来源在案 40）；user_provided → 40/35/25 尺。
- axis 回填判别；跨尺不比较（sort_evidence 按 axis 分区、区内按强度降序，
  UI 分区展示口径）。
- 徽标：强 >=70 / 中 40~69 / 弱 <40。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from flint.domain.models import Doc, EvidenceOrigin, EvidenceScore
from flint.scoring.paper import ScoreComponents, recency_decay, score_paper_components
from flint.scoring.user_scale import score_user_provided
from flint.scoring.variants import score_news_components, score_patent_components

Badge = Literal["strong", "medium", "weak"]


@dataclass(frozen=True)
class ScorerContext:
    today: date
    corpus_citations: list[int] = field(default_factory=list)
    corpus_family_sizes: list[int] = field(default_factory=list)
    venue_tiers: dict[str, float] = field(default_factory=dict)
    default_venue_tier: float = 0.4


def badge(strength: int) -> Badge:
    if strength >= 70:
        return "strong"
    if strength >= 40:
        return "medium"
    return "weak"


class DualScaleScorer:
    """冻结协议 EvidenceScorer 实现：strength(doc) -> EvidenceScore。"""

    def __init__(self, context: ScorerContext) -> None:
        self._context = context

    def strength(self, doc: Doc) -> EvidenceScore:
        if doc.origin == "user_provided":
            return score_user_provided(
                verifiable=float(doc.meta.get("verifiable", 0.5)),
                firsthand=float(doc.meta.get("firsthand", 0.5)),
                published=doc.published_at,
                today=self._context.today,
            )
        components = self._retrieved_components(doc)
        return EvidenceScore(
            strength=round(components.total),
            axis="retrieved",
            components=dict(components.breakdown),
        )

    def _retrieved_components(self, doc: Doc) -> ScoreComponents:
        ctx = self._context
        if doc.kind == "paper":
            venue = str(doc.meta.get("venue", "")).strip().lower()
            return score_paper_components(
                cited_by=int(doc.meta.get("cited_by", 0)),
                corpus_citations=ctx.corpus_citations,
                published=doc.published_at,
                today=ctx.today,
                venue_tier=ctx.venue_tiers.get(venue, ctx.default_venue_tier),
                peer_reviewed=bool(doc.meta.get("peer_reviewed", False)),
                artifacts_available=bool(doc.meta.get("artifacts", False)),
            )
        if doc.kind == "patent":
            return score_patent_components(
                family_size=int(doc.meta.get("family_size", 1)),
                corpus_family_sizes=ctx.corpus_family_sizes,
                legal_status=str(doc.meta.get("legal_status", "pending")),
                published=doc.published_at,
                today=ctx.today,
            )
        if doc.kind == "news":
            return score_news_components(
                media_tier=int(doc.meta.get("media_tier", 3)),
                independent_sources=int(doc.meta.get("independent_sources", 1)),
                published=doc.published_at,
                today=ctx.today,
            )
        # 通用 retrieved 式（product/repo/webpage）：时效 60 + 来源在案 40
        breakdown = {
            "recency": 60 * recency_decay(doc.published_at, ctx.today, 365),
            "provenance": 40.0 if doc.url else 0.0,
        }
        return ScoreComponents(total=sum(breakdown.values()), breakdown=breakdown)


def sort_evidence(
    scorer: DualScaleScorer, docs: list[Doc]
) -> dict[EvidenceOrigin, list[tuple[Doc, EvidenceScore]]]:
    """UI 展示口径：按 axis 分区（retrieved 先），区内按强度降序。"""
    partitions: dict[EvidenceOrigin, list[tuple[Doc, EvidenceScore]]] = {}
    for doc in docs:
        score = scorer.strength(doc)
        partitions.setdefault(score.axis, []).append((doc, score))
    ordered: dict[EvidenceOrigin, list[tuple[Doc, EvidenceScore]]] = {}
    for axis in ("retrieved", "user_provided"):
        if axis in partitions:
            ordered[axis] = sorted(
                partitions[axis], key=lambda pair: -pair[1].strength
            )
    return ordered
