"""弱信号早期轨（H-4，bge-m3 质心漂移 + 小而在加速 + 突发）——BERTrend/Snapchat 路线。

单列一轨（Phase ③），NEVER 混主榜。纯单测（合成质心序 + agg 序 + burst 强度），零 DB/零联网。
"""
from __future__ import annotations

from datetime import date, timedelta

from flint.weaksignal import (
    WeakSignalConfig,
    centroid_drift,
    rank_weak_signals,
    weak_signal_score,
)

TODAY = date(2026, 7, 26)
CFG = WeakSignalConfig()


def _agg(today_val: float, prev_val: float) -> dict[date, float]:
    return {TODAY: today_val, TODAY - timedelta(days=1): prev_val}


def test_centroid_drift_stable_vs_moving() -> None:
    same = [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]]
    moving = [[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]]
    assert centroid_drift(same) == 0.0
    assert centroid_drift(moving) > 0.5
    assert centroid_drift([[1.0, 0.0]]) == 0.0          # 单点无漂移


def test_small_rising_coherent_is_weak_signal() -> None:
    # 小（agg 20<ceiling）+ 在加速（20>0）+ 语义稳定（漂移0）+ 有突发 → 弱信号。
    s = weak_signal_score("c1", _agg(20.0, 5.0), [[1.0, 0.0], [1.0, 0.0]],
                          burst_weight=1.0, today=TODAY, config=CFG)
    assert s.is_weak_signal and s.score > 0.0 and s.velocity == 15.0


def test_large_agg_is_not_weak_signal_belongs_to_main_board() -> None:
    # agg 高于 ceiling（80）= 主榜料、非弱信号（NEVER 混主榜的反向：主榜料不进弱信号轨）。
    s = weak_signal_score("big", _agg(80.0, 10.0), [[1.0, 0.0], [1.0, 0.0]],
                          burst_weight=1.0, today=TODAY, config=CFG)
    assert not s.is_weak_signal and s.score == 0.0


def test_flat_or_falling_not_weak_signal() -> None:
    flat = weak_signal_score("f", _agg(20.0, 20.0), [[1.0, 0.0]], 0.0, TODAY, CFG)
    falling = weak_signal_score("d", _agg(15.0, 30.0), [[1.0, 0.0]], 0.0, TODAY, CFG)
    assert not flat.is_weak_signal and not falling.is_weak_signal  # 不在加速


def test_high_drift_downweights_vs_coherent() -> None:
    # 同小同加速同突发，语义漂移高（噪声）→ 分低于语义稳定。
    coherent = weak_signal_score("coh", _agg(20.0, 5.0), [[1.0, 0.0], [1.0, 0.0]],
                                 1.0, TODAY, CFG)
    noisy = weak_signal_score("noise", _agg(20.0, 5.0), [[1.0, 0.0], [0.0, 1.0]],
                              1.0, TODAY, CFG)
    assert coherent.score > noisy.score and noisy.is_weak_signal


def test_rank_weak_signals_excludes_non_weak_and_orders_by_score() -> None:
    a = weak_signal_score("a", _agg(20.0, 5.0), [[1.0, 0.0], [1.0, 0.0]], 2.0, TODAY, CFG)
    b = weak_signal_score("b", _agg(25.0, 20.0), [[1.0, 0.0], [1.0, 0.0]], 0.0, TODAY, CFG)
    big = weak_signal_score("big", _agg(90.0, 5.0), [[1.0, 0.0]], 5.0, TODAY, CFG)
    ranked = rank_weak_signals([b, big, a])
    assert [s.cluster_id for s in ranked] == ["a", "b"]    # big 排除（非弱信号）、a>b
