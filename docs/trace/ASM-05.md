# ASM-05 · 端到端冒烟（主链第一次真跑通）— trace

批次：v0.4.1 第 1 批。台账：`docs/progress-v041.jsonl`。**owner_review=true**（事后补审，
按 `worker.md` §7 打标继续，不停机）。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| ASM-05 卡 + 工单 §0/§4 | 卡面真相与红线 |
| `flint/api/compose.py` 全文 | `POST /projects/{id}/report` 的 deps 与 payload 形状 |
| `flint/api/deliverables.py` 全文 | `/blocks`、`/render?fmt=`、409 EXPORT_BLOCKED 的响应体 |
| `flint/render/gatekeeper.py` 全文 | `ExportBlocked` / `check_export` 的判据（needs_review + blocking） |
| `flint/jobs/worker_main.py`（ASM-03） | 入队钩子与 burst worker |
| `flint/jobs/compose_deps.py`（ASM-01） | 生产组稿装配 |
| `harness/demo_seed_report.py` 首 30 行 | fixture 前缀 `del-demo-fixture-` |
| `flint/compose/blocks.py`（review 字段名） | 门禁用例要写的三列 |

实际装载约 30k tokens（≤40k）。

## 断点与决策

1. **§4.2 顺序偏离（如实记录）**：本卡先写了 `harness/e2e_smoke.py`，再写
   `tests/v041/test_asm_05_e2e.py`；首次跑测即 7 条全绿，**没有先看到红**。
   偏离原因：冒烟脚本本身就是本卡的产出之一（卡的 outputs 列了它），测试只是它的验收壳。
   补偿措施：每条 acceptance 都配了**反例用例**证明断言不空转——
   `test_the_fixture_prefix_assertion_is_not_vacuous`（fixture 前缀确实是那个值）、
   `test_failure_names_the_step_it_broke_at`（真造一次失败，断言定位到 consume 步）、
   `test_every_step_has_a_named_failure_path`（AST 面收 `raise SmokeFailure("<step>",…)`
   的首参，五步一个不少）。另外「占位生成器会让 compose 步红」这条已由 ASM-01 的
   `test_placeholder_degradation_is_detected_by_the_same_assertion` 覆盖。
   这条偏离**留给 owner / supervisor 判**，我不自行开脱。
2. **零修改边界守住**：产出仅 `harness/e2e_smoke.py` 与 `tests/v041/test_asm_05_e2e.py`
   两个新文件。`harness/demo_seed_report.py`、`harness/demo_server.py`、
   `flint/api/*` 全部一字未动。
3. **入队钩子每次现开 pool**：提交端点跑在 TestClient 自己的事件循环里，跨循环复用
   连接池会绑错 loop。钩子本身仍是 `worker_main.build_enqueue_hook`（未另写一份）。
4. **respx 护栏**：整条链包在 `respx.mock(assert_all_called=False)` 里。录制回放走
   `httpx.MockTransport`、API 走 ASGI 传输，两者都不经默认 http 传输——所以护栏拦的
   正是「除这两者之外的任何真出网」。护栏未被绕过（没有 `respx.route(...).pass_through()`）。
5. **真实源冒烟按工单 §4 留卡不执行**：真实 github/arxiv 检索属红线，写进
   `docs/blocked/E2E-REALSOURCE.md`，需 owner 在场点一次。

## 自审报告（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 测试 |
|---|---|
| 一条链路真跑：POST report → worker 消费 → /blocks 非空且含 paragraph → /render 出 markdown | `test_full_chain_runs_end_to_end`（断言五步名字齐、blocks 非空、含 paragraph、markdown 非空**且包含本次生成的正文**——最后这条是关键：只断言「非空」的话，占位 heading 也能过） |
| 冒烟数据 NEVER 来自 fixture 播种：deliverable_id 不带 `del-demo-fixture-`，blocks 的 author 与 revision 与本次真跑一致 | `test_smoke_data_is_not_fixture_seeded`（前缀 + `deliverable_id == f"del-{job_id}"` + 逐块 author=="system"、revision==1、block_id 含本次 job_id）+ **反例** `test_the_fixture_prefix_assertion_is_not_vacuous` |
| 沿途至少一道导出闸门被真实触发：blocking 命中返回 409 带 blocking_block_ids、放行时出产物，两种用例都要有 | `test_export_gate_blocks_and_names_the_blocking_blocks`（把真跑产出的某块置 needs_review+blocking，断言 409、code==EXPORT_BLOCKED、detail 里点名那个 block_id）+ `test_export_gate_lets_a_clean_deliverable_through`（清掉标记 → 200 且正文在里面） |
| 全程零真实网络：respx 护栏不得绕过；LLM 走录制回放或本机模型 | 所有链路用例都经 `_smoke()`，它把 `run_e2e_smoke` 包在 `respx.mock` 里；LLM 是 `httpx.MockTransport` 录制回放 |
| 失败时报出断在哪一步，NEVER 只报一句断言失败 | `test_failure_names_the_step_it_broke_at`（注入会抛的 provider，断言 `err.step == "consume"` 且消息含「断在」与步名、detail 非空）+ `test_every_step_has_a_named_failure_path`（AST 面五步全覆盖） |

7 条用例，全部 `@pytest.mark.compose`（要真容器），无 `assert True`。

### ② 无冻结件偏离

`contracts/`、`flint/domain/`、`flint/api/`、`flint/render/` 均一字未动。

```
$ python -m mypy --strict harness/e2e_smoke.py
Success: no issues found in 1 source file
```

### ③ 无禁用词

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" harness/e2e_smoke.py tests/v041/test_asm_05_e2e.py
（无输出）
```

### ④ 复用断言在位

- 复用 `flint.api.compose.create_compose_app`（真端点，未另写提交逻辑）。
- 复用 `flint.api.deliverables.create_deliverables_app`（真端点，`/blocks` 与 `/render` 都走它）。
- 复用 `flint.jobs.worker_main.build_enqueue_hook` / `build_worker`（ASM-03）。
- 复用 `flint.jobs.compose_deps.build_production_compose_deps`（ASM-01）——正是它让
  `/blocks` 里出现 paragraph 而不是占位 heading。
- 复用 `flint.render.gatekeeper.guarded_render`（门禁未另写一份判据）。

### ⑤ 装载未超预算

约 30k tokens < 40k。

## 产出文件

- `harness/e2e_smoke.py`（新增）
- `tests/v041/test_asm_05_e2e.py`（新增，7 条用例）
- `docs/blocked/E2E-REALSOURCE.md`（真实源冒烟留卡，需 owner 在场）

## verify

```
$ python -m pytest tests/v041/test_asm_05_e2e.py -q
7 passed in 7.50s
$ python -m pytest tests/v041/ -q
56 passed
$ python -m ruff check harness/e2e_smoke.py tests/v041/ --no-cache
All checks passed!
```
