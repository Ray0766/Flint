# ASM-04 · 定时批 cron 装配 — trace

批次：v0.4.1 第 1 批。台账：`docs/progress-v041.jsonl`。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| ASM-04 卡 | 卡面真相 |
| `flint/jobs/sched.py` 全文 | `CRON_BATCHES` / `BatchLock` / `run_scheduled_ingest` / `lock_key` |
| `flint/jobs/revalidation.py` 全文 | `SCAN_HOUR` / `scan_lock_key` |
| `flint/jobs/worker_main.py`（ASM-03 产出） | `build_worker(cron_jobs=...)` 挂载点 |
| arq `cron()` 与 `CronJob` 签名 | 注册参数 |
| `harness/drill7.py:79` | redis 客户端构造的仓内既有写法 |

实际装载约 12k tokens（≤40k）。

## 断点与决策

1. **时刻只有一个真相**：`build_cron_registrations()` 从 `sched.CRON_BATCHES` 与
   `revalidation.SCAN_HOUR` **读**，模块里没有任何 cron 字面量。这一条有两道测试守：
   monkeypatch 改掉上游定义后注册面必须跟着变；AST 面断言 cron.py 里没有 `M H * * *`
   形状的字符串常量（并用 sched.py 做反例，证明检查不空转）。
2. **`run_batch(release=False)` 是日更批次的正路**：既有 `run_scheduled_ingest` 完成即
   释放锁，那挡不住同一天的第二次触发（E4 口径：日更幂等，晚到无意义）。故本模块在
   既有锁之上加一个 `release` 开关：定时批走 `release=False`（锁留到 TTL 到期，同一天
   第二次触发直接 skipped），要重跑的场景走 `release=True`（即既有行为）。
   锁命名空间**不新造**——仍是 `sched.lock_key` 的 `lock:daily_ingest:{day}:{batch}`，
   有一条集成用例直接读那个键断言持有者令牌在位。
3. **`day_of` 可注入**：锁键按天分片，取「今天」这件事必须可注入才能被测。生产传
   `today_utc`。
4. **`max_tries=1`**：定时批 NEVER 靠盲重试补跑——下一次触发才是正路。
5. **revalidation 扫描一并注册**（卡的 inputs 列了 `revalidation.py`）：每日
   `SCAN_HOUR`:00 一次，扫描器自身的幂等由它既有的 `lock:revalidation_scan:{day}` 负责。
6. 零修改既有文件：产出仅 `flint/jobs/cron.py` 与 `tests/v041/test_asm_04.py`。
7. 无返工轮（一次绿）；两处收尾修正：ruff 的未用 import、mypy 对模块级
   `aioredis.from_url` 无标注 → 改用仓内既有写法 `aioredis.Redis.from_url`。

## 自审报告（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 测试 |
|---|---|
| 两个批次的时刻取自 `sched.py` 既有定义，NEVER 另写一份 | `test_registrations_match_the_existing_batch_definitions`（逐批比对）+ `test_registrations_follow_sched_when_it_changes`（**改掉上游定义，注册面必须跟着变**——这条才真正区分「取」与「抄」）+ `test_revalidation_hour_follows_the_revalidation_module` + `test_module_holds_no_second_copy_of_a_cron_expression`（AST 面 + sched.py 反例）+ `test_parse_rejects_a_non_daily_expression` |
| 幂等：同一天同一批次重复触发只跑一次，复用既有 `lock:daily_ingest:{day}:{batch}` | `test_same_day_same_batch_runs_once`（真 redis；断言 executed→skipped 且业务函数只被调 1 次）+ `test_two_batches_on_the_same_day_both_run`（反例：不同批次互不阻塞）+ `test_the_lock_key_is_the_existing_one_not_a_new_namespace`（执行期间直接读 `sched.lock_key(...)` 那个键，断言令牌在位；释放后断言键消失） |
| cron 注册面可在不启动真实调度的前提下被断言 | `test_registry_is_inspectable_without_starting_a_scheduler`（纯数据，无 redis/事件循环）+ `test_cron_jobs_carry_the_registered_times_into_arq`（CronJob 的 hour/minute/max_tries）+ `test_worker_accepts_the_cron_jobs`（真的挂进 ASM-03 的 worker，读 `worker.cron_jobs`） |

11 条用例（8 条免容器 + 3 条 `@pytest.mark.compose`），无 `assert True`。

### ② 无冻结件偏离

`contracts/`、`flint/domain/`、`flint/jobs/sched.py`、`flint/jobs/revalidation.py` 均一字未动。

```
$ python -m mypy --strict flint/jobs/cron.py
Success: no issues found in 1 source file
```

### ③ 无禁用词

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" flint/jobs/cron.py tests/v041/test_asm_04.py
（无输出）
```

### ④ 复用断言在位

- 复用 `sched.CRON_BATCHES`（未另写时刻表）→ `test_registrations_follow_sched_when_it_changes`。
- 复用 `revalidation.SCAN_HOUR` → `test_revalidation_hour_follows_the_revalidation_module`。
- 复用 `sched.BatchLock` / `sched.lock_key` / `sched.run_scheduled_ingest`（未新造锁）→ `test_the_lock_key_is_the_existing_one_not_a_new_namespace`。
- 复用 `worker_main.build_worker` 的 `cron_jobs` 挂载点 → `test_worker_accepts_the_cron_jobs`。

### ⑤ 装载未超预算

约 12k tokens < 40k。

## 产出文件

- `flint/jobs/cron.py`（新增）
- `tests/v041/test_asm_04.py`（新增，11 条用例）

## verify

```
$ python -m pytest tests/v041/test_asm_04.py -q
11 passed in 1.44s
$ python -m pytest tests/v041/ -q
49 passed
$ python -m mypy --strict flint/jobs/cron.py && python -m ruff check flint/jobs/cron.py --no-cache
Success / All checks passed!
```
