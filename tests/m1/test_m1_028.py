"""M1-028 acceptance tests: incremental centroid update + drift guard.

Acceptance (tasks.json M1-028):
  - EMA update
  - single-day movement beyond the cap triggers the guard and leaves an audit
"""
from __future__ import annotations

import numpy as np

from flint.cluster.centroid import CentroidUpdate, update_centroid
from flint.domain.models import CentroidDriftAudit

DIM = 16


def unit(v: np.ndarray) -> list[float]:
    return list((v / np.linalg.norm(v)).tolist())


def axis(i: int) -> np.ndarray:
    v = np.zeros(DIM)
    v[i] = 1.0
    return v


def cosine(a: list[float], b: list[float]) -> float:
    x, y = np.asarray(a), np.asarray(b)
    return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y)))


def test_ema_moves_toward_day_mean() -> None:
    old = unit(axis(0))
    day_mean = unit(axis(0) + 0.3 * axis(1))
    update = update_centroid(
        "c-1", old, day_mean, alpha=0.2, max_shift=0.5
    )
    assert isinstance(update, CentroidUpdate)
    assert update.audit is None
    expected = np.asarray(old) * 0.8 + np.asarray(day_mean) * 0.2
    expected = expected / np.linalg.norm(expected)
    assert cosine(update.centroid, list(expected.tolist())) > 0.999999
    assert abs(float(np.linalg.norm(update.centroid)) - 1.0) < 1e-6


def test_alpha_zero_keeps_old_centroid() -> None:
    old = unit(axis(0))
    update = update_centroid("c-1", old, unit(axis(1)), alpha=0.0, max_shift=0.5)
    assert cosine(update.centroid, old) > 0.999999


def test_drift_beyond_cap_triggers_guard_and_audit() -> None:
    old = unit(axis(0))
    hostile_mean = unit(axis(1))  # orthogonal: EMA with big alpha would jump far
    update = update_centroid(
        "c-drift", old, hostile_mean, alpha=0.9, max_shift=0.2
    )
    assert update.centroid == old, "guard must reject the oversized move"
    assert isinstance(update.audit, CentroidDriftAudit)
    assert update.audit.cluster_id == "c-drift"
    assert update.audit.attempted_shift > 0.2
    assert update.audit.action == "rejected"


def test_shift_within_cap_passes_without_audit() -> None:
    old = unit(axis(0))
    nearby = unit(axis(0) + 0.1 * axis(1))
    update = update_centroid("c-ok", old, nearby, alpha=0.3, max_shift=0.2)
    assert update.audit is None
    assert update.centroid != old
