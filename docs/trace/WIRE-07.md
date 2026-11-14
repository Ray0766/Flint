# WIRE-07 · analysis 族三条路由接通

**卡** `docs/steward/tasks-v041-b4.json#WIRE-07` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `AUTH-03`

## 1. 装载清单

卡面 WIRE-07 · `flint/api/app.py` 的 `UNWIRED_FAMILIES` / `_Assembler` / `create_app` ·
`flint/api/analysis.py` 的 `AnalysisApiDeps` 与三个端点 · `flint/authz` ·
`flint/jobs/worker_main.py` 的 `build_enqueue_hook` ·
`harness/demo_server.py` 与 `harness/e2e_stack.py` 的装配段。约 14k tokens，预算 40k 以内。

## 2. 接通了什么

三条路由进 `create_app`：`/projects/{}/analysis` · `/jobs/{}` · `/jobs/{}/events`，
用的是 `AUTH-02` 的**真解析器**与**真归属**（`build_role_resolver` /
`build_owner_scope_for_project`）。`UNWIRED_FAMILIES` 从四族减到三族。

**队列是一条显式的缝**：`create_app(dsn, redis_url=None, queue_name=None)`。
不给 → 入队走既有的 `_unconfigured("analysis")`，提交回 **503 + 点名是哪一族**。
**NEVER 让它默默不入队**：那样作业永远停在 `queued`，
而「队列没配」与「worker 没起来」在 `jobs` 表上长得一模一样。
`queue_name` 也开成缝，是因为端到端夹具每轮用自己的队列——
两条跑在同一条队列上会互相吃对方的作业。

**`ProjectNotFound` → 404**：真归属查不到项目时抛它，不接住就是 500，
而 500 读起来是「服务器坏了」，会让人去翻栈，实际上要做的只是改一个 id。

## 3. 一条判据被自己写的机制咬了三次，都咬对了

接通之后，**七个既有判据同时变红**——它们全是等值判据，钉的是「analysis 还没挂」：

| 判据 | 它原本钉的 |
|---|---|
| `test_app_assembly.py` 的 51→10 | 登记面 10 条 → 现在 7 条 |
| `test_sse_live.py` 两条 | 「SSE **不在**可部署应用上、但登记着」→ 现在反过来 |
| `test_fe_be_parity.py` 的闲置样本 | 拿 `/projects/{}/analysis` 当「仍未挂」的样本 |
| `test_demo_stack_wired.py` 的差集 | demo 多出来的那几族里有 analysis |
| `test_e2e_full_stack.py` 的 `extra_families` | 夹具栈多出来的是 analysis + compose |

`test_fe_be_parity.py` 那条的 docstring 里**自己写着**：
「等那张单结掉、四族接上，本条会因为找不到闲置样本而红，
**那正是提醒来这里把判据改成断言空集的机制**」。它照着自己写的那句话红了。

**这些红不是坏消息，是记账**。每接通一族就要改一次那个数字——
NEVER 把它写成一个范围来省这次改动，范围会让「少挂了一族」也绿。

## 4. 两处 harness 必须停止重复挂 analysis

`create_app` 挂上之后，`harness/demo_server.py` 与 `harness/e2e_stack.py`
里那份自己造的 analysis 就成了**第二份**——`_Assembler` 当场以
`RouteConflictError` 拦下来（它拦得对：并进一个应用后必有一个永远收不到请求）。
两处都删掉自己造的那份。

