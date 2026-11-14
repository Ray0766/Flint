# HOTSPOT-PHASE1 trace — 搜热点主榜综合分 H-1/H-3/H-5（owner @2026-07-31，读时算零契约）

## 装载清单
- `flint/heat.py`（norm_score 时序原料）、`flint/signals.py`（momentum Δ 口径）、`flint/api/views.py`（plaza 排序）、
  `contracts/models.py#Cluster/HeatPoint`（只读消费，NEVER 改）、`docs/搜热点-升级方案.md`（据其 H-1/H-3/H-5 落地）。

## 决策日志
- **排序哲学（owner 定案）**：主榜=跨源印证（稳/可信）、时间衰减中等、新颖度加分常年热降权。
- **零契约（S2-1）**：`flint/hotness.py` 纯读时算——吃现成 heat_points day 时序 + clusters.first_seen + by_source，
  **NEVER 给 HeatPoint/Cluster 加字段**。综合分 `hotness = base/(age+2)^G · (1+ν·nov) · multi_boost`：
  - 速度 v=agg(today)−agg(today−w_v)、加速度 a 二阶差分（复用 momentum Δ 口径）；
  - HN 型衰减 G=1.6（中等，owner 定案）；新颖度 nov=max(0,1−age/horizon)（复用 first_seen）；
  - **跨源印证（主榜核心）** multi_boost=1+κ·max(0,cross−1)，cross=#{源 norm>θ_cross}（by_source 现成）。
- **参数全临时初值 + 标定通道**（问题单登记，类比 θ_rel/δ，NEVER report_only 关约束）。
- **plaza 换排序**：`views.py /plaza/hot` 由 Σnorm 静态快照 → 取回看窗口（window_days=7）算综合分降序；
  保留 total_heat(=agg)/by_source 展示，新增 hotness + 分量。仅当日有热度点的簇入主榜。

## 落盘
- 新增 `flint/hotness.py`（HotnessConfig/ClusterSeries/compute_hotness/rank_hotness）、`tests/m1/test_hotness.py`（6 绿：
  跨源排前单源靠后/速度+加速度/衰减+新颖度/缺日按0/分量暴露/参数可调非report_only）。
- 改 `flint/api/views.py`（plaza 换综合分排序）、`tests/fe_views/test_read_endpoints.py`（+跨源印证端点测；原测保持绿——
  同龄同agg小norm数据下综合分保序、total_heat=agg 不破）。问题单登记标定通道 + 排序哲学定案 + Phase ②③ 待建。
- verify：ruff 净 · mypy --strict 233 文件净 · S2-8 净 · hotness 6 + fe_views 5 = 11 绿。**未改冻结件**（contracts 只读）；
  **未改依赖锁**；零联网零付费（纯计算 + 本地 PG 种子）；**DAG**：owner 授权 tasks.json 外，无对账/H-3。

## 返工记录
- test 跨源门槛 norm>60 严格大于：测试用 60.0 不算冒头 → 改 62.0（真>60）。
- views.py 迭代 dict 用 .items()（ruff PLC0206）。
