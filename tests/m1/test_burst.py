"""Kleinberg 突发检测（H-2，读时算零契约）——从 heat_points day 时序检 novelty+growth 爆发。

两态（base/burst）代价模型 + Viterbi 最优态序；突发态代价换（转上态付 γ）。喂弱信号轨（Phase ③）。
纯单测（合成日序），零 DB/零联网。
"""
from __future__ import annotations

from datetime import date, timedelta

from flint.burst import BurstConfig, cluster_burst, detect_burst

CFG = BurstConfig()
TODAY = date(2026, 7, 26)


def test_flat_series_no_burst() -> None:
    # 平稳（历来 50）→ 无突发。
    r = detect_burst([50.0, 50.0, 50.0, 50.0, 50.0], CFG)
    assert not any(r.states) and not r.is_burst_today and r.burst_run == 0


def test_spike_series_bursts_at_high_days() -> None:
    # 低位后跃升（10→10→10→90→95）→ 末两日突发态。
    r = detect_burst([10.0, 10.0, 10.0, 90.0, 95.0], CFG)
    assert r.states[-1] and r.states[-2]              # 末两日 burst
    assert not r.states[0]                            # 首日 base
    assert r.is_burst_today and r.burst_run == 2


def test_burst_ended_before_today_not_today() -> None:
    # 爆发在中段、今日已回落（10→90→95→10→10）→ 今日非突发、burst_run=0。
    r = detect_burst([10.0, 90.0, 95.0, 10.0, 10.0], CFG)
    assert not r.is_burst_today and r.burst_run == 0
    assert any(r.states)                             # 中段确有突发


def test_gamma_higher_suppresses_marginal_burst() -> None:
    # 转态代价 γ↑ → 边际小爆发被抑制：单日 80 尖峰，低 γ 判 1 段突发、高 γ 抑成 0（差异抑制）。
    series = [40.0, 40.0, 40.0, 80.0, 40.0]
    loose = detect_burst(series, BurstConfig(gamma=0.5))
    strict = detect_burst(series, BurstConfig(gamma=8.0))
    assert sum(loose.states) == 1 and sum(strict.states) == 0   # γ↑ 真抑掉边际爆发
    assert sum(strict.states) < sum(loose.states)


def test_short_and_empty_series_safe() -> None:
    assert detect_burst([], CFG).states == []
    assert detect_burst([70.0], CFG).burst_run in (0, 1)  # 单点不炸


def test_cluster_burst_from_agg_by_day() -> None:
    # 读时算包装：从 agg_by_day（heat_points 派生）按窗口构日序 → 突发信号。
    agg = {TODAY - timedelta(days=k): 10.0 for k in range(4, 0, -1)}
    agg[TODAY] = 95.0
    agg[TODAY - timedelta(days=1)] = 90.0
    sig = cluster_burst("c1", agg, TODAY, CFG)
    assert sig.cluster_id == "c1" and sig.is_burst_today
    assert sig.burst_weight > 0.0                    # 突发强度>0（喂弱信号）
