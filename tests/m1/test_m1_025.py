"""M1-025 acceptance tests: lineage steps 2+3 — split & merge detection.

Acceptance (tasks.json M1-025):
  - 5 constructed split cases and 5 merge cases are all detected
  - parent_cluster_ids / merged_into are correct
"""
from __future__ import annotations

import numpy as np

from flint.cluster.daily import ClusterCandidate
from flint.lineage.s1 import ClusterRef
from flint.lineage.s23 import detect_split_merge

DIM = 32
TAU_LINK = 0.6


def axis(i: int) -> np.ndarray:
    v = np.zeros(DIM)
    v[i] = 1.0
    return v


def unit(v: np.ndarray) -> list[float]:
    return list((v / np.linalg.norm(v)).tolist())


def perturbed(i: int, other: int, weight: float) -> list[float]:
    return unit(axis(i) + weight * axis(other))


def id_factory(i: int) -> str:
    return f"c-new-{i}"


# 5 split scenarios: old cluster on axis k, two new candidates leaning toward
# different secondary axes but both still >= tau_link to the old centroid.
SPLIT_OLD = [ClusterRef(f"c-split-{k}", unit(axis(k)), "active") for k in range(5)]
SPLIT_CANDIDATES = [
    cand
    for k in range(5)
    for cand in (
        ClusterCandidate([f"s{k}-a1", f"s{k}-a2"], perturbed(k, 20, 0.4)),
        ClusterCandidate([f"s{k}-b1", f"s{k}-b2"], perturbed(k, 21, 0.4)),
    )
]

# 5 merge scenarios: two old clusters on axes (10,11), (12,13), ... and one
# new candidate at their bisector (cos ~= 0.707 to each parent).
MERGE_OLD = [
    ClusterRef(f"c-merge-{2 * p + off}", unit(axis(10 + 2 * p + off)), "active")
    for p in range(5)
    for off in (0, 1)
]
MERGE_CANDIDATES = [
    ClusterCandidate([f"m{p}-kw"], unit(axis(10 + 2 * p) + axis(10 + 2 * p + 1)))
    for p in range(5)
]


def test_five_split_cases_all_detected() -> None:
    result = detect_split_merge(
        SPLIT_CANDIDATES, SPLIT_OLD, tau_link=TAU_LINK, new_id_factory=id_factory
    )
    splits = [d for d in result.decisions if d.kind == "split"]
    assert len(splits) == 10, "each of 5 old clusters splits into 2 new ones"
    for k in range(5):
        children = [d for d in splits if d.parent_cluster_ids == [f"c-split-{k}"]]
        assert len(children) == 2, f"old cluster c-split-{k} must have 2 split children"
    assert result.merged_into == {}


def test_five_merge_cases_all_detected() -> None:
    result = detect_split_merge(
        MERGE_CANDIDATES, MERGE_OLD, tau_link=TAU_LINK, new_id_factory=id_factory
    )
    merges = [d for d in result.decisions if d.kind == "merge"]
    assert len(merges) == 5
    for p, decision in enumerate(sorted(merges, key=lambda d: d.keyword_ids)):
        expected_parents = [f"c-merge-{2 * p}", f"c-merge-{2 * p + 1}"]
        assert sorted(decision.parent_cluster_ids) == expected_parents
        for old_id in expected_parents:
            assert result.merged_into[old_id] == decision.new_cluster_id


def test_unrelated_candidate_is_brand_new() -> None:
    candidate = ClusterCandidate(["lonely"], unit(axis(30)))
    result = detect_split_merge(
        [candidate], SPLIT_OLD, tau_link=TAU_LINK, new_id_factory=id_factory
    )
    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.kind == "new"
    assert decision.parent_cluster_ids == []
    assert result.merged_into == {}


def test_one_to_one_link_records_parent_without_split() -> None:
    candidate = ClusterCandidate(["single"], perturbed(0, 20, 0.4))
    result = detect_split_merge(
        [candidate], SPLIT_OLD, tau_link=TAU_LINK, new_id_factory=id_factory
    )
    decision = result.decisions[0]
    assert decision.kind == "new"
    assert decision.parent_cluster_ids == ["c-split-0"]


def test_new_ids_come_from_factory_and_are_unique() -> None:
    result = detect_split_merge(
        SPLIT_CANDIDATES + MERGE_CANDIDATES,
        SPLIT_OLD + MERGE_OLD,
        tau_link=TAU_LINK,
        new_id_factory=id_factory,
    )
    ids = [d.new_cluster_id for d in result.decisions]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("c-new-") for i in ids)


def test_merged_old_clusters_not_reused_as_split_parents() -> None:
    """An old cluster consumed by a merge cannot simultaneously split."""
    result = detect_split_merge(
        MERGE_CANDIDATES, MERGE_OLD, tau_link=TAU_LINK, new_id_factory=id_factory
    )
    split_parents = {
        p for d in result.decisions if d.kind == "split" for p in d.parent_cluster_ids
    }
    assert split_parents.isdisjoint(result.merged_into)