**连带一处实测**：e2e 夹具原先假设作业 id 由自己的 `id_factory` 给；
analysis 归 `create_app` 之后那个 id 是**服务端**给的，
夹具去队列里找自己那个 id 会找不到。改成**从提交响应里取 job_id**——
本来就该这么写。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_wire_analysis.py -q → 10 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 3971 passed（AUTH-05 收卡时 3961，本卡 +10）
对账器:     backend_not_assembled 10 → **7**（analysis 那三条不再计入）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 三条挂进 `create_app` | `test_the_three_paths_are_mounted` |
| ② 逐条探活：不是 404 / 无权是 403 | `test_every_path_answers_something_other_than_404`、`test_a_user_without_a_role_is_refused_with_403`、`test_the_member_can_read_the_job` 与 `test_the_member_can_subscribe_to_the_stream`（**正例**：没有它们，那些 403 可能是「这条路对谁都拒」换来的）、`test_an_unknown_job_is_404_not_403` |
| ③ 建应用仍不连库 | `test_building_the_app_still_touches_no_database`（把 `asyncpg.connect` 换成一调就炸的桩——真手是**懒的**，第一次查询发生在请求里） |
| ④ 从 `UNWIRED_FAMILIES` 删掉 analysis | `test_analysis_is_gone_from_the_unwired_register`（判**等值**：剩下正好三族） |
| （自加） | 队列那条缝两侧各一条：没给 `redis_url` → 503 且点名 analysis；给了 → 换成真入队钩子 |

**② 改既有文件七处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/api/app.py` | 挂 analysis；加 `redis_url` / `queue_name` 两条缝与 `_queue_hook`；`ProjectNotFound` → 404；`UNWIRED_FAMILIES` 删掉 analysis | **卡上 outputs**，本卡主体 |
| `harness/demo_server.py` · `harness/e2e_stack.py` | 删掉各自那份 analysis 装配 | 见 §4。不删就是 `RouteConflictError`，demo 与 e2e 全起不来 |
| `tests/v041/test_app_assembly.py` · `test_sse_live.py` · `test_fe_be_parity.py` · `test_demo_stack_wired.py` · `test_e2e_full_stack.py` | 等值判据里的数字与集合跟着实况改（§3） | 它们钉的是「analysis 还没挂」。**红了就是提醒来改**——那句话是它们自己写的 |
| `flint/authz/__init__.py` | `from contracts.models import Principal` → `from flint.domain.models import Principal` | 两份同名同形的定义混用时 mypy 判类型不符（接线时当场撞到）；`flint/api/*` 全族引的是 `flint.domain.models` 那一份 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回缺陷态：不挂 analysis | 红 |
| ② 挂了但用假手（人人 owner） | 红 |
| ③ 登记没跟着删（analysis 仍在 `UNWIRED_FAMILIES`） | 红 |
| ④ 队列缝默默不入队（`enqueue=None`） | 红 |
| ⑤ 装配期先查一次库 | 红（2 条） |
| ⑥ 假变异对照：末尾加一行注释 | 全绿 |

**②「挂了但用假手」这一条把判据吊死过两次**，值得记：

1. 第一版拿一条 `queued` 的作业去探 SSE——那条流**不会自己结束**，用例挂住；
2. 改成「只探被拒的那一路」之后，②把它挂了 **600 秒**：假手一放行，
   那次探活就变成订阅一条永不结束的流。**判据在那条变异下不是变红，是吊死**——
   而会吊死的判据比红的更坏：CI 上看不出是断言不过还是环境卡住；
3. 给 `timeout=` 也没用：`TestClient` 的传输在 portal 线程里跑应用，读超时管不到它。

最终解法是让**流本身有终点**：夹具把作业种成 `done`
（`analysis.py` 在 `_TERMINAL` 后收尾），于是放行与拒绝两条路都会返回。

**④** 装载约 14k tokens；**⑤** 禁用词六词 0 命中。

## 6. 登记未做

1. **`AUTH-03` 的身份入口还没接进这三条端点**。它们仍用
   `x_user_id: str = Header()`（缺头 → FastAPI 默认 422，不是 401）。
   接它要动 `flint/api/analysis.py`——**在本卡 outputs 之外**，
   且四族统一换是 `WIRE-11` 收口时更合适的一步。已在 `AUTH-03` trace §6-2 登记。
2. **可部署应用默认不带队列**（`redis_url=None`）。谁来传它是部署面的事；
   `harness/run_worker.py` 那侧已有 `FLINT_REDIS_URL`，两边接起来是另一张卡。
3. **SSE 只探了状态码**。真的订阅一条流、读到事件，是 `test_sse_live.py` 的面。
