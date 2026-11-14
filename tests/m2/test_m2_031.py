"""M2-031 acceptance tests: four-signal deriver (evidence-driven).

Acceptance (tasks.json M2-031):
  - funded_or_scaled / mature_pricing / same_target_user / active_last_12m
    each driven by concrete evidence
  - a signal with no evidence is never produced (negative case)
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.competitor.signals import SignalInputs, derive_signals
from flint.domain.models import Doc, PricingRecord

TODAY = date(2026, 7, 28)
FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def funding_doc() -> Doc:
    return Doc(
        doc_id="doc-funding-1", source_id="funding", kind="webpage",
        title="Series B announcement", url="https://funding.example/1",
        published_at=date(2026, 3, 1),
        meta={"fetched_at": FETCHED, "raised_usd": 30_000_000},
        origin="retrieved", access="public",
    )


def pricing(price: float | None, confidence: float) -> PricingRecord:
    return PricingRecord(
        plan="Pro", price=price, currency="USD", region="global",
        confidence=confidence,
        captured_at=datetime(2026, 7, 1, tzinfo=UTC), url="https://v.example/pricing",
    )


def empty_inputs() -> SignalInputs:
    return SignalInputs(
        funding_docs=[], pricing_records=[],
        same_target_user=None, last_activity=None, today=TODAY,
    )


def test_no_evidence_produces_no_signals() -> None:
    evaluation = derive_signals(empty_inputs())
    assert evaluation.fired == [], "no evidence -> no signal, no guessing"


def test_funded_or_scaled_needs_funding_evidence() -> None:
    inputs = empty_inputs()
    evaluation = derive_signals(
        SignalInputs(
            funding_docs=[funding_doc()], pricing_records=[],
            same_target_user=None, last_activity=None, today=TODAY,
        )
    )
    assert "funded_or_scaled" in evaluation.fired
    assert evaluation.evidence["funded_or_scaled"] == ["doc-funding-1"]
    assert "funded_or_scaled" not in derive_signals(inputs).fired


def test_mature_pricing_requires_confident_number() -> None:
    confident = derive_signals(
        SignalInputs([], [pricing(99.0, 0.9)], None, None, TODAY)
    )
    assert "mature_pricing" in confident.fired

    pending_conf = derive_signals(
        SignalInputs([], [pricing(99.0, 0.3)], None, None, TODAY)
    )
    assert "mature_pricing" not in pending_conf.fired, "待确认定价不产生 signal"
    assert pending_conf.evaluated["mature_pricing"] is None, "pending = 无法判定，非 False"

    contact_us = derive_signals(
        SignalInputs([], [pricing(None, 0.9)], None, None, TODAY)
    )
    assert "mature_pricing" not in contact_us.fired


def test_same_target_user_needs_explicit_judgment() -> None:
    yes = derive_signals(SignalInputs([], [], True, None, TODAY))
    assert "same_target_user" in yes.fired
    no = derive_signals(SignalInputs([], [], False, None, TODAY))
    assert "same_target_user" not in no.fired
    assert no.evaluated["same_target_user"] is False
    unknown = derive_signals(SignalInputs([], [], None, None, TODAY))
    assert unknown.evaluated["same_target_user"] is None, "未判定 != 否定"


def test_active_last_12m_from_activity_date() -> None:
    recent = derive_signals(SignalInputs([], [], None, date(2026, 6, 1), TODAY))
    assert "active_last_12m" in recent.fired
    stale = derive_signals(SignalInputs([], [], None, date(2024, 6, 1), TODAY))
    assert "active_last_12m" not in stale.fired
    assert stale.evaluated["active_last_12m"] is False
    missing = derive_signals(SignalInputs([], [], None, None, TODAY))
    assert missing.evaluated["active_last_12m"] is None


def test_all_four_signals_fire_together() -> None:
    evaluation = derive_signals(
        SignalInputs(
            funding_docs=[funding_doc()],
            pricing_records=[pricing(99.0, 0.95)],
            same_target_user=True,
            last_activity=date(2026, 7, 1),
            today=TODAY,
        )
    )
    assert sorted(evaluation.fired) == [
        "active_last_12m", "funded_or_scaled", "mature_pricing", "same_target_user",
    ]
