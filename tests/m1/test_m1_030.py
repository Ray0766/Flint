"""M1-030 acceptance tests: HeatPoint writes + per-source 90-day percentile norm.

Acceptance (tasks.json M1-030):
  - raw values are not comparable across sources (type-layer assertion)
  - percentile golden cases pass
"""
from __future__ import annotations

import asyncio
import os
from datetime import date, timedelta
from typing import Any

import asyncpg
import pytest

from flint.domain.models import HeatPoint
from flint.heat import (
    CrossSourceMixError,
    RawHeatObservation,
    build_heat_points,
    percentile_norm,
    write_heat_points,
)

DAY = date(2026, 7, 23)
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


# ── percentile golden cases ───────────────────────────────

GOLDEN = [
    # (value, window, expected 0~100)
    (40.0, [10.0, 20.0, 30.0, 40.0], 100.0),
    (10.0, [10.0, 20.0, 30.0, 40.0], 25.0),
    (25.0, [10.0, 20.0, 30.0, 40.0], 50.0),
    (5.0, [10.0, 20.0, 30.0, 40.0], 0.0),
    (30.0, [30.0, 30.0, 30.0], 100.0),
    (55.0, [float(i) for i in range(1, 91)], 55.0 / 90.0 * 100.0),
    (7.7, [], 100.0),  # first-ever observation is its own ceiling
]


@pytest.mark.parametrize(("value", "window", "expected"), GOLDEN)
def test_percentile_golden_cases(
    value: float, window: list[float], expected: float
) -> None:
    assert percentile_norm(value, window) == pytest.approx(expected)


# ── 90-day window + build ─────────────────────────────────


def history(source_id: str, days_values: list[tuple[int, float]]) -> list[RawHeatObservation]:
    return [
        RawHeatObservation(
            source_id=source_id, cluster_id="c-1", day=DAY - timedelta(days=d), raw_value=v
        )
        for d, v in days_values
    ]


def test_window_excludes_older_than_90_days() -> None:
    obs = RawHeatObservation("gtrends", "c-1", DAY, 10.0)
    hist = history("gtrends", [(1, 20.0), (90, 30.0), (91, 999.0), (120, 999.0)])
    points = build_heat_points([obs], hist)
    # window = {20, 30}: both above 10 -> percentile 0
    assert points == [
        HeatPoint(cluster_id="c-1", source_id="gtrends", day=DAY, raw_value=10.0, norm_score=0.0)
    ]


def test_norm_is_per_source_not_global() -> None:
    obs_a = RawHeatObservation("gtrends", "c-1", DAY, 50.0)
    obs_b = RawHeatObservation("weibo", "c-1", DAY, 50.0)
    hist = history("gtrends", [(1, 10.0), (2, 20.0)]) + history(
        "weibo", [(1, 100.0), (2, 200.0)]
    )
    points = build_heat_points([obs_a, obs_b], hist)
    by_source = {p.source_id: p for p in points}
    assert by_source["gtrends"].norm_score == pytest.approx(100.0)
    assert by_source["weibo"].norm_score == pytest.approx(0.0)


# ── cross-source type-layer assertion ─────────────────────


def test_cross_source_raw_values_not_comparable() -> None:
    obs = RawHeatObservation("gtrends", "c-1", DAY, 10.0)
    mixed_history = history("weibo", [(1, 20.0)])
    with pytest.raises(CrossSourceMixError):
        build_heat_points([obs], mixed_history, strict_sources=["gtrends"])


def test_observation_source_outside_declared_set_rejected() -> None:
    obs = RawHeatObservation("tiktok", "c-1", DAY, 10.0)
    with pytest.raises(CrossSourceMixError):
        build_heat_points([obs], [], strict_sources=["gtrends", "weibo"])


# ── DB write ──────────────────────────────────────────────


@pytest.mark.compose
def test_write_heat_points_idempotent() -> None:
    def run(coro: Any) -> Any:
        return asyncio.run(coro)

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM heat_points WHERE cluster_id = 'm1030-c'")
        finally:
            await conn.close()

    run(wipe())
    points = [
        HeatPoint("m1030-c", "gtrends", DAY, 42.0, 77.5),
        HeatPoint("m1030-c", "weibo", DAY, 9000.0, 12.5),
    ]
    run(write_heat_points(DSN, points))
    run(write_heat_points(DSN, points))  # idempotent re-run

    async def count() -> int:
        conn = await asyncpg.connect(DSN)
        try:
            value: int = await conn.fetchval(
                "SELECT count(*) FROM heat_points WHERE cluster_id = 'm1030-c'"
            )
            return value
        finally:
            await conn.close()

    assert run(count()) == 2
