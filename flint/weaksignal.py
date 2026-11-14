"""弱信号早期轨（H-4，读时算，零契约 S2-1）——BERTrend/Snapchat 路线的差异化点。

早期抓"**小而在加速**"的语义新趋势：agg 尚低（<ceiling）+ 速度>0（在加速）+ 语义**稳定/紧致**
（bge-m3 质心低漂移=真成形非噪声）+ 突发（Kleinberg burst_weight）。**单列一轨，NEVER 混主榜**。

质心历史来自新内部表 `cluster_centroid_daily`（迁移 0018，NEVER 改冻结 Cluster）；agg/burst 来自
heat_points 读时算。纯计算、零依赖（stdlib）。参数临时初值（标定通道见 v0.4-问题单）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class WeakSignalConfig:
    agg_ceiling: float = 40.0       # "小"上限：agg ≥ 此属主榜料、不进弱信号轨
    velocity_window: int = 1        # 速度窗（日）
    drift_penalty: float = 1.0      # 语义漂移惩罚（高漂移=噪声→降权）
    burst_coef: float = 1.0         # 突发强度权


@dataclass(frozen=True)
class WeakSignalScore:
    cluster_id: str
    is_weak_signal: bool
    score: float
    drift: float
    agg: float
    velocity: float
    burst_weight: float


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def centroid_drift(history: list[list[float]]) -> float:
    """相邻日质心 cosine 距离均值（0=稳定/紧致，大=漂移/噪声）。史 <2 → 0。"""
    if len(history) < 2:
        return 0.0
    dists = [
        1.0 - _cosine(history[i], history[i + 1])
        for i in range(len(history) - 1)
    ]
    return sum(dists) / len(dists)


def weak_signal_score(
    cluster_id: str,
    agg_by_day: dict[date, float],
    centroid_history: list[list[float]],
    burst_weight: float,
    today: date,
    config: WeakSignalConfig,
) -> WeakSignalScore:
    """弱信号分：小（agg<ceiling）+ 在加速（v>0）门控；语义稳定 + 突发放大。"""
    agg = agg_by_day.get(today, 0.0)
    velocity = agg - agg_by_day.get(
        today - timedelta(days=config.velocity_window), 0.0)
    drift = centroid_drift(centroid_history)
    is_weak = agg < config.agg_ceiling and velocity > 0.0
    coherence = 1.0 / (1.0 + config.drift_penalty * drift)   # 稳定/紧致 → 高
    score = (
        (velocity + config.burst_coef * burst_weight) * coherence
        if is_weak else 0.0
    )
    return WeakSignalScore(
        cluster_id=cluster_id, is_weak_signal=is_weak, score=score,
        drift=drift, agg=agg, velocity=velocity, burst_weight=burst_weight,
    )


def rank_weak_signals(scores: list[WeakSignalScore]) -> list[WeakSignalScore]:
    """只留弱信号、按分降序（同分 cluster_id 升序，确定性）。"""
    weak = [s for s in scores if s.is_weak_signal]
    weak.sort(key=lambda s: (-s.score, s.cluster_id))
    return weak
