# DESIGN-16 trace — 导出闸门基线（fact_removed + 空假设边）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-16`；
- context_refs：`WORKORDER-v04.md#5-G`（G22 一行）、`WORKORDER-v04.md#9`（§9-P2 全文）；
- 前置产物：`flint/render/gatekeeper.py#check_export`（审11 blocking 语义）、
  `flint/design/export.py`（DESIGN-15 的接线）、`flint/api/graph_edges.py`
  （GRAPH-07 的空假设口径）、`tests/v04/_source_scan.py`。
- 实测装载 ≈ 8k tokens，未超 40k。

## 2 §9-P2 风险登记（acceptance② 点名的那条）

**当前基线 = P2 未采纳**：两条判据写在闸门这一处（D2 基线），而不是对象化进
`ExportGate.register` 的判据注册表。

- **现在够用**：两条判据、一个遍历，读起来比注册表直白。
- **代价在第三条判据出现时**：工单 §9-P2 ⑥ 说得明白——隔离带的「模板未固化」
  （DESIGN-32）与 ⑧ 推演还会加判据，届时要做一次抽取重构，改动面比现在大。

本卡为那次重构留的形状：判据结果已经是**对象**（`GateViolation`：criterion / ref / action），
遍历与抛错都走同一个出口。真要抽注册表时，动的是「谁来产 violations」，
而不是「violations 长什么样」——调用点与错误体不用改。

## 3 关键设计判断

**两条并列不短路**：命中第一条就返回的话，用户改完再点导出又被第二条拦下——
他会觉得系统在挤牙膏。一次说清所有问题（与 FAV-05 批量入台同一条纪律）。

**每条违规带「怎么办」**：一句「不能导出」会让用户去逐块翻找，而系统明明知道
是哪几处。清单不是贴心，是**可执行**——他要照着它一条条处理完才能导出。

**拒绝时不渲染**：先判后渲。渲染完再拒等于白花一次算力，也可能在磁盘上留下半个产物。
测试用一个会记账的 render 断言它一次都没被调。

**严重度不另定一套**：审11 的 blocking 判定取自既有 `check_export`（有 import 断言）。
本模块只把它翻译成 `GateViolation`。

**空白假设算空**：只有空格的假设说明不了任何事，却能骗过「非空」这种粗筛
（与 GRAPH-07 后端同一条）。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| 两判据命中 → 拒绝并列阻塞项清单 | `test_both_criteria_are_reported_together`、`test_guard_raises_with_the_full_list`、`test_violation_carries_what_and_where_and_how_to_fix` |
| 判据一（fact_removed=blocking） | `test_fact_removed_blocks_export`、`test_advisory_does_not_block` |
| 判据二（空假设边） | `test_empty_hypothesis_edge_blocks_export`、`test_whitespace_only_hypothesis_counts_as_empty` |
| 沿审11 语义 | `test_gate_reuses_the_existing_block_severity_source`（import 断言） |
| （行为边界） | `test_guard_does_not_render_when_blocked`、`test_guard_renders_when_clean`、`test_clean_state_exports`（阴性对照） |

**②** 无冻结件偏离：零触碰 `contracts/`；`Block` 按既有字段构造。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：审11 严重度来自既有 `check_export`（AST import 断言）；
空假设口径与 GRAPH-07 一致。
**⑤** 装载 ≈8k tokens，未超 40k。

## 5 verify

```
$ pytest tests/v04/design/test_export_gate_base.py -q  → 11 passed
$ pytest tests/v04/design -q                            → 62 passed
$ ruff check . --no-cache                               → All checks passed!
$ mypy --strict flint                                   → 262 source files, no issues
```

## 6 产出

- `flint/design/export_gate.py`
- `tests/v04/design/test_export_gate_base.py`（11 条）
