# ASM-03 · arq worker 进程装配 — trace

批次：v0.4.1 第 1 批。台账：`docs/progress-v041.jsonl`。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| ASM-03 卡 + 工单 §3/§4/§7 | 卡面真相、触碰边界、红线、并行纪律 |
| `flint/jobs/runner.py` 全文 | `EnqueueHook` 签名（既有可注入点，一字未改） |
| `flint/jobs/dispatch.py`（ASM-02 产出） | 总表与失败处置 |
| `flint/jobs/compose_deps.py`（ASM-01 产出） | 生产组稿装配 |
| 各 job 入口签名（gate1/ingest/spec_export/compose/regenerate_job） | 五个可接线 kind 的执行体 |
| `flint/api/compose.py` 提交端点 | report / proposal 的 payload 形状 |
| `flint/jobs/regenerate_worker.py:parse_regenerate_payload` | report 类作业的形状判别 |
| `harness/demo_server.py:_enqueue` 与 `_is_regenerate_payload` | 形状判别的既有口径（照抄语义，未 import harness） |
| `tests/m3/test_m3_060.py` 全文 | compose 集成测试的仓内写法（wipe / seed_claim / _steps） |
| `tests/m1/test_m1_036.py` 首 30 行 | `FLINT_TEST_REDIS` 默认值口径 |
| `requirements.lock`（arq/redis 两行） | 版本钉值 |
| arq 0.28 源码（`Worker.__init__` / `close` / `typing.WorkerCoroutine`） | 装配参数与 Windows 信号坑 |

实际装载约 33k tokens（≤40k）。

## 断点与决策

1. **零修改边界守住**：`flint/jobs/runner.py` 一字未改（`EnqueueHook` 本来就是注入点，
   工单 §3 明写）。本卡产出仅 `flint/jobs/worker_main.py` 与 `tests/v041/test_asm_03.py`。
2. **不新写 runner（H7）**：五个可接线 kind 的执行体全部是既有 `run_*` 入口；worker 只做
   「取队列 → 查表 → 调既有入口 → 失败记 failed」。
3. **缺注入件的三 kind 显式抛错**：`gate1_analysis` 要真 searcher、`daily_ingest` 要
   source/embedder、`spec_export` 要包清单。这些在 CI 里不该被构造（gate1 的真 searcher =
   真实 github/arxiv，属工单 §4 红线）。故 handler 在**被调用时**抛 `HandlerDepsMissing`
   并点名要注入什么；`compose_provider` 是 report/proposal 的硬前提，改在**装配期**就抛。
4. **`_job_id` 去重**：入队用 `_job_id=f"arq-{job_id}"`，同一作业重复提交在队列层被去重。
   代价是 arq 的 `_job_id` 键是**全局**的（不按队列名分区）——测试里复用固定 job_id 会让
   第二次跑静默不入队。这坑咬了一轮（见下），测试改为每次用新 id。
5. **每个用例独立队列名 `arq:asm03-{uuid}`**：redis 容器是 worker 与 supervisor 共用的一台
   （§7.1 只分了测试库，没分 redis）。固定队列名会让两条线互相消费对方的作业。
6. **arq 在 Windows 的信号坑**：`Worker.close()` 在 `handle_signals=False` 时会调
   `signal.SIGUSR1`，Windows 没有这个信号（arq 0.28 的 POSIX 假设）。而 arq 自己的
   `_add_signal_handler` 已经吞掉了 Windows 的 `NotImplementedError`。故 `handle_signals`
   留 arq 默认（True），dev 机与 Linux 部署面都能关干净。
7. **mypy 的 `WorkerCoroutine` cast**：arq 的 `func()` 形参类型是带 `__qualname__` 的
   Protocol，普通函数运行期满足它但 mypy 不认，故显式 `cast`，并把 arq 的类型 import 放进
   `TYPE_CHECKING`（运行期不引入）。
8. **返工两轮**（未触 §4.4 的 3 轮上限）：
   - 轮 1：`handle_signals=False` 导致 `Worker.close()` 在 Windows 抛 `AttributeError`；
     且续跑用例原本把中断点设在 align 步，但 `flint/jobs/compose.py:283` 的 align 步传的是
     **空 claim 列表**（`align_gate(aligner, [], {}, record)`），注入的 aligner 根本不会被调到，
     所以「DID NOT RAISE」。中断点改到 draft 步（provider 抛错），断点前缀 = outline/freeze。
   - 轮 2：两条集成用例复用固定 job_id，被 arq 的全局 `_job_id` 去重挡住 → 队列空。改为
     每次跑用新 id，并顺手加了一条「重复提交不排两条」的正向断言。
