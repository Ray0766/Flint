"""M2-025 acceptance tests: patent/news formula variants.

Acceptance (tasks.json M2-025):
  - patent variant carries family-size and legal-status components
  - news variant carries media-tier and independent-sources components
"""
from __future__ import annotations

from datetime import date

import pytest

from flint.scoring.variants import score_news_components, score_patent_components

TODAY = date(2026, 7, 28)


def test_patent_variant_components_present() -> None:
    components = score_patent_components(
        family_size=8, corpus_family_sizes=[1, 2, 4, 8],
        legal_status="active", published=TODAY, today=TODAY,
    )
    assert {"family", "legal", "recency"} <= set(components.breakdown)
    assert components.total > 0


def test_patent_family_size_moves_score() -> None:
    small = score_patent_components(1, [1, 2, 4, 8], "active", TODAY, TODAY)
    large = score_patent_components(8, [1, 2, 4, 8], "active", TODAY, TODAY)
    assert large.total > small.total, "family size is a live component"


def test_patent_legal_status_moves_score() -> None:
    active = score_patent_components(4, [1, 2, 4, 8], "active", TODAY, TODAY)
    pending = score_patent_components(4, [1, 2, 4, 8], "pending", TODAY, TODAY)
    assert active.total > pending.total, "legal status is a live component"
    with pytest.raises(ValueError, match="legal_status"):
        score_patent_components(4, [1], "expired?", TODAY, TODAY)


def test_news_variant_components_present() -> None:
    components = score_news_components(
        media_tier=1, independent_sources=4, published=TODAY, today=TODAY
    )
    assert {"media", "independence", "recency"} <= set(components.breakdown)


def test_news_media_tier_and_independence_move_score() -> None:
    top = score_news_components(1, 4, TODAY, TODAY)
    tabloid = score_news_components(3, 4, TODAY, TODAY)
    assert top.total > tabloid.total, "media tier is a live component"
    single = score_news_components(1, 1, TODAY, TODAY)
    assert top.total > single.total, "independent sources is a live component"
    with pytest.raises(ValueError, match="media_tier"):
        score_news_components(0, 1, TODAY, TODAY)
