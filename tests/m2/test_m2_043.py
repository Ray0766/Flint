"""M2-043 acceptance tests: B7 budget degradation ladder.

Acceptance (tasks.json M2-043):
  - over budget degrades strictly in the fixed order L1 -> L4 (order asserted)
  - every applied level lands on the quality card, user-visible
"""
from __future__ import annotations

import pytest

from flint.domain.models import QualityCard
from flint.gate.budget_ladder import (
    LADDER,
    AnalysisBudgetKnobs,
    BudgetLadderState,
    LadderExhausted,
    apply_action,
    next_action_if_over,
    quality_card_entries,
)


def knobs() -> AnalysisBudgetKnobs:
    return AnalysisBudgetKnobs(
        docs_per_query=8, expansion_queries=6,
        noncore_model_tier="large", appendix_truncated=False,
    )


def test_ladder_is_fixed_four_levels() -> None:
    assert LADDER == ("L1", "L2", "L3", "L4")


def test_within_budget_no_degradation() -> None:
    state = BudgetLadderState(budget_cny=10.0)
    action = next_action_if_over(state, cost_accum=9.99)
    assert action is None
    assert state.applied == []
    assert quality_card_entries(state) == []


def test_over_budget_degrades_in_strict_order() -> None:
    state = BudgetLadderState(budget_cny=10.0)
    levels = []
    for _ in range(4):
        action = next_action_if_over(state, cost_accum=12.0)
        assert action is not None
        levels.append(action.level)
    assert levels == ["L1", "L2", "L3", "L4"], "fixed order, one level per breach"


def test_ladder_exhausted_after_l4() -> None:
    state = BudgetLadderState(budget_cny=10.0)
    for _ in range(4):
        next_action_if_over(state, cost_accum=12.0)
    with pytest.raises(LadderExhausted):
        next_action_if_over(state, cost_accum=12.0)


def test_knob_effects_per_level() -> None:
    state = BudgetLadderState(budget_cny=10.0)
    current = knobs()

    l1 = next_action_if_over(state, cost_accum=12.0)
    assert l1 is not None
    current = apply_action(l1, current)
    assert current.docs_per_query == 4, "L1: docs per query -50%"
    assert current.expansion_queries == 6, "L1 touches retrieval only"

    l2 = next_action_if_over(state, cost_accum=12.0)
    assert l2 is not None
    current = apply_action(l2, current)
    assert current.expansion_queries == 3, "L2: expansion queries halved"

    l3 = next_action_if_over(state, cost_accum=12.0)
    assert l3 is not None
    current = apply_action(l3, current)
    assert current.noncore_model_tier == "small", "L3: non-core sections downtier"

    l4 = next_action_if_over(state, cost_accum=12.0)
    assert l4 is not None
    current = apply_action(l4, current)
    assert current.appendix_truncated is True, "L4: appendix truncated + annotated"

    assert current == AnalysisBudgetKnobs(
        docs_per_query=4, expansion_queries=3,
        noncore_model_tier="small", appendix_truncated=True,
    ), "full end-state: later levels never revisit earlier knobs"


def test_halving_floors_at_one() -> None:
    state = BudgetLadderState(budget_cny=1.0)
    current = AnalysisBudgetKnobs(
        docs_per_query=1, expansion_queries=1,
        noncore_model_tier="large", appendix_truncated=False,
    )
    l1 = next_action_if_over(state, cost_accum=2.0)
    assert l1 is not None
    current = apply_action(l1, current)
    assert current.docs_per_query == 1, "never degrade to zero retrieval"


def test_every_level_lands_on_quality_card() -> None:
    state = BudgetLadderState(budget_cny=10.0)
    for _ in range(3):
        next_action_if_over(state, cost_accum=12.0)
    entries = quality_card_entries(state)
    assert len(entries) == 3
    for level, entry in zip(("L1", "L2", "L3"), entries):
        assert entry.startswith(f"{level}："), "entry names its level"
        assert "预算" in entry, "user-readable budget copy"

    card = QualityCard(
        evidence_count=10, evidence_age_median_days=30, citation_coverage=1.0,
        alignment_rate=0.98, degradations=entries, user_supplied_evidence_count=0,
        private_evidence_ratio=0.0, disputed_facts=0, blocking_reviews_open=0,
        price_data_notes=[], blind_spots=[], reproducible=True,
    )
    assert card.degradations == entries, "entries feed the frozen QualityCard shape"
