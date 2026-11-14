"""当日聚类候选：凝聚聚类 + cosine 阈值（M1-023，技术方案 E1）。

- similarity_threshold 配置化（验收）：内部换算 distance_threshold = 1 - sim。
- 距离矩阵以 float32 归一化点积预计算（1e4 × 1e4 约 400MB、BLAS 秒级），
  再交给 scikit-learn 凝聚聚类（average linkage）——1e4/日 CPU < 60s（验收）。
- 输入输出保持域类型（keyword_id + list[float]），numpy 仅限模块内部。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from flint.domain.models import Vector


@dataclass(frozen=True)
class ClusterCandidate:
    keyword_ids: list[str]
    centroid: Vector


def _normalized(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms


def cluster_keywords(
    keyword_ids: list[str],
    embeddings: list[Vector],
    similarity_threshold: float,
) -> list[ClusterCandidate]:
    if len(keyword_ids) != len(embeddings):
        raise ValueError("keyword_ids and embeddings must be the same length")
    if not keyword_ids:
        return []

    matrix = _normalized(np.asarray(embeddings, dtype=np.float32))
    if len(keyword_ids) == 1:
        return [
            ClusterCandidate(
                keyword_ids=list(keyword_ids), centroid=matrix[0].tolist()
            )
        ]

    distances = 1.0 - matrix @ matrix.T
    np.fill_diagonal(distances, 0.0)
    np.clip(distances, 0.0, 2.0, out=distances)

    model = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=1.0 - similarity_threshold,
        metric="precomputed",
        linkage="average",
    )
    labels = model.fit_predict(distances)

    result: list[ClusterCandidate] = []
    for label in sorted(set(labels)):
        member_mask = labels == label
        members = [kid for kid, hit in zip(keyword_ids, member_mask) if hit]
        centroid = matrix[member_mask].mean(axis=0)
        norm = float(np.linalg.norm(centroid))
        if norm > 0.0:
            centroid = centroid / norm
        result.append(
            ClusterCandidate(keyword_ids=members, centroid=centroid.tolist())
        )
    return result
