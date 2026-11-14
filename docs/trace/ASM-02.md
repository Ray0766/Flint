# ASM-02 · JobKind → handler 分派表 — trace

批次：v0.4.1 第 1 批。台账：`docs/progress-v041.jsonl`。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| ASM-02 卡（`docs/steward/tasks-v041.json`） | 卡面真相 |
| `contracts/models.py#JobKind`（707–708 行） | 判别联合 7 值 |
| `contracts_v04/models_v04.py`（800–805 行） | v0.4 additive 后的 10 值 |
| `flint/jobs/runner.py` 全文 | `EnqueueHook` / `PgJobRunner.submit` / 状态机 |
| `flint/jobs/checkpoints.py` 1–60 行 | 既有的「按 kind 全表映射」先例 |
| 各 job 入口签名（gate1 / ingest / revalidation / sched / spec_export / compose / regenerate_job） | 判定哪些 kind 真有消费者 |
| `flint/i18n/name_display_job.py`、`flint/design/solidify.py`、`flint/design/session.py` | 判定 v0.4 三新 kind 有无消费者 |
| `harness/demo_server.py:_enqueue` | 现状缺陷取样（只认两 kind，其余静默 return） |
| `pyproject.toml`、`tests/m3/*` 抽样 | 测试异步写法的仓内约定 |

实际装载约 24k tokens（≤40k）。

## 断点与决策

1. **覆盖面取两份契约的并集**（10 值）。理由：两份都在被真代码引用——`flint/jobs/runner.py`
   的类型标注用 `flint/domain/models.py`（7 值），而 `flint/i18n/name_display_job.py` 的
   `translate` 出自 `contracts_v04/models_v04.py`（10 值）。只认前者会漏掉 v0.4 三新 kind；
   只认后者会与运行期标注脱节。`known_job_kinds()` 用 `typing.get_args` 从两个真文件求出。
2. **表分两半，两半都是显式的**：
   - `WIREABLE_KINDS`（5 个：gate1_analysis / report / proposal / spec_export / daily_ingest）
     —— 仓里确有 per-job 消费者，handler 由调用方注入（ASM-03 装配处）。少一个即
     `IncompleteDispatchTable` 并点名。
   - `UnwiredKindReason`（5 个：revalidation / pricebook_scan / translate / design_generate /
     template_solidify）—— 逐条实测确认仓里**没有** per-job 消费者，理由里写明现有代码在哪。
     被调到时抛 `JobKindNotWired`，NEVER 静默排队。
   实测依据：`flint/jobs/revalidation.py` 只有扫描器 `run_revalidation_scan`（它是 submit
   方，不是消费方）；`flint/pricebook/seed.py` 只做种子；`flint/i18n/name_display_job.py`
   只产 payload；`flint/design/session.py`、`flint/design/solidify.py` 都是同步纯函数。
3. **三条失败路都落到「job 变 failed 且有话说」**：未知 kind（`UnknownJobKind`）、未接线
   （`JobKindNotWired`）、handler 自己抛错——统一先 `mark_failed(job_id, error)` 再把错抛上去。
   先记 failed 再抛，是因为作业状态必须先离开 queued：静默丢弃的用户可见症状就是永远排队。
4. **异步测试写法随仓内约定**：本仓不用 `pytest-asyncio` 标记（`pyproject.toml` 的
   `[tool.pytest.ini_options]` 未注册该 marker），既有 m3/m4 测试一律 `asyncio.run(coro)`。
   首轮写成 `@pytest.mark.asyncio` 被判红（5 条），改为 `asyncio.run` 后全绿。返工 1 轮。
5. 零修改既有文件：本卡产出仅 `flint/jobs/dispatch.py` 与 `tests/v041/test_asm_02.py`。

## 自审报告（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 测试 |
|---|---|
| 覆盖判别联合全部成员；覆盖面用 `get_args` 遍历真件求出，NEVER 手抄 | `test_known_kinds_equal_the_union_of_both_real_contracts`（测试侧独立地从两个真文件求一遍，与实现对比）+ `test_known_kinds_are_derived_by_get_args_not_a_literal_list`（AST 面断言实现真的调了 `get_args`）+ `test_every_contract_kind_has_a_row_in_the_table`（表 10 行）+ `test_every_unwired_kind_carries_a_concrete_reason`（两半之和 == 契约全集） |
| 缺任一成员即红，并在报错里点名缺哪个 | `test_missing_wireable_handler_is_red_and_names_it`（抽掉 report）+ `test_empty_handlers_names_every_missing_kind`（逐个点名）+ `test_a_new_contract_member_nobody_declared_is_red_and_named`（**模拟契约将来新增一个 kind**，这条是防手抄的真闸）+ `test_typo_in_a_handler_key_is_rejected_and_named`（多出的 key 也点名） |
| 未知 kind → 抛错并把 job 记为 failed，NEVER 静默丢弃 | `test_unknown_kind_raises_and_marks_the_job_failed`（断言抛错 + `mark_failed` 收到 job_id 与含 kind 的原因）+ `test_unknown_kind_never_reaches_any_handler`（断言没有 handler 被调到）+ `test_unwired_kind_raises_with_a_reason_and_marks_failed` + `test_handler_failure_marks_failed_and_reraises` |

14 条用例，无 `assert True`；反例用例 4 条（缺 handler / 新契约成员 / key 拼错 / handler 抛错）。

### ② 无冻结件偏离

```
$ python tools/check_frozen_additive.py contracts/models.py contracts_v04/models_v04.py
additive 校验通过：models_v04.py 逐字含 models.py 全量 87 类 / 443 字段 / 1 方法签名 / 31 枚举；新增 17 类、13 字段、10 枚举/联合成员
$ python tools/check_frozen_additive.py contracts/protocols.py contracts_v04/protocols_v04.py
additive 校验通过：protocols_v04.py 逐字含 protocols.py 全量 24 类 / 1 字段 / 40 方法签名 / 0 枚举；新增 0 类、0 字段、0 枚举/联合成员
$ python -m mypy --strict flint/jobs/dispatch.py
Success: no issues found in 1 source file
```

`contracts/` 与 `flint/domain/` 一字未动。新增的三个异常类是本模块局部错误类，不进冻结件。

### ③ 无禁用词

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" flint/jobs/dispatch.py tests/v041/test_asm_02.py
（无输出）
```

### ④ 复用断言在位

- 复用 `flint.domain.models.JobKind`（未另定义 kind 字面量）→ `test_known_kinds_equal_the_union_of_both_real_contracts`。
- 复用 `contracts_v04/models_v04.py` 的 JobKind（经文件加载，非复制）→ 同上测试独立加载后比对。
- 未新写 runner（H7）：分派表只做查表与失败处置，handler 由调用方注入既有 `run_*` 入口。

### ⑤ 装载未超预算

约 24k tokens < 40k。

## 产出文件

- `flint/jobs/dispatch.py`（新增）
- `tests/v041/test_asm_02.py`（新增，14 条用例）

## verify

```
$ python -m pytest tests/v041/test_asm_02.py -q
14 passed in 0.22s
$ python -m ruff check flint/jobs/dispatch.py tests/v041/ --no-cache
All checks passed!
```
