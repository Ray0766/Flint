# GOLD-01 · 金标集采集脚手架 — trace

批次：v0.4.1 第 1 批。台账：`docs/progress-v041.jsonl`。

## 装载清单（实际）

| 来源 | 用途 |
|---|---|
| GOLD-01 卡 + `CLAUDE.md#S4` | 卡面真相 + Open Question 清单（θ_rel 0.6 / δ 0.965 属未决） |
| `flint/jobs/gate1.py:run_gate1`（497–600 行） | 一次真跑往库里落哪三份快照 |
| `flint/jobs/gate1.py:build_offline_deps` | 离线确定性真跑入口（零网络） |
| `harness/gate1_live.py` 首 50 行 | 真跑与库选择的既有口径（确认默认连测试库） |

实际装载约 11k tokens（≤40k）。

## 断点与决策

1. **采什么**：一次 Gate① 真跑在 `snapshots` 表留三份——`snap-{job}-docs`（证据 Doc 元
   信息）、`snap-{job}-judge`（support_claims）、`snap-{job}-verdict`（四分类判定）。
   分别摊成 `evidence` / `claim` / `verdict` 三类可标注条目。
2. **时间戳取数据自身的，不取导出时的 now()**。这一条同时满足卡的两条 acceptance：
   「每条带真实 UTC 时间戳」与「同一输入两次导出逐字节一致」——取 `now()` 的话这两条
   互斥。时间戳来源是 `snapshots.created_at`，有一条测试直接回查该列比对。
3. **只采不判**：模块里没有任何浮点常量、不引用 `THETA_REL`/`theta`/`delta`、
   **也没有任何大小比较**（`ast.Compare` 的 `<`/`<=`/`>`/`>=` 一个都没有——判定的最小
   形态就是比较）。三条都是 AST 面断言，并用 `flint/jobs/gate1.py` 做反例证明检查不空转。
4. **标注槽留白**：`label` 恒 `None`、`note` 恒空串。脚本不预填任何猜测——预填的猜测
   会被标注者当成参考答案。
5. **可复现的三个来源**：条目 id = 内容哈希（`sha256(job|kind|index|canonical)`）；
   快照按 `SNAPSHOT_KINDS` 固定序遍历；序列化固定 `sort_keys=True` + `ensure_ascii=False`。
6. **返工两轮**（未触 §4.4 的 3 轮上限）：
   - 轮 1：阈值文本检查把模块 docstring 里「0.6 / 0.965 是 Open Question，所以这里不放」
     的说明判成违规（假红）。改为排除 docstring 的字符串常量检查。
   - 轮 2：排除没生效——`ast.get_docstring` 默认 `clean=True` 会归一化缩进，与原始
     Constant 值对不上。改成 `clean=False`。
   - 另有一处 mypy 收尾：`_utc_text` 从 `Any` 返回 `str` 被 `no-any-return` 判红，加显式
     局部标注。
7. 零修改既有文件：产出仅 `harness/gold_collect.py` 与 `tests/v041/test_gold_01.py`。

## 自审报告（self_review=true）

### ① 测试真实覆盖 acceptance

| acceptance | 测试 |
|---|---|
| 能把一次真跑的簇/证据/判定导出成可人工标注的金标条目，每条带来源 job_id 与真实 UTC 时间戳 | `test_collects_annotatable_entries_from_a_real_run`（跑一次真 `run_gate1`，断言三类条目齐、每条带 job_id 与来源快照 id、标注槽为空）+ `test_each_entry_carries_the_real_utc_timestamp_of_its_source`（**回查 `snapshots.created_at` 逐条比对**，不是只看格式） |
| NEVER 内置任何阈值判定：只采集不调参 | `test_collector_holds_no_threshold_constant`（浮点常量 / 阈值名 / 非 docstring 字符串三面查）+ `test_collector_makes_no_judgement_call`（AST 面：没有大小比较）+ `test_annotation_slots_are_left_empty` + **反例** `test_the_threshold_check_is_not_vacuous`（同款检查在 gate1.py 上认得出 `THETA_REL`） |
| 可复现：同一输入两次导出逐字节一致 | `test_export_is_byte_identical_across_two_runs`（比 `utf-8` 字节，且断言导出非空、无空行——防「两次都空所以相等」的空转）+ `test_entry_ids_are_content_derived_and_stable`（id 不撞号、两次一致） |

另有 `test_missing_snapshots_are_skipped_not_faked`（没跑到的步骤不造空条目顶上）。
9 条用例（4 条免容器 + 5 条 `@pytest.mark.compose`），无 `assert True`。

### ② 无冻结件偏离

`contracts/`、`flint/` 均一字未动（本卡产出全在 `harness/` 与 `tests/`）。

```
$ python -m mypy --strict harness/gold_collect.py
Success: no issues found in 1 source file
```

### ③ 无禁用词

```
$ grep -nE "适当|合理|必要时|大约|尽量|若干" harness/gold_collect.py tests/v041/test_gold_01.py
（无输出）
```

### ④ 复用断言在位

- 复用 `flint.jobs.gate1.build_offline_deps` / `run_gate1` 做真跑（未另造假数据）→
  `test_collects_annotatable_entries_from_a_real_run` 走的就是它。
- 采集只读既有 `snapshots` 表，未新建任何表或落盘格式之外的中间态。

### ⑤ 装载未超预算

约 11k tokens < 40k。

## 产出文件

- `harness/gold_collect.py`（新增，含 CLI）
- `tests/v041/test_gold_01.py`（新增，9 条用例）

## verify

```
$ python -m pytest tests/v041/test_gold_01.py -q
9 passed in 1.89s
$ python -m mypy --strict harness/gold_collect.py && python -m ruff check harness/gold_collect.py tests/v041/ --no-cache
Success / All checks passed!
```
