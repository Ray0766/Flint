"""Kleinberg 突发检测（H-2，读时算、零契约 S2-1）——喂弱信号轨（Phase ③）。

Kleinberg (2002) 两态突发模型的离散日序变体：base 态（速率 λ0=序列均值）/ burst 态（λ1=s·λ0）。
每日代价 = Poisson 负对数似然（丢常数项）`σ_i(x)=λ_i − x·ln λ_i`；转入 burst 付代价 γ。Viterbi DP
求最优态序，burst 态 = 真爆发（速率跃升 = novelty+growth）。**纯读时算**：吃现成 heat_points 的
agg_norm 日序，NEVER 给冻结件加字段（S2-1）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class BurstConfig:
    s: float = 2.0              # burst 速率倍数（λ1 = s·λ0）
    gamma: float = 1.0         # 转入 burst 的代价（越大越抑制边际小爆发）
    min_base: float = 1.0      # λ0 下限（防 ln(0)/空序）
    window_days: int = 7       # 读时回看窗（日）


@dataclass(frozen=True)
class BurstResult:
    states: list[bool]         # 逐日 burst 态（True=突发）
    is_burst_today: bool       # 末日是否突发
    burst_run: int             # 末尾连续突发天数
    peak: float                # 突发区峰值（无突发=0）
    burst_weight: float        # 末尾突发段相对超出强度（Σ max(x/λ0−1,0)），喂弱信号


def detect_burst(values: list[float], config: BurstConfig) -> BurstResult:
    """按时间升序的日值序列 → Kleinberg 两态最优态序 + 突发信号。"""
    n = len(values)
    if n == 0:
        return BurstResult([], False, 0, 0.0, 0.0)
    lam0 = max(sum(values) / n, config.min_base)
    lam1 = config.s * lam0
    ln0, ln1 = math.log(lam0), math.log(lam1)

    def cost(state: int, x: float) -> float:
        return (lam1 - x * ln1) if state else (lam0 - x * ln0)

    # Viterbi：dp[i]=末态 i 的最小累计代价；起始隐含 base，起于 burst 付 γ。
    dp = [cost(0, values[0]), cost(1, values[0]) + config.gamma]
    back: list[list[int]] = [[0, 0] for _ in range(n)]
    for t in range(1, n):
        x = values[t]
        ndp = [math.inf, math.inf]
        for j in (0, 1):
            for i in (0, 1):
                trans = config.gamma if (i == 0 and j == 1) else 0.0
                c = dp[i] + trans + cost(j, x)
                if c < ndp[j]:
                    ndp[j] = c
                    back[t][j] = i
        dp = ndp

    end = 0 if dp[0] <= dp[1] else 1
    states = [False] * n
    s = end
    for t in range(n - 1, 0, -1):
        states[t] = s == 1
        s = back[t][s]
    states[0] = s == 1

    burst_run = 0
    for st in reversed(states):
        if st:
            burst_run += 1
        else:
            break
    peak = max((values[t] for t in range(n) if states[t]), default=0.0)
    burst_weight = sum(
        max(values[t] / lam0 - 1.0, 0.0)
        for t in range(n - burst_run, n)
    ) if burst_run else 0.0
    return BurstResult(
        states=states, is_burst_today=states[-1], burst_run=burst_run,
        peak=peak, burst_weight=burst_weight,
    )


@dataclass(frozen=True)
class BurstSignal:
    cluster_id: str
    is_burst_today: bool
    burst_run: int
    burst_weight: float


def cluster_burst(
    cluster_id: str, agg_by_day: dict[date, float], today: date, config: BurstConfig
) -> BurstSignal:
    """读时算包装：从 agg_by_day（heat_points 派生）按窗口构升序日序 → 突发信号（缺日按 0）。"""
    series = [
        agg_by_day.get(today - timedelta(days=k), 0.0)
        for k in range(config.window_days, -1, -1)
    ]
    r = detect_burst(series, config)
    return BurstSignal(
        cluster_id=cluster_id, is_burst_today=r.is_burst_today,
        burst_run=r.burst_run, burst_weight=r.burst_weight,
    )
