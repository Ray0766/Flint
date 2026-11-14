"""血缘②③ 分裂与合并检测（M1-025，PDD v0.2 §3.2 步骤 3）。

判定规则（对 s1 剩余关键词聚出的候选新簇 × 旧簇心，链接 = cosine >= tau_link）：
- 多旧对一新 → merge：旧簇标 merged_into=新簇 ID，新簇 parent_cluster_ids=旧簇集；
- 一旧对多新 → split：每个新簇 parent_cluster_ids=[该旧簇]；
- 一旧对一新 → new + 记录 parent（血缘保留但不标分裂——s1 未吸收说明簇心已漂移，
  按新生建档、留可追溯的来源）；
- 无链接 → new（交 M1-027 建档命名）。
- 被 merge 消费的旧簇不再充当 split 父簇（一日一命运，先并后分不并存）。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from flint.cluster.daily import ClusterCandidate
from flint.domain.models import Vector
from flint.lineage.s1 import ClusterRef

DecisionKind = Literal["split", "merge", "new"]


@dataclass(frozen=True)
class LineageDecision:
    kind: DecisionKind
    new_cluster_id: str
    keyword_ids: list[str]
    centroid: Vector
    parent_cluster_ids: list[str]


@dataclass
class SplitMergeResult:
    decisions: list[LineageDecision] = field(default_factory=list)
    merged_into: dict[str, str] = field(default_factory=dict)


def _normalized(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def detect_split_merge(
    candidates: list[ClusterCandidate],
    existing: list[ClusterRef],
    tau_link: float,
    new_id_factory: Callable[[int], str],
) -> SplitMergeResult:
    result = SplitMergeResult()
    if not candidates:
        return result
    pool = [ref for ref in existing if ref.status != "merged"]

    if pool:
        cand_matrix = _normalized(
            np.asarray([c.centroid for c in candidates], dtype=np.float32)
        )
        old_matrix = _normalized(
            np.asarray([ref.centroid for ref in pool], dtype=np.float32)
        )
        sims = cand_matrix @ old_matrix.T
        links: list[list[str]] = [
            [pool[j].cluster_id for j in range(len(pool)) if float(sims[i][j]) >= tau_link]
            for i in range(len(candidates))
        ]
    else:
        links = [[] for _ in candidates]

    # pass 1: merges claim their parent clusters first (one fate per day)
    merged_parents: set[str] = set()
    kinds: list[DecisionKind] = []
    new_ids = [new_id_factory(i) for i in range(len(candidates))]
    for i, linked in enumerate(links):
        if len(linked) >= 2:
            kinds.append("merge")
            for old_id in linked:
                merged_parents.add(old_id)
                result.merged_into[old_id] = new_ids[i]
        else:
            kinds.append("new")  # provisional; split resolved in pass 2

    # pass 2: an old cluster linked to >=2 candidates (and not consumed by a
    # merge) marks those candidates as its splits
    parent_fanout: dict[str, list[int]] = {}
    for i, linked in enumerate(links):
        if kinds[i] == "merge":
            continue
        for old_id in linked:
            if old_id not in merged_parents:
                parent_fanout.setdefault(old_id, []).append(i)
    split_indices = {
        i for indices in parent_fanout.values() if len(indices) >= 2 for i in indices
    }

    for i, candidate in enumerate(candidates):
        if kinds[i] == "merge":
            parents = sorted(links[i])
            kind: DecisionKind = "merge"
        else:
            parents = sorted(o for o in links[i] if o not in merged_parents)
            kind = "split" if i in split_indices else "new"
        result.decisions.append(
            LineageDecision(
                kind=kind,
                new_cluster_id=new_ids[i],
                keyword_ids=list(candidate.keyword_ids),
                centroid=list(candidate.centroid),
                parent_cluster_ids=parents,
            )
        )
    return result
