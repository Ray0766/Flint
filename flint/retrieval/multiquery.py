"""多 query 结果合并去重（M2-019，PDD v0.2 §4.1 第三步）。

- 第一层：DOI 优先 / URL 兜底合并去重（复用 M2-009 dedupe_by_doi_url，
  首见保序）。
- 第二层：embedding 近邻辅助去重——标题向量 cosine >= near_dup_threshold
  （配置化）判近重，保留首见；embedder 可缺省关闭该层。
"""
from __future__ import annotations

import math

from flint.domain.models import Doc, Vector
from flint.embed import EmbeddingService
from flint.evidence.paper import dedupe_by_doi_url


def _cosine(a: Vector, b: Vector) -> float:
    dot = float(sum(x * y for x, y in zip(a, b)))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def merge_results(
    result_sets: list[list[Doc]],
    embedder: EmbeddingService | None,
    near_dup_threshold: float = 0.95,
) -> list[Doc]:
    flat = [doc for result_set in result_sets for doc in result_set]
    merged = dedupe_by_doi_url(flat)
    if embedder is None or not merged:
        return merged
    vectors = embedder.embed([doc.title for doc in merged])
    kept: list[Doc] = []
    kept_vectors: list[Vector] = []
    for doc, vector in zip(merged, vectors):
        if any(_cosine(vector, kv) >= near_dup_threshold for kv in kept_vectors):
            continue
        kept.append(doc)
        kept_vectors.append(vector)
    return kept
