"""专利/新闻评分变体（M2-025，PDD v0.2 §4.3 变体行）。

- 专利：同族规模分位 40 + 法律状态 30（active=1 / pending=0.5，其余拒绝）
  + 时效 30。
- 新闻：媒体等级 40（tier1=1.0 / tier2=0.7 / tier3=0.4）+ 独立信源数 30
  （min(n/4, 1)）+ 时效 30。
变体权重初值与 B4 主权重同属 Open Questions（人工评估校准）。
"""
from __future__ import annotations

from datetime import date
from typing import Final

from flint.scoring.paper import ScoreComponents, citation_percentile, recency_decay

_LEGAL_FACTORS: Final[dict[str, float]] = {"active": 1.0, "pending": 0.5}
_MEDIA_FACTORS: Final[dict[int, float]] = {1: 1.0, 2: 0.7, 3: 0.4}


def score_patent_components(
    family_size: int,
    corpus_family_sizes: list[int],
    legal_status: str,
    published: date | None,
    today: date,
    half_life_days: int = 730,
) -> ScoreComponents:
    if legal_status not in _LEGAL_FACTORS:
        raise ValueError(f"unknown legal_status: {legal_status!r}")
    breakdown = {
        "family": 40 * citation_percentile(family_size, corpus_family_sizes),
        "legal": 30 * _LEGAL_FACTORS[legal_status],
        "recency": 30 * recency_decay(published, today, half_life_days),
    }
    return ScoreComponents(total=sum(breakdown.values()), breakdown=breakdown)


def score_news_components(
    media_tier: int,
    independent_sources: int,
    published: date | None,
    today: date,
    half_life_days: int = 180,
) -> ScoreComponents:
    if media_tier not in _MEDIA_FACTORS:
        raise ValueError(f"unknown media_tier: {media_tier!r}")
    breakdown = {
        "media": 40 * _MEDIA_FACTORS[media_tier],
        "independence": 30 * min(max(independent_sources, 0) / 4.0, 1.0),
        "recency": 30 * recency_decay(published, today, half_life_days),
    }
    return ScoreComponents(total=sum(breakdown.values()), breakdown=breakdown)