9. **draft 步断点复用的证据放在真 kill 那条**：`test_real_kill_then_resume_via_the_compose_cli`
   用子进程跑 `python -m flint.jobs.compose --crash-after draft`（`os._exit(137)` 真 kill），
   断点前缀 = outline/freeze/draft，重启后只跑 align/render。in-process 那条中断在 draft 步，
   证明的是「已完成前缀原样复用」。两条合起来覆盖 acceptance ②。

## 自审报告（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 测试 |
|---|---|
| enqueue 钩子实调：submit 后作业确实进入队列，断言基于**队列真实状态**而非调用计数 | `test_enqueue_hook_puts_the_job_in_the_real_queue`（读 `pool.queued_jobs(queue_name=...)`，断言 `job_def.function == ARQ_TASK_NAME` 且 `args[0] == job_id`、`args[1] == "report"`；并断言重复提交仍是 1 条）+ **反例** `test_empty_queue_makes_the_previous_assertion_fail`（不接钩子时队列为空——证明上一条看的是真队列） |
| worker 消费一条 compose 作业并把状态机推进到 done | `test_worker_consumes_a_compose_job_and_drives_it_to_done`（真 arq Worker burst 模式跑；断言 `jobs.state == 'done'`、blocks 里有 paragraph 且正文是本次注入的那段、五步 job_steps 齐全） |
| 中途 kill 后重启能续跑（复用既有 DraftCheckpoint） | `test_real_kill_then_resume_via_the_compose_cli`（子进程 `os._exit(137)` 真 kill，断言退出码 137、断点前缀 outline/freeze/draft，重启后补齐 align/render 并到 done）+ `test_worker_resumes_a_half_finished_job_reusing_draft_checkpoints`（worker handler 路中断，断言已完成前缀的 snapshot_ref 逐字未变、续跑补齐五步并出 paragraph） |
| NEVER 新增依赖：arq 0.28.0 与 redis 5.3.1 已在 lock，测试里断言版本来自 lock 而非硬编码 | `test_arq_and_redis_versions_come_from_the_lock_not_a_hardcoded_string`（正则从 `requirements.lock` 读钉值，与 `arq.__version__` / `redis.__version__` 比对）+ `test_worker_module_introduces_no_dependency_outside_the_lock`（AST 解析 worker_main 的第三方 import 根名，逐个要求在 lock 里；并断言解析到了非空集合，防空转） |
| 测试 NEVER 触真实外网 | LLM 全走 `httpx.MockTransport` 录制回放；postgres/redis 是本机容器（工单 §4「本机不算外网」）+ `test_worker_module_never_opens_a_real_network_client_at_import`（模块层不得出现 `httpx.Client(` / `GithubArxivSearcher(` / `api_key`） |

另有分派面 4 条：`test_handlers_cover_every_wireable_kind`、
`test_missing_compose_provider_is_named_at_build_time`、
`test_missing_gate1_deps_names_what_to_inject`、
`test_unwired_kind_still_fails_loudly_through_the_worker_table`。
合计 13 条用例（7 条免容器 + 6 条 `@pytest.mark.compose`）。

### ② 无冻结件偏离

`contracts/`、`flint/domain/`、`flint/jobs/runner.py` 均一字未动。

```
$ python -m mypy --strict flint/jobs/worker_main.py
Success: no issues found in 1 source file
```

（additive 双校验已在 ASM-02 trace 贴出，本卡未触契约面。）

### ③ 无禁用词

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" flint/jobs/worker_main.py tests/v041/test_asm_03.py
（无输出）
```

### ④ 复用断言在位

- 复用 `flint.jobs.runner.EnqueueHook` 注入点（未新写 runner）→ `test_enqueue_hook_puts_the_job_in_the_real_queue` 走的就是 `PgJobRunner.submit`。
- 复用 `flint.jobs.dispatch`（ASM-02）→ `test_handlers_cover_every_wireable_kind` 断言表仍是 10 行；`test_unwired_kind_still_fails_loudly_through_the_worker_table` 断言未接线路径穿透到 worker 表。
- 复用 `flint.jobs.compose_deps.build_production_compose_deps`（ASM-01）→ worker 消费用例产出的正文是真生成的段落，不是占位 heading。
- 复用既有 `run_compose` / `run_gate1` / `run_daily_ingest` / `run_spec_export` / `run_regenerate_job`（未新写执行体）。
- 复用 `flint.jobs.regenerate_worker.parse_regenerate_payload` 做形状判别（未复制 demo 的判别逻辑，也未 import harness）。

### ⑤ 装载未超预算

约 33k tokens < 40k。

## 产出文件

- `flint/jobs/worker_main.py`（新增）
- `tests/v041/test_asm_03.py`（新增，13 条用例）

## verify

```
$ python -m pytest tests/v041/test_asm_03.py -q
13 passed
$ python -m pytest tests/v041/ -q
38 passed
$ python -m mypy --strict flint/jobs/worker_main.py && python -m ruff check flint/jobs/worker_main.py tests/v041/ --no-cache
Success / All checks passed!
```
