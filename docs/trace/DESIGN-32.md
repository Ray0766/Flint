# DESIGN-32 trace — [隔离·G22扩] 导出闸门增「模板未固化」判据@2026-08-03

> **隔离带卡 + owner_review**，按 DEC-000 默认照做；`DECISIONS-v04.md` 无划除记录。

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-32`；
- context_refs：`WORKORDER-v04.md#11`、`WORKORDER-v04.md#9`（§9-P2 全文）；
- 前置产物：`flint/design/export_gate.py`（DESIGN-16 基线两条判据 + `GateViolation` 形状）、
  `flint/design/templates/registry.py`、`flint/design/prod_render.py`（G6 的 owner/停用口径）。
- 实测装载 ≈ 9k tokens，未超 40k。

## 2 第三条判据来了，但**没有**去做 P2 的抽取重构——理由

DESIGN-16 的 trace 里我写过：「第三个判据出现时要做一次抽取重构」。本卡就是那第三条，
而我**没有**做那次重构。理由是隔离带的约束比「少一次重构」更硬：

- 判据注册表会把三条判据焊在一张表里；owner 划掉本卡时，就要动那张表——
  而 acceptance② 要的恰恰是「**仅移除本卡与判据注册，基线闸门不受影响**」。
- 所以本卡是**加一层**：提供第三条判据 + 一个把基线与它串起来的组合函数。
  `flint/design/export_gate.py` 一个字都没改（有测试断言：基线源码里不出现本卡的判据 id、
  也不 import 本卡）。

**代价照 DESIGN-16 记的那样存在**：三条判据现在分布在两个模块里。
但 `GateViolation` 的形状是共享的，所以**调用点与错误体仍然只有一种**——
那正是当初把 violations 做成对象留下的余地。

owner 若日后采纳 P2，重构的形状也已经清楚：把两个模块里的 `check_*` 注册进一张表，
`GateViolation` 不动。

## 3 为什么导出这一侧也要有门

G6（DESIGN-31）管的是**生产渲染**这条路。导出是**另一个出口**：拿一份没固化的样板
直接导出 PDF，示例数字就这样交给了客户，而它一次都没经过生产渲染。**两个出口都要有门。**

**探索期导出不受这条管**（`html` 不在 `PRODUCTION_FORMATS` 里）：预览与内部分享
属于 G0 该有的自由；把它们也拦下来，用户会为了看一眼效果而被迫先固化，
固化就成了一道过场手续。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| 未固化 → 拒绝并指认判据 id | `test_production_export_without_template_is_blocked`、`test_unregistered_template_is_blocked`（`ref` 指到具体 template_id）、`test_another_owners_template_is_blocked`、`test_disabled_template_is_blocked` |
| （放行面） | `test_registered_template_passes`、`test_exploration_export_is_not_gated`、`test_clean_state_exports`、`test_guard_renders_when_clean` |
| 零下游破坏 | `test_base_gate_is_untouched_by_this_card`、`test_this_card_depends_on_base_not_the_other_way`、`test_base_gate_still_works_on_its_own` |
| （与基线并列） | `test_three_criteria_are_reported_together`（三条一次说清）、`test_guard_blocks_before_rendering`（拒绝时零渲染） |

**②** 无冻结件偏离：零触碰 `contracts/` 与 `contracts_v04/`；基线闸门文件未改动。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：`GateViolation` / `GateResult` / `DesignExportBlocked` 全部取自基线；
「已固化」的判定口径（owner、enabled）与 G6 门一致。
**⑤** 装载 ≈9k tokens，未超 40k。

## 5 verify

```
$ pytest tests/v04/design/test_export_gate_template.py -q  → 13 passed
$ pytest tests/v04/design -q                                → 134 passed
$ ruff check . --no-cache                                   → All checks passed!（--fix 归位四处 import 排序）
$ mypy --strict flint                                       → 269 source files, no issues
```

## 6 产出

- `flint/design/export_gate_template.py`
- `tests/v04/design/test_export_gate_template.py`（13 条）
