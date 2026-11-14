"""M2-027 acceptance tests: EvidenceScorer assembly + strength badges.

Acceptance (tasks.json M2-027):
  - the scale auto-selects by doc.origin (review-7 dual scale)
  - badges >=70 / 40~69 / <40; same-conclusion evidence ordered by strength
"""
from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from flint.domain.models import Doc, EvidenceScore
from flint.scoring.scorer import DualScaleScorer, ScorerContext, badge, sort_evidence

TODAY = date(2026, 7, 28)
FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(kind: str, origin: str, meta: dict[str, object]) -> Doc:
    payload = {"fetched_at": FETCHED, **meta}
    return Doc(
        doc_id=f"doc-{kind}-{origin}",
        source_id="crossref" if kind == "paper" else kind,
        kind=kind,  # type: ignore[arg-type]
        title=f"{kind} evidence",
        url=f"https://example.com/{kind}",
        published_at=TODAY,
        meta=payload,
        origin=origin,  # type: ignore[arg-type]
        access="public" if origin == "retrieved" else "private",
    )


def make_scorer() -> DualScaleScorer:
    return DualScaleScorer(
        context=ScorerContext(
            today=TODAY,
            corpus_citations=[0, 10, 50, 100, 400],
            corpus_family_sizes=[1, 2, 4, 8],
            venue_tiers={"neurips": 1.0, "journal of applied energy": 0.8},
        )
    )


def test_retrieved_paper_uses_b4_scale() -> None:
    doc = make_doc(
        "paper", "retrieved",
        {"cited_by": 400, "venue": "NeurIPS", "peer_reviewed": True, "artifacts": True},
    )
    score = make_scorer().strength(doc)
    assert isinstance(score, EvidenceScore)
    assert score.axis == "retrieved"
    assert score.strength >= 70
    assert "citation" in score.components


def test_retrieved_patent_and_news_use_variants() -> None:
    scorer = make_scorer()
    patent = scorer.strength(
        make_doc("patent", "retrieved", {"family_size": 8, "legal_status": "active"})
    )
    assert "family" in patent.components and "legal" in patent.components
    news = scorer.strength(
        make_doc("news", "retrieved", {"media_tier": 1, "independent_sources": 4})
    )
    assert "media" in news.components and "independence" in news.components


def test_user_provided_routes_to_user_scale() -> None:
    doc = make_doc("user_upload", "user_provided", {"verifiable": 1.0, "firsthand": 1.0})
    score = make_scorer().strength(doc)
    assert score.axis == "user_provided", "origin drives the scale (review-7)"
    assert set(score.components) == {"verifiable", "firsthand", "recency"}
    assert score.strength == 100


def test_generic_retrieved_kinds_still_score() -> None:
    doc = make_doc("product", "retrieved", {"last_activity": "2026-07-01"})
    score = make_scorer().strength(doc)
    assert score.axis == "retrieved"
    assert 0 <= score.strength <= 100


@pytest.mark.parametrize(
    ("strength", "expected"),
    [(100, "strong"), (70, "strong"), (69, "medium"), (40, "medium"), (39, "weak"), (0, "weak")],
)
def test_badge_boundaries(strength: int, expected: str) -> None:
    assert badge(strength) == expected


def test_sort_partitions_by_axis_and_orders_by_strength() -> None:
    scorer = make_scorer()
    strong_paper = make_doc(
        "paper", "retrieved",
        {"cited_by": 400, "venue": "NeurIPS", "peer_reviewed": True, "artifacts": True},
    )
    weak_paper = make_doc("paper", "retrieved", {"cited_by": 0, "venue": "unknown"})
    user_doc = make_doc("user_upload", "user_provided", {"verifiable": 0.9, "firsthand": 0.9})

    ranked = sort_evidence(scorer, [weak_paper, user_doc, strong_paper])
    assert list(ranked) == ["retrieved", "user_provided"], "partitioned by axis"
    retrieved_docs = [doc.doc_id for doc, _ in ranked["retrieved"]]
    assert retrieved_docs[0] == strong_paper.doc_id, "strength descending inside axis"
    assert len(ranked["user_provided"]) == 1
