# HOTSPOT-PHASE3 trace — 弱信号早期轨 H-4（owner @2026-07-31，新内部表 + bge-m3 漂移）

## 装载清单
- `flint/burst.py`（Phase ② burst_weight）、`flint/hotness.py`（agg_by_day 口径）、`flint/api/views.py`（plaza）、
  `flint/jobs/ingest.py`（heat_signals 步）、`contracts/models.py#Cluster`（只读，NEVER 改）、`migrations/versions/0017`（接号）。

## 决策日志
- **S9 契约面（owner 授权走新内部表、NEVER 改冻结 Cluster）**：弱信号须每日簇质心历史，冻结 `Cluster.centroid`
  只存当前。新表 **`cluster_centroid_daily`（迁移 0018，接 0017 后）**：(day, cluster_id, centroid vector(1024))，PK(day,cluster_id)。
- **weaksignal.py（读时算、零依赖 stdlib）**：BERTrend/Snapchat 路线——早期抓"**小而在加速**"的语义新趋势：
  agg<ceiling（小）+ velocity>0（在加速）门控；`coherence=1/(1+drift·penalty)`（bge-m3 质心低漂移=真成形，高漂移=噪声降权）；
  突发 burst_weight 放大。`score=(velocity+burst_coef·burst_weight)·coherence`（非弱信号=0）。`rank_weak_signals` 只留弱信号降序。
- **plaza 单列一轨（NEVER 混主榜）**：`/plaza/hot` 响应加 `weak_signals`（与 `clusters` 主榜分开）；取窗口内每日质心
  （cluster_centroid_daily）算漂移 + agg_by_day + cluster_burst → 弱信号轨。大 agg 簇只在主榜、不进弱信号轨（测断言）。
- **ingest 写（heat_signals 步、事务内、幂 upsert）**：`PgCentroidDailyStore.snapshot_from_clusters_on` 把当日热点簇质心
  从 clusters **INSERT...SELECT** 直拷进快照表（无向量文本往返）；resume 幂等（ingest 16 测含 diff-empty 绿）。

## 落盘
- 新增 `migrations/versions/0018_cluster_centroid_daily.py`（applied，alembic head 0018 线性）、`flint/weaksignal.py`、
  `flint/repo/centroid_daily.py`、`tests/m1/test_weaksignal.py`（6）、`tests/m1/test_centroid_daily.py`（2）。
- 改 `flint/api/views.py`（weak_signals 轨）、`flint/jobs/ingest.py`（heat_signals 快照写）、`tests/fe_views/test_read_endpoints.py`
  （+弱信号轨端点测、+cluster_centroid_daily wipe）。问题单登记 burst/weaksignal 标定 + 新表说明。
- verify：ruff 净 · mypy --strict 236 文件净 · S2-8 净 · m1+fe_views+m4 ledger **383 绿**（weaksignal 6/centroid_daily 2/
  fe_views 弱信号轨 1/ingest 16 含 diff-empty）。**未改冻结 Cluster/HeatPoint**（只加内部表）；**未改依赖锁**；零联网零付费；
  台账 malformed=[]。**DAG**：owner 授权 tasks.json 外，无卡增删；migration 链 0017→0018 线性 head 一致（迁移对账）。

## 返工记录
- 无（store 由 save/history 早稿重构为 snapshot_from_clusters_on 单法，避免死代码；plaza 读走内联窗口查询）。
