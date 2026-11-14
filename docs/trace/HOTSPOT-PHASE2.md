# HOTSPOT-PHASE2 trace — Kleinberg 突发检测 H-2（owner @2026-07-31，读时算零契约）

## 装载清单
- `flint/hotness.py`（agg_by_day 口径）、`flint/heat.py`（norm 时序原料）、`docs/搜热点-升级方案.md#H-2`。

## 决策日志
- **Kleinberg (2002) 两态离散日序变体**：base 态 λ0=序列均值、burst 态 λ1=s·λ0（s 初值 2.0）；
  每日代价 = Poisson 负对数似然（丢常数）`σ_i(x)=λ_i−x·ln λ_i`；转入 burst 付 γ（初值 1.0，越大越抑边际爆发）。
  Viterbi DP 求最优态序，burst 态 = 真爆发（速率跃升 = novelty+growth）。
- **纯读时算、零契约（S2-1）**：吃现成 heat_points agg_norm 日序，`cluster_burst` 从 agg_by_day 按窗构升序序（缺日按 0），
  **NEVER 给 HeatPoint/Cluster 加字段**。输出 `BurstSignal`（is_burst_today/burst_run/burst_weight）**喂弱信号轨（Phase ③）**——
  本阶段只出算法+信号，NEVER 接 plaza（弱信号轨的呈现属 Phase ③）。
- 参数（s/γ/min_base/window）临时初值，标定随主榜一并入通道（问题单）。

## 落盘
- 新增 `flint/burst.py`（BurstConfig/BurstResult/detect_burst/BurstSignal/cluster_burst）、`tests/m1/test_burst.py`（6 绿：
  平稳无突发/跃升末段突发/中段突发今日非/γ↑抑边际（单调）/短空序安全/cluster_burst 包装出强度）。
- verify：ruff 净 · mypy --strict 234 文件净 · S2-8 净 · m1 356 绿（含 burst 6）。**未改冻结件**；**未改依赖锁**；
  纯 stdlib（math/dataclasses/datetime）；零联网零付费。**DAG**：owner 授权 tasks.json 外，无对账/H-3。

## 返工记录
- 无（一次通过）。
