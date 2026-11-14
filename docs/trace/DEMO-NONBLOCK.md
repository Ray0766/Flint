# DEMO-NONBLOCK trace — 修 demo 后端「点生成就冻死」（阻塞事件循环）@2026-08-01

## 装载清单
- `flint/llm/local.py`（LocalProvider：冻结 LLMProvider 协议 = **同步** generate/generate_structured，httpx.Client）、
  `flint/api/combo.py`（combo handler → orchestrate_combo）、`flint/topic/orchestrate.py`（sync 纯计算）、
  `flint/jobs/gate1.py`（run_gate1 async orchestrator + _plan_queries/_judge_payload/_validate_verdict sync 相位）、
  `harness/demo_server.py`（_gate1_enqueue：asyncio.create_task 后台跑 run_gate1）、`flint/api/views.py`（连接开闭复查）、
  `tests/topic/test_ts_010_combo_api.py`（复用合成 provider/DB 装置）。

## 根因
LLMProvider 冻结协议本就**同步**（`generate`/`generate_structured` 非 async，内部同步 httpx.Client，超时 600s）。
一次 combo 生成（orchestrate_combo → 逐主题 generate_structured）或 gate1 判官（_judge_payload/_validate_verdict）
**~75s 的同步调用直接跑在 async handler / 后台 asyncio.create_task（同一事件循环）里 → 阻塞整个事件循环**。
期间所有并发请求（`/plaza`、`/clusters/.../evidence-cards`…）无法被服务 → 前端 `Failed to fetch`。
注：gate1 虽走 `asyncio.create_task`「后台」，但 create_task 只是排协程到**同一 loop**，协程内的裸同步调用照样憋死 loop。

## 修法（冻结件不动，只动调用点：同步活挪出事件循环）
- **combo**（`flint/api/combo.py`）：`result = await run_in_threadpool(orchestrate_combo, ...)`（starlette.concurrency）。
  orchestrate_combo 是同步纯计算（provider + DeterministicHash embed，无 asyncpg），整块进线程池；周边 async DB 存取留在 loop。
- **gate1**（`flint/jobs/gate1.py` run_gate1）四处同步 provider/searcher 全 `await run_in_threadpool(...)`：
  ① `_plan_queries`（query builder 调 provider）；② 新增 `_collect_docs`（retrieve 相位逐 query 调同步 searcher 去重收集）；
  ③ `_judge_payload`（relevance/competitor 抽取，调 provider + searcher）；④ `_validate_verdict`（对齐 aligner，调 provider）。
  **asyncpg 异步 DB（_enter_state/_put_snapshot/_record_step/事务）全留在 loop**——sync 只在这四个纯计算相位，无 DB 交织。
- **demo_server 后台 task**：`_gate1_enqueue` 的 `asyncio.create_task(run_gate1...)` 无需改——run_gate1 内部已把同步活threadpool 出去，后台 job 自动受益。
- **views.py 连接复查**（owner 顺带项）：plaza/workbench/gate_verdict 均 `connect()` → `try: ... finally: await conn.close()`；
  topic_detail/project_topics 走 PgTopicStore/PgProjectStore 自管连接。**无泄漏**，无需改。

## 实测
### 自动化回归（test-first，CI 装置=compose 本地 PG，S2-7 零外网）
`tests/harness/test_demo_nonblocking.py`：慢同步 provider（每次 generate_structured `time.sleep(0.12)`）驱真实 combo handler +
真实 orchestrate_combo + 真实 DB（仅 LLM 延迟用 sleep 顶替，语义同真机 75s）；心跳协程（每 10ms 一拍）测事件循环**单次最长停顿**。
- **修前 FAIL**：最长停顿 **1.105s**（9 次同步调用全砸 loop）≥ 0.25s 阈值。
- **修后 PASS**：最长停顿 **< 0.25s**（同步活在线程池，loop 空闲）。

### 真机实测（owner CRITICAL「别只 mock」：真 demo 栈 + 真 qwen3.6:35b-a3b + 真 github/arxiv，2026-07-04）
| 场景 | /plaza 延迟（生成进行中并发打） | 结论 |
|---|---|---|
| **修前** combo（临时 revert threadpool） | t=2s/4s = **8.0s 超时 http=000**；combo 结束后立刻回 0.4s http=200 | 事件循环憋死 = 前端 Failed to fetch ✅复现 |
| **修后** combo（16s 真生成 6 主题） | 全程 **0.36~0.39s**（max 0.394s） | 秒回 ✅ |
| **修后** gate1（40s 真 live 后台跑 queued→retrieving→judging→validating→done） | `/plaza` 全程 **0.37~0.43s**、`/cards` **0.02s**（仅 done 瞬间 1.3s = 快照写，非持续停顿） | 后台 job 不憋 loop ✅ |

（修前 revert 仅供演示，随后即恢复；恢复后 ruff+mypy 复验、与已验证版 byte 一致。）

## 落盘 / 门
- 改 `flint/api/combo.py`（+run_in_threadpool import + orchestrate_combo 挪线程池）、`flint/jobs/gate1.py`（+import + _collect_docs 新helper + 四处 threadpool）；
  新增 `tests/harness/test_demo_nonblocking.py`。
- verify：`ruff check` 净 · `mypy --strict flint` 224 文件净 · S2-8 禁用词净 · 回归
  `combo(ts010) + gate1(featb_live/m2_040/m2_042/m2_049/m3_056/ts_006) + nonblocking` **28+1 绿**。
- **冻结件不动**（contracts/ + LLMProvider 同步协议未碰，只在调用侧 offload）；**零付费**（免费本地 qwen + 免费公网 github/arxiv）；未改依赖锁（run_in_threadpool 来自已锁 starlette 1.3.1）。

## 返工记录
- 测试脚手架：起初 import TS-010 的 `_clean` autouse fixture 无法在本模块注册 → 改本模块自定义 `_clean_nb`（ts010nb 前缀）+ 只 import 纯函数 `_payload/_pick_cross_cluster`。
- 真机计时踩坑：Git Bash 无 `/usr/bin/time`、`/tmp` 与 Windows Python 路径不一致 → 改用 curl 内建 `-w "%{time_total}"` + bash 直读。
