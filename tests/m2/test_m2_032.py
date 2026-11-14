"""M2-032 acceptance tests: competitor strength judgment (conservative face).

Acceptance (tasks.json M2-032):
  - any two signals = strong; insufficient signals = unknown (NOT weak)
  - pending pricing never participates in strength (just drops one signal)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.competitor.extract import CompetitorRecord
from flint.competitor.signals import SignalEvaluation
from flint.competitor.strength import build_competitor, judge_strength
from flint.domain.models import Competitor, PricingRecord, StrengthSignal

TODAY = date(2026, 7, 28)


def evaluation(**states: bool | None) -> SignalEvaluation:
    result = SignalEvaluation()
    defaults: dict[StrengthSignal, bool | None] = {
        "funded_or_scaled": None, "mature_pricing": None,
        "same_target_user": None, "active_last_12m": None,
    }
    defaults.update(states)  # type: ignore[arg-type]
    result.evaluated = defaults
    return result


def test_any_two_signals_is_strong() -> None:
    two = evaluation(funded_or_scaled=True, active_last_12m=True)
    assert judge_strength(two) == "strong"
    other_two = evaluation(mature_pricing=True, same_target_user=True)
    assert judge_strength(other_two) == "strong"


def test_one_signal_is_moderate() -> None:
    assert judge_strength(evaluation(mature_pricing=True)) == "moderate"


def test_insufficient_signals_is_unknown_not_weak() -> None:
    """信号不足以判定 → unknown（不是 weak）——判错 C 的代价不对称。"""
    nothing_known = evaluation()
    assert judge_strength(nothing_known) == "unknown"
    partially_known = evaluation(funded_or_scaled=False)  # 其余三项无法判定
    assert judge_strength(partially_known) == "unknown"


def test_weak_requires_full_negative_evidence() -> None:
    all_negated = evaluation(
        funded_or_scaled=False, mature_pricing=False,
        same_target_user=False, active_last_12m=False,
    )
    assert judge_strength(all_negated) == "weak", "weak 须四面证据全否证"


def test_pending_pricing_only_drops_one_signal() -> None:
    """定价待确认（mature_pricing=None）不参与判定：其余任二仍可 strong。"""
    strong_anyway = evaluation(
        funded_or_scaled=True, same_target_user=True, mature_pricing=None
    )
    assert judge_strength(strong_anyway) == "strong"
    # 其余不足 → unknown（而非 weak）
    insufficient = evaluation(
        mature_pricing=None, funded_or_scaled=False,
        same_target_user=False, active_last_12m=False,
    )
    assert judge_strength(insufficient) == "unknown"


def test_build_frozen_competitor_entity() -> None:
    record = CompetitorRecord(
        name="Solid Vendor", url="https://vendor.example", source_doc_ids=["doc-1"]
    )
    pending = PricingRecord(
        plan="Enterprise", price=None, currency="USD", region="global",
        confidence=0.3, captured_at=datetime(2026, 7, 1, tzinfo=UTC),
        url="https://vendor.example/pricing",
    )
    confident = PricingRecord(
        plan="Pro", price=99.0, currency="USD", region="global",
        confidence=0.9, captured_at=datetime(2026, 7, 1, tzinfo=UTC),
        url="https://vendor.example/pricing",
    )
    competitor = build_competitor(
        record,
        evaluation(mature_pricing=True, active_last_12m=True),
        pricing_records=[pending, confident],
    )
    assert isinstance(competitor, Competitor)
    assert competitor.name == "Solid Vendor"
    assert competitor.strength == "strong"
    assert sorted(competitor.strength_signals) == ["active_last_12m", "mature_pricing"]
    assert competitor.pricing == confident, "display picks the most confident record"

    bare = build_competitor(record, evaluation(), pricing_records=[])
    assert bare.strength == "unknown"
    assert bare.strength_signals == []
    assert bare.pricing is None
