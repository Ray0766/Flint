"""M2-048 acceptance tests: quality card assembly.

Acceptance (tasks.json M2-048):
  - QualityCard fully populated (incl degradation records + blind spots)
  - blocking_reviews_open linkage slot ready (review-11 export gate is M3)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.domain.models import Doc, GapHint, QualityCard
from flint.gate.budget_ladder import BudgetLadderState, next_action_if_over
from flint.gate.quality_card import build_quality_card, evidence_age_median_days

TODAY = date(2026, 7, 26)
FETCHED = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(i: int, published: date | None, origin: str = "retrieved",
             access: str = "public") -> Doc:
    return Doc(
        doc_id=f"doc-{i}", source_id="crossref", kind="paper", title=f"t{i}",
        url=f"https://a/{i}", published_at=published,
        meta={"fetched_at": FETCHED}, origin=origin, access=access,  # type: ignore[arg-type]
    )


GAP = GapHint(
    missing_what="缺少对齐通过的支持证据", cause="missing_data",
    suggested_sources=["支持向检索"], action="search",
)


def ladder_with_l1() -> BudgetLadderState:
    state = BudgetLadderState(budget_cny=10.0)
    next_action_if_over(state, cost_accum=12.0)
    return state


def test_full_field_population() -> None:
    docs = [
        make_doc(0, date(2026, 6, 26)),
        make_doc(1, date(2026, 5, 27)),
        make_doc(2, date(2026, 7, 16), origin="user_provided", access="private"),
    ]
    card = build_quality_card(
        docs=docs, today=TODAY, citation_coverage=0.97, alignment_rate=0.98,
        ladder=ladder_with_l1(), gaps=[GAP],
        outage_statements=["盲区：paper 维度证据源全部不可用（已尝试 crossref、backup），该维度覆盖不达标"],
        disputed_facts=1, blocking_reviews_open=2,
        price_data_notes=["单价数据为 2025 年"], has_redactions=False,
    )
    assert isinstance(card, QualityCard)
    assert card.evidence_count == 3
    assert card.evidence_age_median_days == 30, "median of 30/60/10 days"
    assert card.citation_coverage == 0.97
    assert card.alignment_rate == 0.98
    assert card.degradations == ["L1：每 query 取回篇数 −50%（预算超限自动降级）"]
    assert card.user_supplied_evidence_count == 1
    assert card.private_evidence_ratio == 1 / 3
    assert card.disputed_facts == 1
    assert card.price_data_notes == ["单价数据为 2025 年"]
    assert len(card.blind_spots) == 2, "gaps + outage statements both land"
    assert card.reproducible is True


def test_blocking_reviews_linkage_slot_ready() -> None:
    card = build_quality_card(
        docs=[], today=TODAY, citation_coverage=1.0, alignment_rate=1.0,
        ladder=BudgetLadderState(budget_cny=10.0), gaps=[],
        outage_statements=[], disputed_facts=0, blocking_reviews_open=3,
        price_data_notes=[], has_redactions=False,
    )
    assert card.blocking_reviews_open == 3, "review-11 export gate reads this in M3"


def test_redaction_flips_reproducible() -> None:
    card = build_quality_card(
        docs=[], today=TODAY, citation_coverage=1.0, alignment_rate=1.0,
        ladder=BudgetLadderState(budget_cny=10.0), gaps=[],
        outage_statements=[], disputed_facts=0, blocking_reviews_open=0,
        price_data_notes=[], has_redactions=True,
    )
    assert card.reproducible is False


def test_median_edge_cases() -> None:
    assert evidence_age_median_days([], TODAY) == 0
    docs = [make_doc(0, None), make_doc(1, date(2026, 7, 16))]
    assert evidence_age_median_days(docs, TODAY) == 10, "undated docs excluded"
