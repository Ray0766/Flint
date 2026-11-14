"""M2-026 acceptance tests: user_provided scoring scale.

Acceptance (tasks.json M2-026):
  - independent 40-verifiability + 35-firsthand + 25-recency formula
  - axis backfilled; cross-scale score comparison rejected at the type layer
"""
from __future__ import annotations

from datetime import date

import pytest

from flint.domain.models import EvidenceScore
from flint.scoring.user_scale import (
    CrossAxisComparisonError,
    assert_comparable,
    score_user_provided,
)

TODAY = date(2026, 7, 28)


def test_formula_composition_and_axis() -> None:
    score = score_user_provided(
        verifiable=1.0, firsthand=1.0, published=TODAY, today=TODAY
    )
    assert isinstance(score, EvidenceScore)
    assert score.axis == "user_provided", "axis backfill is mandatory (review-7)"
    assert score.strength == 100
    assert set(score.components) == {"verifiable", "firsthand", "recency"}
    assert score.components["verifiable"] == pytest.approx(40.0)
    assert score.components["firsthand"] == pytest.approx(35.0)
    assert score.components["recency"] == pytest.approx(25.0)


def test_partial_inputs_scale_down() -> None:
    score = score_user_provided(
        verifiable=0.5, firsthand=0.0, published=None, today=TODAY
    )
    assert score.strength == 20  # 40*0.5 + 0 + 0
    assert score.components["recency"] == 0.0, "undated material earns no recency"


def test_inputs_clamped_to_unit_range() -> None:
    with pytest.raises(ValueError, match="verifiable"):
        score_user_provided(verifiable=1.4, firsthand=0.5, published=None, today=TODAY)


def test_cross_axis_comparison_rejected() -> None:
    user = score_user_provided(1.0, 1.0, TODAY, TODAY)
    retrieved = EvidenceScore(strength=80, axis="retrieved", components={})
    with pytest.raises(CrossAxisComparisonError):
        assert_comparable(user, retrieved)
    assert_comparable(user, score_user_provided(0.2, 0.2, None, TODAY))  # 同尺可比
