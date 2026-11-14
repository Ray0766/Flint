"""M1-031 acceptance tests: SignalFlag detection (novelty / momentum / revival).

Acceptance (tasks.json M1-031):
  - all three rule thresholds are configuration-driven
  - 3 constructed samples per signal all hit
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from flint.signals import SignalConfig, detect_signals

TODAY = date(2026, 7, 23)
CFG = SignalConfig()  # PDD §3.3 defaults: novelty<=7d, momentum 7d delta>=20


def series(points: list[tuple[int, float]]) -> list[tuple[date, float]]:
    return [(TODAY - timedelta(days=d), v) for d, v in points]


FLAT = series([(14, 50.0), (7, 50.0), (0, 50.0)])


# ── novelty: 3 samples ────────────────────────────────────

@pytest.mark.parametrize("age_days", [0, 3, 7])
def test_novelty_samples_hit(age_days: int) -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=age_days),
        revived_today=False,
        norm_series=FLAT,
        today=TODAY,
        config=CFG,
    )
    assert "novelty" in flags


def test_novelty_expires_after_window() -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=8),
        revived_today=False,
        norm_series=FLAT,
        today=TODAY,
        config=CFG,
    )
    assert "novelty" not in flags


# ── momentum: 3 samples ───────────────────────────────────

@pytest.mark.parametrize(
    "history",
    [
        [(7, 10.0), (0, 90.0)],           # huge 7-day jump
        [(7, 40.0), (0, 60.1)],           # just above the 20-point default
        [(10, 30.0), (7, 30.0), (0, 55.0)],  # baseline picked at 7d boundary
    ],
)
def test_momentum_samples_hit(history: list[tuple[int, float]]) -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=100),
        revived_today=False,
        norm_series=series(history),
        today=TODAY,
        config=CFG,
    )
    assert "momentum" in flags


def test_momentum_needs_delta_above_threshold() -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=100),
        revived_today=False,
        norm_series=series([(7, 40.0), (0, 59.9)]),
        today=TODAY,
        config=CFG,
    )
    assert "momentum" not in flags


def test_momentum_needs_baseline_history() -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=100),
        revived_today=False,
        norm_series=series([(3, 10.0), (0, 90.0)]),  # nothing at/before 7d ago
        today=TODAY,
        config=CFG,
    )
    assert "momentum" not in flags


# ── revival: 3 samples ────────────────────────────────────

@pytest.mark.parametrize("age_days", [30, 100, 365])
def test_revival_samples_hit(age_days: int) -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=age_days),
        revived_today=True,
        norm_series=FLAT,
        today=TODAY,
        config=CFG,
    )
    assert "revival" in flags


def test_no_revival_without_event() -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=30),
        revived_today=False,
        norm_series=FLAT,
        today=TODAY,
        config=CFG,
    )
    assert "revival" not in flags


# ── thresholds are configurable ───────────────────────────

def test_all_three_thresholds_configurable() -> None:
    cfg = SignalConfig(novelty_days=1, momentum_window_days=14, momentum_delta=5.0)
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=2),          # novel under 7d, not under 1d
        revived_today=False,
        norm_series=series([(14, 50.0), (0, 56.0)]),   # +6 over 14d window
        today=TODAY,
        config=cfg,
    )
    assert "novelty" not in flags
    assert "momentum" in flags


def test_flags_combine() -> None:
    flags = detect_signals(
        first_seen=TODAY - timedelta(days=2),
        revived_today=True,
        norm_series=series([(7, 10.0), (0, 90.0)]),
        today=TODAY,
        config=CFG,
    )
    assert set(flags) == {"novelty", "momentum", "revival"}
