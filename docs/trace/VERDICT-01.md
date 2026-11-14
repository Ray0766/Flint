# VERDICT-01 · trace

**卡**：⑥热点分析——判定要真的落库（`cluster_verdicts` 今天 0 行）。
**结果**：verified · 1 cycle · 判据 13 条全绿。
**诊断结论**：卡面给了两种可能，**实查的答案是第三种**。

## 装载清单

`flint/jobs/gate1.py`（`run_gate1` 签名 · 760 行那句 if · `build_offline_deps` / `build_live_deps`）
· `flint/jobs/cluster_verdict.py`（`clusters_for_topic` 四跳 · `record_cluster_verdicts`）
· `flint/api/analysis.py:175` · `flint/jobs/worker_main.py#_gate1_handler`
· `harness/run_worker.py` · `harness/demo_server.py#_enqueue` · `flint/repo/cluster_verdict.py`

## 诊断：不是①也不是②，是**消费侧把它丢了**

| 卡面猜测 | 实查 |
|---|---|
| ① 那 8 条的 payload 本来就没有 `topic_id` | **不成立**。`flint/api/analysis.py:175` 逐字写着 `"topic_id": body.topic_id` |
| ② 带了但 `clusters_for_topic` 回空 | **不是主因**。四跳本身是通的（本卡种一条真链验过） |
| **③ 带了，而消费侧没往下传** | **就是这个** |

那 8 条走的是 `harness/demo_server.py#_enqueue`：

```python
keywords = [str(k) for k in payload.get("keywords", [])]
locale = str(payload.get("locale", "zh-CN"))
await run_gate1(job_id, keywords, locale, deps)      # ← topic_id 没传
```

它从 payload 里取 `keywords`，**而 `topic_id` 就在旁边、没人取**。
于是 `run_gate1(topic_id=None)`，`gate1.py:760` 那句
`if topic_id is not None:` **一次都没走到**。

**没有任何一处会报错**：作业 `done`、判定快照写了、claims 也写了——
只有「这次判的是哪几条热点」这一层关系静静地没建。
`cluster_verdicts` 0 行不是「判定失败」，是「判定成功而无人记它判了谁」。

> `run_gate1` 把 `topic_id` 放在参数表最后并给默认值 `None`，
> 是 `PERSIST-04` 刻意为之（既有调用点一个都不用改）。
> 代价正是今天这一幕：**漏传不报错**。这不是设计错，是这种设计的已知代价——
> 而付账的方式只能是判据。本卡因此把「消费侧传没传」写成了两条判据。

## 第二个坑：真 worker 上 gate1 今天根本跑不起来

`_enqueue` 已经没有调用点（`COMPOSE-01` 实查）。真路径是
`run_worker.py` → `worker_main._gate1_handler`——**那个 handler 是传 `topic_id` 的**
（`worker_main.py:180` 逐字 `topic_id=topic_id`）。

但 `run_worker.py` 造 `WorkerDeps` 时**没注 `gate1_deps`**，
于是每条 `gate1_analysis` 都以 `HandlerDepsMissing` 收场。

也就是说今天这条链是：**旧路能跑但丢参数 → 新路参数对但跑不起来**。
两头都不通，而屏上只会说「还没有判定」。

**改**：`run_worker.build_deps()` 注入 `gate1_deps=build_live_deps(...)`，
provider 与组稿共用同一个 `LocalProvider`（免费本地档，零 key）。

## 真实网络：接线了，**没有实跑**

`build_live_deps` 的 searcher 打的是真实 github / arxiv。
本批的真实网络授权（`DEC-052`）**只覆盖 CN-07**，VERDICT-01 不在其中——
所以这一卡**只接线，一发真实请求都没有发**：

- 判据全部离线（种数据 + 直接调 `clusters_for_topic` / `record_cluster_verdicts`）；
- demo 面按下「发起分析」时会去打 github/arxiv，那是 `build_live_deps` 的既有口径、
  是 owner 自己按下去时发生的事，与本卡在这一轮里做过什么无关；
- **端到端那一跑因此没有做**（acceptance③ 的「真栈跑一遍」这一半）。
  要做的话得先有 `DEC-052` 那样的窗口授权——留给 owner。

## 判据里踩到的四处（都是我，逐条）

| 踩到什么 | 真相 |
|---|---|
| `origins.owner` / `jobs.initiated_by` NOT NULL | 种数据漏列 |
| `topic_seeds` 没有 `created_at`、`topics` 没有 `title` | **列名是我编的**。编列名的红会落在 SQL 上，而不是被判的那件事上 |
| `topics.why_now` 是 `jsonb` 不是 `text` | 同上 |
| **`card_ids` 装的是证据卡 id，不是簇 id** | 第四跳拿 `card_ids` 去 `evidence_cards` 换簇。直接塞簇 id 进去 → 那一跳查不到 → 回 `[]`，**而那与「关系没建」长得一模一样**——差点把自己的种数据错误当成产品缺陷 |
| `latest_verdict_job(DSN, ...)` | 它吃**连接**不吃 DSN。传 DSN 会在它内部 `AttributeError`，而那与「这个热点没判过」是两回事 |

那条 `card_ids` 的教训写进了 fixture 的注释里（不是只写在这份 trace）：
下一个种这条链的人会先读到它。

## 阴性对照（acceptance⑤）

不带 `topic_id` 的分析 → `cluster_verdicts` **一行不写**，判据断言它为空；
并另有一条判据守住「屏上『还没有判定』与『这次判定没记热点』NEVER 共用一句话」
（两者该让用户做的事完全不同：一个等作业跑完，一个刷新一万次也不会变）。

## 本卡没碰判定逻辑（acceptance④）

四分类与引用照旧走 `flint/gate/`。判据钉的是**依赖方向**：
`flint/jobs/cluster_verdict.py` 里 NEVER 出现 `from flint.gate`，
也 NEVER 出现 `verdict_class` / `all_satisfied`——关系层只写关系。

## 判据

`pytest tests/v041/test_verdict_lands.py -q` → **13 passed**。
全量门留到本批收尾一并跑。
