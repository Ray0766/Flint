# DESIGN-25 trace — 图谱变更 → 样板 stale（H1 第三个薄适配器；不自动重跑）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-25`；
- context_refs：`WORKORDER-v04.md#6`（H1 行：三处薄适配器，本卡是第三处）、
  `WORKORDER-v04.md#4`（事件增量 `graph_stale_notice`）、
  `contracts_v04/models_v04.py` 的 `GraphChange` / `_STRUCTURAL_CHANGES` / `derive_stale`；
- 前置产物：`flint/analysis/stale_adapter.py`（HOTSPOT-06，H1 第一处）、
  `flint/fav/stale.py`（FAV-02，第二处）、`tests/v04/_source_scan.py`。
- 实测装载 ≈ 8k tokens，未超 40k。

## 2 关键设计判断

**NEVER 自动重跑**（G33）：用户在图谱上加了一条边，样板就自己重新生成一遍——
他刚调好的版式、刚手改过的那句话全没了，而他并没有要求重做，他只是在整理关系。
「变了」与「要不要重做」是两个问题，**第二个只有用户能回答**。
所以这一层只产出通知 + 两条出路，一次生成都不发起：模块不 import runner、
不构造 payload、不入队（AST 断言六个名字全不出现）。

**通知是数据不是动作**：不持有 `on_regenerate` 之类的回调，也没有 `job_id` /
`triggered` 这种「已经发起」的痕迹。谁去执行动作由上层决定。

**两条出路的顺序即界面顺序**：先「查看差异」再「重新生成」——先看清再决定。

**派生规则来自契约**：`node_moved` 不算结构性（画布上挪个位置没有改变任何论断），
这条判定归 `derive_stale`（I12-3），本模块**不复读一遍**——H1 的全部意思就是
比对与判定的口径只有一处。测试用 AST 断言 `derive_stale` 确实在调用面上。

**未知变更类型报错**：悄悄当成「不算结构性」放过的话，将来新增一种真会影响内容的
变更时，样板不会标黄，而用户以为它是最新的。

**同一次变更算两遍结果一样**：通知不该越积越多。

## 3 一处与真件对齐

测试初稿把 `GraphChange` 的时间字段写成 `at`，真件是 `occurred_at`——按契约改测试。
这类偏差正是「逐字对齐冻结件」要防的：字段名猜错时，测试会绿在一个并不存在的形状上。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| graph_stale_notice 触发标黄 | `test_structural_change_marks_linked_deliverables`、`test_change_on_another_graph_does_not_touch_us`、`test_unlinked_graph_yields_no_notice`、`test_non_structural_change_marks_nothing` |
| 自动重跑路径不存在 | `test_module_never_submits_a_job`（六个名字）、`test_regenerate_is_an_action_not_an_effect`、`test_notice_is_data_not_an_action_object` |
| 两动作可用 | `test_notice_offers_exactly_two_actions`（顺序也断） |
| （H1 复用） | `test_derivation_reuses_the_contract_rule` |
| （边界） | `test_unknown_change_kind_is_rejected`、`test_same_change_twice_is_idempotent` |

**②** 无冻结件偏离：零触碰 `contracts/` 与 `contracts_v04/`；字段名按真件对齐（见 §3）。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：H1 第三处适配器与前两处同源——判定走 `derive_stale`，
本模块只做接线；源码扫描走共享 `tests/v04/_source_scan.py`。
**⑤** 装载 ≈8k tokens，未超 40k。

## 5 verify

```
$ pytest tests/v04/design/test_graph_stale_link.py -q  → 11 passed
$ pytest tests/v04/design -q                            → 83 passed
$ ruff check . --no-cache                               → All checks passed!（--fix 归位三处 import 排序）
$ mypy --strict flint                                   → 264 source files, no issues
```

## 6 产出

- `flint/design/graph_stale.py`
- `tests/v04/design/test_graph_stale_link.py`（11 条）
