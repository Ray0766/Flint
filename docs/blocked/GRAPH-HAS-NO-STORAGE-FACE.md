# 图谱没有存储面：`graph_nodes` / `graph_edges` 两张表还没建

**状态** closed · 2026-08-09 · `PERSIST-02`（开单人是 `ENTRY-03`；三张表与 `PgGraphStore` 由 `PERSIST-02` 建）

> **端点已经建好并挂上了**（`POST /workbenches` 回 `graph_id`，幂等，AUTH-03 三种拒绝分开）。
> 挡着的只有一件：**图存在进程内存里，重启就没了。**

## 现象

`flint/graph/store.py` 的 `GraphStore` 是一个 `dict` 两件套。它自己的文件头写着：

```python
"""内存实现；SQL 实现随 E2 的 graph_nodes / graph_edges 两表接入。"""
```

而库里确实没有这两张表（`information_schema` 实测，2026-08-09）：

```
alembic_version · blocks · categories · citations · cluster_centroid_daily · clusters
· degradation_notes · deliverables · doc_contents · docs · edit_events · evidence_cards
· facts · facts_ledgers · generation_records · heat_points · idempotency_keys
· job_events · job_steps · jobs · keywords · lineage_audit · lineage_results
· memberships · orgs · origins · pricebook · pricing_records · profiles · projects
· snapshots · task_specs · topic_seeds · topics · trend_items_raw · users
```

## 后果，说准一点

| 还成立 | 不成立 |
|---|---|
| 入台拿得到 `ok` 与 `graph_id`，人被带去工作台 | 后端重启后那张图**空了** |
| 同一个人对同一个热点重复入台落回同一张图 | 跨进程 / 多副本部署下各算各的 |
| 建出来的图能加边（与 edges 端点共用一个 store） | 边同样不落库 |

`graph_id` 本身**是可复算的**（`blake2b(user_id|cluster_id)`），所以重启后同一个人
再入台会算出**同一个 id**——URL 不会失效，失效的是图里的内容。

## 为什么本卡没有顺手建表

`ENTRY-03` 的 outputs 是 `flint/api/` 与判据文件，**不含 `migrations/`**
（同一批的 `ENTRY-07` outputs 里就明写着 `migrations/versions/`——
可见这一批里哪张卡该动库是分好的）。按 `worker.md` §4.3③ 与本批工单
「改动面大于卡上 outputs → 停下走 `docs/blocked/`」，这里立单而不是自行扩面。

## 缝已经留好了

`WorkbenchDeps.store` 只用到 `GraphStore` 的四个方法
（`nodes` / `edges` / `put_node` / `put_edge`）。换成 SQL 实现时：

1. 建迁移（接号，当时的水位是多少就接多少）：
   `graph_nodes(node_id PK, graph_id, source_kind, source_id, label, position, created_at, primary)`
   · `graph_edges(edge_id PK, graph_id, from_node_id, to_node_id, hypothesis, created_at)`；
2. 写 `PgGraphStore`，四个方法照抄语义；
3. `flint/api/app.py` 里 `graph_store = GraphStore()` 换成 `PgGraphStore(dsn)`。

**端点与判据一行都不用改。**

## 关掉这一单的条件

两张表在、`PgGraphStore` 接上，且重启后同一个 `graph_id` 仍能读回它的节点与边。

---

## 关闭（`PERSIST-02`）

迁移 `0027` 建了 `workbenches` / `graph_nodes` / `graph_edges` 三张表，`flint/graph/pgstore.py#PgGraphStore` 是 `flint/graph/store.py:34` 自述的那个接入，`create_app` 注的对象从内存件换成了它。**端点的存储写法一行没改**——当时留的缝（`WorkbenchDeps.store`）今天兑现了。

两库 `alembic_version = 0027`，八张表 8/8。详见 `docs/trace/PERSIST-02.md`。
