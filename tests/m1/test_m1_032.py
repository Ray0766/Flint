"""M1-032 acceptance tests: EvidenceCard build (seven elements).

Acceptance (tasks.json M1-032):
  - the card carries all seven elements
  - top_links ordering rule is unit-tested

Seven elements (derivation recorded in docs/trace/M1-032.md): stable ids,
cluster name + category, keyword set, per-source normalized curves, signal
flags, top links, gap-annotation slot.
"""
from __future__ import annotations

from datetime import date

from flint.cards import CardView, LinkCandidate, build_card, rank_top_links
from flint.domain.models import Cluster, EvidenceCard, HeatPoint
from flint.sources.degradation import DegradationNote

DAY = date(2026, 7, 23)

CLUSTER = Cluster(
    cluster_id="c-battery",
    canonical_name="固态电池产业化",
    category_id="cat-energy",
    centroid=[1.0, 0.0],
    status="active",
    first_seen=date(2026, 7, 20),
    last_active=DAY,
    parent_cluster_ids=[],
    merged_into=None,
    aliases=["solid-state battery"],
)

HEAT = [
    HeatPoint("c-battery", "gtrends", DAY, 320.0, 88.0),
    HeatPoint("c-battery", "weibo", DAY, 2_900_000.0, 95.0),
    HeatPoint("c-battery", "gtrends", date(2026, 7, 22), 300.0, 80.0),
]

LINKS = [
    LinkCandidate("https://g.example/1", "gtrends", 1000.0),
    LinkCandidate("https://g.example/2", "gtrends", 500.0),
    LinkCandidate("https://w.example/1", "weibo", 3_000_000.0),
    LinkCandidate("https://w.example/2", "weibo", 1_000_000.0),
    LinkCandidate("https://w.example/3", "weibo", 500_000.0),
]

NOTES = [DegradationNote(day=DAY, source_id="arxiv", reason="fetch_failed", detail="503")]


def make_card(top_n: int = 5) -> CardView:
    return build_card(
        card_id="card-1",
        cluster=CLUSTER,
        keyword_ids=["kw-1", "kw-2"],
        flags=["novelty", "momentum"],
        link_candidates=LINKS,
        heat_points=HEAT,
        degradation_notes=NOTES,
        top_n=top_n,
    )


# ── seven elements ────────────────────────────────────────


def test_seven_elements_complete() -> None:
    view = make_card()
    assert view.card.card_id == "card-1"                      # 1 stable ids
    assert view.card.cluster_id == "c-battery"
    assert view.cluster_name == "固态电池产业化"                # 2 name + category
    assert view.category_id == "cat-energy"
    assert view.card.keyword_ids == ["kw-1", "kw-2"]          # 3 keywords
    assert set(view.heat_curves) == {"gtrends", "weibo"}      # 4 per-source curves
    assert view.card.flags == ["novelty", "momentum"]         # 5 signal flags
    assert view.card.top_links                                 # 6 top links
    assert view.gap_annotations and "arxiv" in view.gap_annotations[0]  # 7 gap slot


def test_frozen_evidence_card_type() -> None:
    view = make_card()
    assert isinstance(view.card, EvidenceCard)


def test_curves_sorted_by_day_within_source() -> None:
    view = make_card()
    days = [p.day for p in view.heat_curves["gtrends"]]
    assert days == sorted(days)


def test_gap_slot_empty_when_no_degradation() -> None:
    view = build_card(
        card_id="card-2",
        cluster=CLUSTER,
        keyword_ids=["kw-1"],
        flags=[],
        link_candidates=LINKS,
        heat_points=HEAT,
        degradation_notes=[],
    )
    assert view.gap_annotations == []


# ── top_links ordering rule ───────────────────────────────


def test_rank_uses_within_source_percentile_across_sources() -> None:
    """Raw scores never compare across sources (A2): each link ranks by its
    percentile INSIDE its own source, then percentiles interleave globally.
    g1 (1/1.0) and w1 (1.0) tie -> url ascending; then w2 (2/3 rank -> 0.667),
    g2 (0.5), w3 (0.333)."""
    ordered = rank_top_links(LINKS, top_n=5)
    assert ordered == [
        "https://g.example/1",
        "https://w.example/1",
        "https://w.example/2",
        "https://g.example/2",
        "https://w.example/3",
    ]


def test_rank_caps_at_top_n() -> None:
    assert len(rank_top_links(LINKS, top_n=2)) == 2
    view = make_card(top_n=3)
    assert len(view.card.top_links) == 3


def test_rank_dedupes_urls_keeping_best() -> None:
    dup = LINKS + [LinkCandidate("https://g.example/1", "weibo", 1.0)]
    ordered = rank_top_links(dup, top_n=10)
    assert ordered.count("https://g.example/1") == 1
    assert ordered[0] == "https://g.example/1"


def test_rank_deterministic_on_score_ties() -> None:
    ties = [
        LinkCandidate("https://b.example", "gtrends", 100.0),
        LinkCandidate("https://a.example", "gtrends", 100.0),
    ]
    assert rank_top_links(ties, top_n=2) == ["https://a.example", "https://b.example"]


def test_rank_empty() -> None:
    assert rank_top_links([], top_n=5) == []
