"""HeatPoint 写入与源内 90 天分位归一（M1-030，PDD v0.2 §3.3 / A2）。

- 各源 raw_value 单位互不可比（Trends 相对值 / GitHub star 增量 / 微博序数 /
  arXiv 计数）——归一只在**同源**历史窗口内进行；跨源混入抛
  CrossSourceMixError（类型层断言，验收硬条款）。
- norm_score = 90 天窗口内 <= 当日值的占比 × 100（0~100）；空窗口（首日）
  = 100.0（自身即天花板，随窗口积累回落）。
- 「综合热度」派生加权属展示层（§3.3 derived 标注），本模块不做跨源合成。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import asyncpg

from flint.domain.models import HeatPoint

WINDOW_DAYS = 90


class CrossSourceMixError(TypeError):
    """Raised when raw heat values from different sources are mixed."""


@dataclass(frozen=True)
class RawHeatObservation:
    source_id: str
    cluster_id: str
    day: date
    raw_value: float


def percentile_norm(value: float, window_values: list[float]) -> float:
    if not window_values:
        return 100.0
    at_or_below = sum(1 for v in window_values if v <= value)
    return 100.0 * at_or_below / len(window_values)


def build_heat_points(
    observations: list[RawHeatObservation],
    source_history: list[RawHeatObservation],
    strict_sources: list[str] | None = None,
) -> list[HeatPoint]:
    """Normalize each observation against ITS OWN source's trailing 90-day
    history. strict_sources declares the allowed source set; any observation or
    history row outside it (or history from a source with no matching
    observation source) trips the cross-source guard."""
    if strict_sources is not None:
        allowed = set(strict_sources)
        offenders = {
            o.source_id
            for o in [*observations, *source_history]
            if o.source_id not in allowed
        }
        if offenders:
            raise CrossSourceMixError(
                f"raw heat values are per-source; got undeclared sources: "
                f"{sorted(offenders)} (allowed: {sorted(allowed)})"
            )
        observed_sources = {o.source_id for o in observations}
        stray = {h.source_id for h in source_history} - observed_sources
        if stray:
            raise CrossSourceMixError(
                f"history from sources without observations mixed in: {sorted(stray)}"
            )

    points: list[HeatPoint] = []
    for obs in observations:
        window = [
            h.raw_value
            for h in source_history
            if h.source_id == obs.source_id
            and h.cluster_id == obs.cluster_id
            and 0 < (obs.day - h.day).days <= WINDOW_DAYS
        ]
        points.append(
            HeatPoint(
                cluster_id=obs.cluster_id,
                source_id=obs.source_id,
                day=obs.day,
                raw_value=obs.raw_value,
                norm_score=percentile_norm(obs.raw_value, window),
            )
        )
    return points


async def write_heat_points_on(conn: asyncpg.Connection, points: list[HeatPoint]) -> None:
    """Connection-scoped variant: caller owns the transaction boundary."""
    await conn.executemany(
        "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, norm_score) "
        "VALUES ($1, $2, $3, $4, $5) "
        "ON CONFLICT (cluster_id, source_id, day) DO UPDATE SET "
        "raw_value = EXCLUDED.raw_value, norm_score = EXCLUDED.norm_score",
        [
            (p.cluster_id, p.source_id, p.day, p.raw_value, p.norm_score)
            for p in points
        ],
    )


async def write_heat_points(dsn: str, points: list[HeatPoint]) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.executemany(
            "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, norm_score) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (cluster_id, source_id, day) DO UPDATE SET "
            "raw_value = EXCLUDED.raw_value, norm_score = EXCLUDED.norm_score",
            [
                (p.cluster_id, p.source_id, p.day, p.raw_value, p.norm_score)
                for p in points
            ],
        )
    finally:
        await conn.close()
