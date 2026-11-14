"""血缘① 延续匹配（M1-024，PDD v0.2 §3.2 步骤 1~2）。

- 当日新关键词向量与全体 active + dormant 簇心算 cosine 相似度；
  >= tau_match 归入相似度最高的既有簇（cluster_id 跨日稳定，绝不改 ID）。
- merged 簇不参与匹配池（其身份已并入 merged_into 目标）。
- 未达阈值的关键词落 leftover，交给血缘②③（候选新簇 → 分裂/合并/新生）。
- tau_match 配置化（Open Question 类阈值，标注集校准前用调用方传入值）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from flint.domain.models import ClusterStatus, Vector


@dataclass(frozen=True)
class ClusterRef:
    cluster_id: str
    centroid: Vector
    status: ClusterStatus


@dataclass
class ContinuationResult:
    assignments: dict[str, list[str]] = field(default_factory=dict)
    matched_cluster_ids: list[str] = field(default_factory=list)
    leftover_keyword_ids: list[str] = field(default_factory=list)


def _normalized(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def match_continuation(
    keyword_ids: list[str],
    embeddings: list[Vector],
    existing: list[ClusterRef],
    tau_match: float,
) -> ContinuationResult:
    if len(keyword_ids) != len(embeddings):
        raise ValueError("keyword_ids and embeddings must be the same length")
    result = ContinuationResult()
    pool = [ref for ref in existing if ref.status != "merged"]
    if not keyword_ids:
        return result
    if not pool:
        result.leftover_keyword_ids = list(keyword_ids)
        return result

    kw_matrix = _normalized(np.asarray(embeddings, dtype=np.float32))
    centroid_matrix = _normalized(
        np.asarray([ref.centroid for ref in pool], dtype=np.float32)
    )
    similarities = kw_matrix @ centroid_matrix.T  # (n_keywords, n_clusters)

    for i, keyword_id in enumerate(keyword_ids):
        best = int(np.argmax(similarities[i]))
        if float(similarities[i][best]) >= tau_match:
            cluster_id = pool[best].cluster_id
            result.assignments.setdefault(cluster_id, []).append(keyword_id)
        else:
            result.leftover_keyword_ids.append(keyword_id)
    result.matched_cluster_ids = sorted(result.assignments)
    return result
