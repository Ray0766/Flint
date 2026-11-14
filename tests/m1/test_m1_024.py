"""M1-024 acceptance tests: lineage step 1 — continuation matching.

Acceptance (tasks.json M1-024):
  - known continuation samples hit "continued"
  - cluster IDs stay stable across days
"""
from __future__ import annotations

import numpy as np

from flint.lineage.s1 import ClusterRef, ContinuationResult, match_continuation

DIM = 32


def axis_vec(axis: int, noise: float = 0.0, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    v = np.zeros(DIM)
    v[axis] = 1.0
    if noise:
        v = v + rng.normal(0, noise, DIM)
    v = v / np.linalg.norm(v)
    return list(v.tolist())


EXISTING = [
    ClusterRef(cluster_id="c-battery", centroid=axis_vec(0), status="active"),
    ClusterRef(cluster_id="c-agents", centroid=axis_vec(1), status="active"),
    ClusterRef(cluster_id="c-old-vr", centroid=axis_vec(2), status="dormant"),
]


def test_known_continuation_samples_hit() -> None:
    result = match_continuation(
        keyword_ids=["kw-solid", "kw-sodium", "kw-memory"],
        embeddings=[
            axis_vec(0, 0.02, seed=1),
            axis_vec(0, 0.02, seed=2),
            axis_vec(1, 0.02, seed=3),
        ],
        existing=EXISTING,
        tau_match=0.8,
    )
    assert isinstance(result, ContinuationResult)
    assert set(result.assignments["c-battery"]) == {"kw-solid", "kw-sodium"}
    assert result.assignments["c-agents"] == ["kw-memory"]
    assert result.leftover_keyword_ids == []


def test_cluster_ids_stay_stable() -> None:
    """Two consecutive days matched into the same cluster keep its ID."""
    day1 = match_continuation(
        ["d1-kw"], [axis_vec(0, 0.01, seed=4)], EXISTING, tau_match=0.8
    )
    day2 = match_continuation(
        ["d2-kw"], [axis_vec(0, 0.01, seed=5)], EXISTING, tau_match=0.8
    )
    assert "c-battery" in day1.assignments
    assert "c-battery" in day2.assignments
    assert day1.matched_cluster_ids == day2.matched_cluster_ids == ["c-battery"]


def test_below_threshold_goes_leftover() -> None:
    result = match_continuation(
        ["kw-new-topic"], [axis_vec(5)], EXISTING, tau_match=0.8
    )
    assert result.assignments == {}
    assert result.leftover_keyword_ids == ["kw-new-topic"]


def test_dormant_cluster_can_be_matched() -> None:
    """Dormant centroids stay in the comparison pool (PDD v0.2 SS3.2 step 1)."""
    result = match_continuation(
        ["kw-vr-again"], [axis_vec(2, 0.01, seed=6)], EXISTING, tau_match=0.8
    )
    assert result.assignments == {"c-old-vr": ["kw-vr-again"]}


def test_merged_clusters_excluded_from_pool() -> None:
    pool = EXISTING + [
        ClusterRef(cluster_id="c-gone", centroid=axis_vec(5), status="merged")
    ]
    result = match_continuation(
        ["kw-x"], [axis_vec(5)], pool, tau_match=0.8
    )
    assert result.leftover_keyword_ids == ["kw-x"]


def test_argmax_when_multiple_clusters_pass_threshold() -> None:
    blend = np.array(axis_vec(0)) * 0.8 + np.array(axis_vec(1)) * 0.6
    blend = blend / np.linalg.norm(blend)
    result = match_continuation(
        ["kw-blend"], [list(blend.tolist())], EXISTING, tau_match=0.5
    )
    assert result.assignments == {"c-battery": ["kw-blend"]}


def test_tau_is_configurable() -> None:
    loose = match_continuation(["kw"], [axis_vec(0, 0.15, seed=7)], EXISTING, 0.5)
    strict = match_continuation(["kw"], [axis_vec(0, 0.15, seed=7)], EXISTING, 0.99)
    assert loose.assignments and not strict.assignments
