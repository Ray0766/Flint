# HOTSPOT-03 · 规格与真件不符：`GET /clusters/{id}/verdict` 并不存在（**已关闭** @2026-08-03）

**状态** closed · 2026-08-03 · `DEC-012`

> 状态：**非阻塞**。卡片两条 acceptance 均已交付并 verified；本单只为 worker.md §1.4
> 「发现矛盾 MUST 上报、NEVER 自行择一后不留痕」而立，等 owner 一句话定端点归属。

## 现象（命令原样输出）

卡片 `tasks-v04.json#HOTSPOT-03` 的 inputs 写着：

```
"inputs": ["api: GET /clusters/{id}/verdict(既有)"]
```

真件里没有这个端点。`flint/api/views.py` 注册的读端点全表：

```
$ python -c "... _routes(create_views_app(...)) ..."
/plaza/hot                              {GET, HEAD}
/clusters/{cluster_id}/evidence-cards   {GET, HEAD}
/jobs/{job_id}/verdict                  {GET, HEAD}
/topics/{topic_id}                      {GET, HEAD}
/projects/{project_id}/topics           {GET, HEAD}
```

判定按 **job 键**落盘（`snapshots.snapshot_id = 'snap-{job_id}-verdict'`），不是 cluster 键。

## 为什么不能自己补一个 cluster 键端点

cluster→判定 的对应关系**当前没有持久化真相**：

- `contracts/models.py#Job`：字段为 `job_id/kind/project_id/owner_scope/state/steps/...`，
  **无 cluster 字段**；
- `contracts/models.py#VerdictResult`：`verdict/all_satisfied/key_citation_ids/
  rationale_fact_ids/competitors/constraints_checked`，**无 cluster_id**；
- `migrations/versions/0002_job_tables.py` 的 `jobs` 表：**无 cluster_id 列**。

要实现 `GET /clusters/{id}/verdict`，只能在这三处之一凭空发明一条对应关系
（例如按 `job_id` 命名约定反查、或按 project 猜）。那正是 K 组纪律禁止的「编造缺口内容」：
一旦猜错，用户看到的是**另一个热点的判定**，而判定是要被引用进计划书的。

## 已试三案

1. **查真件是否已有 cluster 键读法**：`grep -rn "verdict" flint/api` → 只有
   `/jobs/{job_id}/verdict` 一处；`flint/api/pack.py` 的 verdict 是导出闸门，非 Gate①。
2. **查存储层是否有可复用的对应关系**：`grep -rn "cluster_id" migrations/versions/*.py`
   在 jobs/snapshots 两表上无命中。
3. **查冻结件是否允许 additive 补字段**：`Job` 与 `VerdictResult` 均为冻结件实体，
   补 `cluster_id` 属改冻结件（S2-1 NEVER），且 contracts_v04 的 additive 校验也不覆盖
   为「补一条业务对应关系」而加字段的情形。

## 怀疑根因

工单 §5-C 的 C6/C7 用「分析界面」口径叙述（以 cluster 为中心），而 Gate① 的落盘口径
是以 job 为中心；tasks-v04.json 的 inputs 行按前者写，且误标为「既有」。

## 需要 owner 提供什么

二选一（一句话即可，落 `DECISIONS-v04.md`）：

- **甲**：cluster→Gate① job 的对应关系由**调用方（路由层/上层页面）**持有 ——
  维持当前实现，本单关闭；
- **乙**：需要 `GET /clusters/{id}/verdict` —— 则须先定对应关系存哪：
  新表 `cluster_verdict_ref`？还是 `jobs` 加列（触碰既有迁移）？定了才能开卡实现。

## 绕行现状（本卡已交付形态）

- `web/views/analysis/AnalysisView.tsx` 的 `verdictJobId` 由**调用方给出**；
  缺省即渲染「未判定」态，**不发 verdict 请求**（测试第 5 条断言 spy 里无 `/verdict`）。
- 未判定态 NEVER 显示四分类里的任何一个值（测试断言文案不含 `A_/B_/C_/D_`）。
- 后端一侧 `tests/v04/hotspot/test_analysis_view_api.py` 断言这条读路径只跑 SELECT、
  零写路由、判定缺失即 404 而非当场造一个。

---

## 裁决（owner 2026-08-03，DECISIONS-v04.md#DEC-012）

**选甲**：cluster→Gate① 判定的对应关系由**调用方**（路由层/上层页面）持有，
`AnalysisView` 的 `verdictJobId` 入参形态维持不变，本单**关闭**。

**乙案**（真建端点 + 对应关系持久化）登记为 **v0.4.1 候选**，与 §9-P1、§9-P3 同批再议。
在那之前 NEVER 自行开工，也 NEVER 在任何卡里假定该端点存在。
