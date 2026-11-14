"""M2-024 acceptance tests: B4 paper strength formula.

Acceptance (tasks.json M2-024):
  - 30/20/20/15/15 five-component weighting is configurable (initial values
    registered as Open Questions)
  - citation-percentile and recency-decay boundary golden cases
"""
from __future__ import annotations

from datetime import date

import pytest

from flint.scoring.paper import (
    PaperScoreWeights,
    citation_percentile,
    recency_decay,
    score_paper_components,
)

TODAY = date(2026, 7, 28)


def test_default_weights_are_b4_initial_values() -> None:
    weights = PaperScoreWeights()
    assert (weights.citation, weights.recency, weights.venue,
            weights.peer_review, weights.artifacts) == (30, 20, 20, 15, 15)


def test_weights_configurable_and_sum_checked() -> None:
    custom = PaperScoreWeights(citation=40, recency=20, venue=20, peer_review=10, artifacts=10)
    assert custom.citation == 40
    with pytest.raises(ValueError, match="100"):
        PaperScoreWeights(citation=90, recency=20, venue=20, peer_review=15, artifacts=15)


# ── citation percentile goldens ───────────────────────────


@pytest.mark.parametrize(
    ("cited", "corpus", "expected"),
    [
        (400, [0, 10, 50, 100, 400], 1.0),      # top of corpus
        (0, [0, 10, 50, 100, 400], 0.2),        # ties count as <=
        (50, [0, 10, 50, 100, 400], 0.6),
        (5, [], 1.0),                            # empty corpus: sole paper is its own ceiling
    ],
)
def test_citation_percentile_goldens(cited: int, corpus: list[int], expected: float) -> None:
    assert citation_percentile(cited, corpus) == pytest.approx(expected)


# ── recency decay goldens ─────────────────────────────────


def test_recency_decay_boundaries() -> None:
    assert recency_decay(TODAY, TODAY, half_life_days=730) == pytest.approx(1.0)
    two_years = date(2024, 7, 28)
    assert recency_decay(two_years, TODAY, half_life_days=730) == pytest.approx(0.5, abs=0.01)
    assert recency_decay(None, TODAY, half_life_days=730) == 0.0, "undated paper scores zero recency"


# ── composition ───────────────────────────────────────────


def test_full_score_composition() -> None:
    components = score_paper_components(
        cited_by=400,
        corpus_citations=[0, 10, 50, 100, 400],
        published=TODAY,
        today=TODAY,
        venue_tier=1.0,
        peer_reviewed=True,
        artifacts_available=True,
    )
    assert components.total == pytest.approx(100.0)
    weak = score_paper_components(
        cited_by=0,
        corpus_citations=[0, 10, 50, 100, 400],
        published=None,
        today=TODAY,
        venue_tier=0.0,
        peer_reviewed=False,
        artifacts_available=False,
    )
    assert weak.total == pytest.approx(30 * 0.2)  # only the citation-tie sliver
    assert set(weak.breakdown) == {"citation", "recency", "venue", "peer_review", "artifacts"}
