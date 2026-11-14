# COMPOSE-01 · trace

**卡**：⑦计划书——demo 挂上 compose 提交端点，「不挂」的理由已经过期。
**结果**：verified · 1 cycle · 判据 12 条全绿 · **真栈真模型端到端跑通一次**。

## 装载清单

`harness/demo_server.py` · `harness/run_worker.py` · `flint/jobs/worker_main.py`
· `flint/api/compose.py` · `flint/api/app.py#create_app` · `flint/jobs/runner.py`
· `flint/jobs/compose_deps.py` · `flint/compose/llm_generator.py#_parse_blocks`

## 那句注释错在三重，而第三重是真正坏掉的那一件

卡面给的实况是「前提过期」。实查之后发现**过期的比卡面说的还多一层**：

| 原话 | 实况 |
|---|---|
| 「report/proposal 提交端点**刻意不挂**」 | `WIRE-08` 之后这一族由 `create_app` 挂上，**demo 这一侧根本没有挂不挂的选择权**。实测 `/openapi.json` 里 `/projects/{id}/proposal` 与 `/projects/{id}/report` 两条都在 |
| 「demo 无 report worker」 | `harness/run_worker.py` 在，`start-demo.ps1` §3b 每次都起它 |
| 「挂了只会造出永远 queued 的 job」 | **这一句最接近真相，但归因错了** |

第三句的归因错得很贵。真提交一次，回的是：

```
{"code":"FAMILY_NOT_CONFIGURED","family":"analysis",
 "message":"analysis 这一族还没有后端（迁移里没有对应的表），本端点未配置。"}
```

一条打到 **compose** 的请求，回的却是 **analysis 没配**。顺着找下去：

- `create_app(dsn, redis_url=None)` → `_queue_hook(None)` → `_unconfigured("analysis")`；
- 而 `harness/demo_server.py` 调的正是 `create_app(DSN)`——**没给 `redis_url`**。

所以缺的不是 worker，是**队列地址那一个参数**。`flint/api/app.py` 自己写着：
「NEVER 让它默默地不入队：那样作业会永远停在 `queued`，而『队列没配』与
『worker 没起来』在表上长得一模一样」——设计是对的，**demo 这一侧没接**。

> 一句变假的注释比没有注释坏：它把「接线漏了一个参数」讲成了「刻意没做」，
> 于是三个批次里没有人再去碰它。

## 改了什么

1. `create_app(DSN, redis_url=REDIS_URL)`；
2. 新增 `REDIS_URL` 常量，**与 `harness/run_worker.py` 逐字同一行**
   （`os.environ.get("FLINT_REDIS_URL", "redis://localhost:56379/0")`）——
   各写一份的话 API 推 A 队列、worker 守 B 队列，症状与今天一模一样；
3. 三处过期前提改成实况：模块头 · `_enqueue` 的 docstring · 「compose 不挂」那句注释；
4. `_enqueue` 的**抛错文案**也改了（它写着「demo 未挂 compose 提交端点」）——
   这一处是我自己的判据抓出来的，见下。

`flint/jobs/compose.py#_default_generator` **一个字没动**（acceptance⑦）。

## 真栈实跑（本机 qwen3.6:35b-a3b，零 key 零付费）

```
POST /projects/proj-demo-fixture/report  {"analysis_id":"del-demo-fixture-report"}
→ {"job_id":"job-4d22d6be-c3dc-47cf-b334-70a573efb7f4"}

jobs:  queued → drafting → done          （worker 真消费了）
deliverables: 1 → 2                       （新产出 del-job-4d22d6be…）
blocks: 22 个
  [budget]      {"kind":"heading","text":"预算明细","level":2}
  [budget]      "推理算力成本按 GPU 卡时计费，本表记录为 720 卡时。"
  [budget]      "向量库托管成本按实例月计费，本表记录为 12 实例月。"
  [competition] {"kind":"heading","text":"竞品分析","level":2}
  [competition] {"kind":"gap_notice","hints_ref":""}
```

**正文是真句子**，不是 `_default_generator` 那个「标题文字 = section_id」的桩形状。
有一节回的是 `gap_notice`——那是留白，不是编造，正是三条铁律要的姿态。

## 断点一：我的桩不合契约，跑完 0 产出而作业报 `done`

CI 不起 Ollama，所以 §三 用注入的确定性 provider。第一版写的是
`{"blocks":[{"kind":"paragraph", ...}]}`——而 `_parse_blocks` 读的是 **`type`**，
`kind` 那一支走 `continue` 被整块跳过。

实测：**deliverable 建出来了、block 0 个、作业 `done`**。

> 一个不合契约的桩会产出一份空壳并报成功。它比失败坏——失败会喊。

判据因此把「产物有了」与「产物里有东西」**分成两条**：
`assert made` 之后还有 `assert blocks, "产物有了，而一个 block 都没有——那是一份空壳"`。
键名的出处写进了桩自己的注释（逐字指向 `_parse_blocks`），不是我另记一份。

## 断点二：判据抓到的第一个人是我自己

`test_no_stale_claim_is_still_asserted` 第一版是「那几句字面 NEVER 出现」。
它当场红了——**红在我自己新写的注释上**：我把旧话引出来说明它为什么假，
而那正是一条好注释该做的事。

改法不是放宽，是**改判「主张」而不是「字面」**：逐行看，出现旧话的那一行
上下三行内 MUST 有「原先 / 已过期 / 是假的 / 已改」这类过去式记号。

改完之后它又红了一次，这回抓的是**真货**：`_enqueue` 的 `ValueError` 文案里
「demo 未挂 compose 提交端点，故 report 只应来自 regenerate」还在，
且那是一句**运行期会被打印给人看**的话。已改。

> 只禁字面的判据会逼着人把历史抹掉，而抹掉之后没人知道这里曾经为什么不挂。

## 断点三：清理漏了 jobs 的四个引用者

teardown 第一版只删 `jobs`，撞上 `job_steps_job_id_fkey`。
实查 `information_schema`：引用 `jobs` 的有 **job_steps · job_events ·
cluster_verdicts · idempotency_keys** 四张，按序全删。
（同一个教训第二次：红出现在别人的文件里、根因在我这里。）

## 未接上的那一件，如实说

`harness/demo_server.py#_enqueue` **今天没有任何地方调它**——全仓没有一处把它传给
`PgJobRunner(enqueue=...)`。它连带着 demo 那条 gate1 后台派发路径一起是死的。

**没有删它**：它是 demo 面唯一一处写着「gate1 怎么在本机跑起来」的地方，
删掉之后那段接线知识没有第二份。但它的说法已经改成真的，并写明了它不在链路上。
gate1 今天走的是同一条真队列（`dispatch_job` 的分派表），与 report 一样。

## 判据与门

`pytest tests/v041/test_compose_e2e.py -q` → **12 passed**。
全量门留到本批收尾一并跑。
