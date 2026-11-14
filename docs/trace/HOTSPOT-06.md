# HOTSPOT-06 trace — 分析时效 stale 适配器（复用 Revalidator 通道，不新写比对）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#HOTSPOT-06`；
- context_refs：`WORKORDER-v04.md#6`（H1 行原句）、
  `contracts/protocols.py#Revalidator`（第 223~233 行）与 `#LedgerStore.diff`（第 253~256 行）；
- 前置产物：`flint/ledger/diff.py`（`compute_diff` 三分类 + `_MARKS` 严重度表 + 零污染口径）、
  `flint/domain/models.py` 的 `FactDiff / ReviewReason / ReviewSeverity`。
- 实测装载 ≈ 11k tokens，未超 40k。

## 2 关键设计判断

**一行比对逻辑都不写**。再写一套的后果不是重复劳动，而是**同一份分析在两个地方
被判成不同的新旧**：收藏页说它陈旧、分析页说它是最新的，用户不知道该信哪个。

**严重度表也不抄**。抄一份最坏的形态不是抄错，而是**日后只改了一处**——
审11 说严重度只升不降，两张表分叉时，同一次事实移除会在一个界面上是 blocking、
另一个上是 advisory。故直接读 `flint.ledger.diff._MARKS`（表首即最强），
并用一条测试断言映射与它逐项相同。

**只看这份分析真正引用过的事实**（零污染，与既有 block 标记同一条规则）：
否则账本一动、全站分析统统标陈旧，「陈旧」这个标记就不再有信息量。

**同版本不查**：白跑一次 diff 不只是浪费，它给了「同版本也能判出陈旧」的可能性，
而那只会是比对实现的 bug 被放行的入口。**版本倒退直接报错**：账本版本只前进，
收到倒退的版本对就是接线错了，当成「不陈旧」放过等于把接线 bug 藏起来。

## 3 test-first 顺序 + 一次返工

1. 先写 10 条测试 → 跑 → 红（模块不存在）；
2. 实现 `flint/analysis/stale_adapter.py` → 8 passed / 2 failed；
3. 两条红都指向同一件事：函数名 `analysis_stale_from_diff` 命中了 §6-H1 的原句
   `grep -R "def .*diff" flint/`。这里**改的是名字不是断言**——H1 那条 grep 是工单
   写死的机器判据，让它保持字面干净比给适配器起个带 diff 的名字更值；
   改名为 `stale_from_fact_changes` 后语义未变（它本来就只是消费方，不是比对实现）。
4. 10 passed。

## 4 acceptance ↔ 测试映射

acceptance 唯一条：**适配器 import 自 contracts 通道（H1 断言）；无新比对实现**。

| 测试名 | 覆盖点 |
|---|---|
| `test_adapter_imports_the_contracts_channel` | import 面含 `flint.ledger.diff` 与 `flint.domain.models`（AST 断言，非字符串包含） |
| `test_adapter_defines_no_diff_of_its_own` | 本文件定义的函数名里没有 diff |
| `test_repo_wide_diff_implementations_unchanged` | 工单原句的仓库级复跑：新文件不出现在命中集，且既有 ledger 比对仍在原处 |
| `test_severity_table_is_the_existing_one` | 三类映射与 `_MARKS` 逐项相同（表变则测试跟着变，两处 NEVER 分叉） |
| `test_unrelated_fact_change_leaves_the_analysis_fresh` | 零污染：未被引用的事实变动不算陈旧 |
| `test_removed_beats_changed_when_both_hit` | 多类命中取最强（审11 只升不降） |
| `test_empty_diff_is_not_stale` | 空 diff 不陈旧 |
| `test_same_version_never_calls_diff` | 同版本零调用（spy 断言 `calls == []`） |
| `test_advanced_version_asks_the_injected_channel` | 参数逐字 `(project, 旧版, 新版)`，走注入通道 |
| `test_version_going_backwards_is_rejected` | 版本倒退报错，且断言 diff 通道 NEVER 被调 |

「仓库级复跑」那条是本卡最值钱的一条：只断自己那一个文件的话，本卡若在别处
偷偷加了一个比对函数，单文件断言照样绿。

## 5 verify

```
$ pytest tests/v04/hotspot/test_analysis_stale_adapter.py -q  → 10 passed
$ pytest tests/v04/hotspot -q                                  → 41 passed
$ ruff check . --no-cache                                      → All checks passed!
$ mypy --strict flint                                          → 254 source files, no issues
```

禁用词扫描：本卡两份产出 0 命中。

## 6 产出

- `flint/analysis/stale_adapter.py`
- `tests/v04/hotspot/test_analysis_stale_adapter.py`（10 条）
