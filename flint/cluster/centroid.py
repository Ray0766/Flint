"""centroid 增量更新与漂移防护（M1-028，PDD v0.2 §3.2 步骤 2）。

- EMA：new = normalize((1-alpha)·old + alpha·day_mean)，alpha 配置化
  （EMA 系数属 Open Question 类阈值，标注集校准前由调用方传入）。
- 漂移防护：单日 cosine 位移超 max_shift → 拒绝本次更新（centroid 原样保留）
  并产出 DriftAudit 留痕——防单日污染样本拖走簇心。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from flint.domain.models import CentroidDriftAudit, Vector

# 决策③（v0.4）：漂移审计唯一命名 = 冻结件 CentroidDriftAudit，
# 本模块不再自设同义类型。


@dataclass(frozen=True)
class CentroidUpdate:
    cluster_id: str
    centroid: Vector
    audit: CentroidDriftAudit | None


def _unit(v: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(v))
    return v / norm if norm > 0.0 else v


def update_centroid(
    cluster_id: str,
    old: Vector,
    day_mean: Vector,
    alpha: float,
    max_shift: float,
) -> CentroidUpdate:
    old_arr = _unit(np.asarray(old, dtype=np.float64))
    mean_arr = _unit(np.asarray(day_mean, dtype=np.float64))
    proposed = _unit((1.0 - alpha) * old_arr + alpha * mean_arr)
    shift = float(1.0 - old_arr @ proposed)  # cosine distance moved today
    if shift > max_shift:
        return CentroidUpdate(
            cluster_id=cluster_id,
            centroid=list(old),
            audit=CentroidDriftAudit(
                cluster_id=cluster_id,
                attempted_shift=shift,
                max_shift=max_shift,
                action="rejected",
            ),
        )
    return CentroidUpdate(
        cluster_id=cluster_id, centroid=list(proposed.tolist()), audit=None
    )
