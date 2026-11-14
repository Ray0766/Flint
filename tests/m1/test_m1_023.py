"""M1-023 acceptance tests: daily cluster candidates (agglomerative, cosine threshold).

Acceptance (tasks.json M1-023):
  - similarity threshold is configuration-driven
  - 1e4 keywords/day clusters in < 60s on CPU
"""
from __future__ import annotations

import time

import numpy as np

from flint.cluster.daily import ClusterCandidate, cluster_keywords

DIM = 64  # geometry, not model fidelity — perf test below uses full 1024


def make_groups(rng: np.random.Generator) -> tuple[list[str], list[list[float]]]:
    """Two tight groups around orthogonal axes + tiny noise."""
    ids: list[str] = []
    vectors: list[list[float]] = []
    for g, axis in enumerate([0, 1]):
        base = np.zeros(DIM)
        base[axis] = 1.0
        for i in range(5):
            noisy = base + rng.normal(0, 0.01, DIM)
            noisy /= np.linalg.norm(noisy)
            ids.append(f"g{g}-{i}")
            vectors.append(noisy.tolist())
    return ids, vectors


def test_two_orthogonal_groups_split_at_high_threshold() -> None:
    ids, vectors = make_groups(np.random.default_rng(7))
    candidates = cluster_keywords(ids, vectors, similarity_threshold=0.5)
    assert len(candidates) == 2
    memberships = sorted(tuple(sorted(c.keyword_ids)) for c in candidates)
    assert memberships[0] == tuple(sorted(f"g0-{i}" for i in range(5)))
    assert memberships[1] == tuple(sorted(f"g1-{i}" for i in range(5)))


def test_threshold_is_configurable() -> None:
    """The same data merges into one cluster once the configured threshold
    tolerates orthogonal members — proving the knob actually drives behavior."""
    ids, vectors = make_groups(np.random.default_rng(7))
    merged = cluster_keywords(ids, vectors, similarity_threshold=-0.5)
    assert len(merged) == 1
    split = cluster_keywords(ids, vectors, similarity_threshold=0.5)
    assert len(split) == 2


def test_centroid_is_normalized_mean() -> None:
    ids, vectors = make_groups(np.random.default_rng(7))
    candidates = cluster_keywords(ids, vectors, similarity_threshold=0.5)
    for cand in candidates:
        assert isinstance(cand, ClusterCandidate)
        norm = float(np.linalg.norm(cand.centroid))
        assert abs(norm - 1.0) < 1e-6
        assert len(cand.centroid) == DIM


def test_edge_cases_empty_and_single() -> None:
    assert cluster_keywords([], [], similarity_threshold=0.5) == []
    only = cluster_keywords(["solo"], [[1.0] + [0.0] * (DIM - 1)], 0.5)
    assert len(only) == 1
    assert only[0].keyword_ids == ["solo"]


def test_perf_1e4_keywords_under_60s() -> None:
    rng = np.random.default_rng(42)
    n = 10_000
    matrix = rng.normal(0, 1, (n, 1024)).astype(np.float32)
    matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
    ids = [f"kw-{i}" for i in range(n)]
    vectors = matrix.tolist()
    started = time.perf_counter()
    candidates = cluster_keywords(ids, vectors, similarity_threshold=0.75)
    elapsed = time.perf_counter() - started
    assert elapsed < 60.0, f"clustering took {elapsed:.1f}s (limit 60s)"
    assert sum(len(c.keyword_ids) for c in candidates) == n
