"""搜热点主榜综合分（H-1/H-3/H-5，读时算、零契约 S2-1）。

排序哲学（owner @2026-07-31 定案）：**主榜 = 跨源印证**（稳/可信优先），**时间衰减中等**，
新颖度加分、常年热降权。五法之主榜三法在此**读时算**（吃现成 heat_points day 时序 + lineage
first_seen + by_source），NEVER 给冻结件加字段。

综合分（HN 型衰减）：
  base   = w_agg·agg + w_velocity·max(v,0) + w_accel·max(a,0)      # 高度 + 速度 + 加速度
  v      = agg(today) − agg(today−velocity_window)                 # 速度（复用 momentum Δ 口径）
  a      = v(today) − v(today−accel_window)                        # 加速度（二阶差分）
  decay  = (age_days + 2) ^ gravity                                # HN (P-1)/(T+2)^G，G 中等
  nov    = max(0, 1 − age_days/novelty_horizon)                    # 新颖度：新簇加分、常年热降权
  cross  = #{源: by_source_today[源] > cross_source_norm_min}      # 跨源印证：多源同时冒头
  boost  = 1 + cross_source_weight·max(0, cross−1)                 # 主榜核心：跨源排前、单源靠后
  hotness = base / decay · (1 + novelty_weight·nov) · boost

参数一律**临时初值**（标定通道见 docs/v0.4-问题单.md，类比 θ_rel/δ）；**NEVER report_only 关约束**。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class HotnessConfig:
    velocity_window: int = 1        # w_v：速度窗（日）
    accel_window: int = 1           # w_a：加速度窗（日）
    gravity: float = 1.6            # G：HN 衰减指数（中等，owner 1.5~1.8）
    w_agg: float = 1.0              # α：高度权
    w_velocity: float = 0.6         # β：速度权
    w_accel: float = 0.3            # γ：加速度权
    novelty_weight: float = 0.4     # ν：新颖度权
    novelty_horizon: int = 14       # 新颖度地平线（日）
    cross_source_norm_min: float = 60.0   # θ_cross：算"冒头"的单源 norm 下限
    cross_source_weight: float = 0.5      # κ：跨源印证权（主榜核心）
    window_days: int = 7            # 读时取 heat_points 的回看窗（日）


@dataclass(frozen=True)
class ClusterSeries:
    """一簇的读时算输入（全部来自现成表，NEVER 冻结件加字段）。"""

    cluster_id: str
    first_seen: date                # clusters.first_seen
    agg_by_day: dict[date, float]   # agg_norm(d)=Σ源 norm_score(d)，来自 heat_points
    by_source_today: dict[str, float]  # 当日每源 norm_score，来自 heat_points（API by_source）


@dataclass(frozen=True)
class HotnessScore:
    total: float
    agg: float
    velocity: float
    accel: float
    decay_divisor: float
    novelty_factor: float
    multi_boost: float
    cross_count: int


def compute_hotness(
    series: ClusterSeries, today: date, config: HotnessConfig
) -> HotnessScore:
    agg_by_day = series.agg_by_day

    def agg_on(d: date) -> float:
        return agg_by_day.get(d, 0.0)              # 缺日按 0（首现即真爆发，不炸）

    agg = agg_on(today)
    velocity = agg - agg_on(today - timedelta(days=config.velocity_window))
    v_prev = (
        agg_on(today - timedelta(days=config.accel_window))
        - agg_on(today - timedelta(days=config.accel_window + config.velocity_window))
    )
    accel = velocity - v_prev

    age_days = max(0, (today - series.first_seen).days)
    decay = float((age_days + 2) ** config.gravity)
    novelty_factor = max(0.0, 1.0 - age_days / config.novelty_horizon)

    cross_count = sum(
        1 for n in series.by_source_today.values() if n > config.cross_source_norm_min
    )
    multi_boost = 1.0 + config.cross_source_weight * max(0, cross_count - 1)

    base = (
        config.w_agg * agg
        + config.w_velocity * max(velocity, 0.0)
        + config.w_accel * max(accel, 0.0)
    )
    total = base / decay * (1.0 + config.novelty_weight * novelty_factor) * multi_boost
    return HotnessScore(
        total=total, agg=agg, velocity=velocity, accel=accel,
        decay_divisor=decay, novelty_factor=novelty_factor,
        multi_boost=multi_boost, cross_count=cross_count,
    )


def rank_hotness(
    series: list[ClusterSeries], today: date, config: HotnessConfig
) -> list[ClusterSeries]:
    """按综合分降序；同分按 cluster_id 升序（确定性）。"""
    scored = [(s, compute_hotness(s, today, config)) for s in series]
    scored.sort(key=lambda item: (-item[1].total, item[0].cluster_id))
    return [s for s, _ in scored]
