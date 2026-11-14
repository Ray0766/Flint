"""B4 论文强度公式（M2-024，PDD v0.2 §4.3）。

strength = 30·引用数分位 + 20·时效衰减 + 20·场所等级 + 15·同行评审 +
15·代码/数据可得（0~100）。权重可配置（和须为 100），初值属 Open Questions
（人工评估校准）。时效为半衰期指数衰减；无日期记 0（不猜时效）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class PaperScoreWeights:
    citation: int = 30
    recency: int = 20
    venue: int = 20
    peer_review: int = 15
    artifacts: int = 15

    def __post_init__(self) -> None:
        total = self.citation + self.recency + self.venue + self.peer_review + self.artifacts
        if total != 100:
            raise ValueError(f"weights must sum to 100, got {total}")


@dataclass(frozen=True)
class ScoreComponents:
    total: float
    breakdown: dict[str, float] = field(default_factory=dict)


def citation_percentile(cited_by: int, corpus_citations: list[int]) -> float:
    """<= 口径分位（与热度分位同族）；空语料 = 自身即天花板。"""
    if not corpus_citations:
        return 1.0
    at_or_below = sum(1 for c in corpus_citations if c <= cited_by)
    return at_or_below / len(corpus_citations)


def recency_decay(
    published: date | None, today: date, half_life_days: int = 730
) -> float:
    if published is None:
        return 0.0
    age_days = max(0, (today - published).days)
    return float(0.5 ** (age_days / half_life_days))


def score_paper_components(
    cited_by: int,
    corpus_citations: list[int],
    published: date | None,
    today: date,
    venue_tier: float,
    peer_reviewed: bool,
    artifacts_available: bool,
    weights: PaperScoreWeights | None = None,
    half_life_days: int = 730,
) -> ScoreComponents:
    w = weights or PaperScoreWeights()
    breakdown = {
        "citation": w.citation * citation_percentile(cited_by, corpus_citations),
        "recency": w.recency * recency_decay(published, today, half_life_days),
        "venue": w.venue * max(0.0, min(1.0, venue_tier)),
        "peer_review": w.peer_review * (1.0 if peer_reviewed else 0.0),
        "artifacts": w.artifacts * (1.0 if artifacts_available else 0.0),
    }
    return ScoreComponents(total=sum(breakdown.values()), breakdown=breakdown)
