# DESIGN-29 trace — [隔离·G4] 固化校验器（四判据 + 行号）@2026-08-03

> **隔离带卡 + owner_review**，按 DEC-000 默认照做；`DECISIONS-v04.md` 无划除记录。

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-29`；
- context_refs：`WORKORDER-v04.md#11`（③承重墙）、`WORKORDER-v04.md#5-G`（G4 行）；
- 前置产物：`flint/design/solidify.py`（DESIGN-28 的转换与遮罩手法）、
  `flint/design/mock_syntax.py`（跨语言占位语法表）、
  `flint/design/prod_render.py`（插槽形态）。
- 实测装载 ≈ 9k tokens，未超 40k。

## 2 为什么校验与转换要分开

固化管道（DESIGN-28）负责**转换**，本模块负责**判定**。转换器只知道自己做了什么；
判定要看的是**结果长什么样**——一份从别处导入的、或被手改过的模板，
转换器根本没见过它，而它照样要过这道检查。

## 3 四条判据，各自的坏后果

| 判据 | 不拦住会怎样 |
|---|---|
| 插槽完整（双向） | 多声明 → 渲染时要一个不存在的值；少声明 → `{{block:x}}` 原样渲染给客户看 |
| 无占位残留 | 示例数字跟着模板进生产，而生产渲染只认模板、不再看内容（G6） |
| 无水印残留 | 正式产物上印着「这是样板」，比漏一个示例数字更难解释 |
| 插槽类型对齐 | 指向不存在的 Block/词条，渲染期才发现——而那时用户已经在等结果了 |

**四条并列不短路**（与 DESIGN-16 闸门同一条纪律）：一次说清所有问题。

## 4 每条违规带行号 + 原文 + 怎么办

「模板不合格」这句话对改的人没有任何帮助。这道检查真正的产物是**那张清单**。
所以 acceptance② 要求断「实际输出文本」——只断 `raises` 的话，清单退化成一句话
也照样绿，而那正是这张卡要防的形态。`test_report_text_is_actionable` 因此断了四样：
行号 `L4`、判据名、原文 `42.7`、以及「换成什么」。

**CRLF 行号一致**：Windows 上编辑过的模板不该报错位（本仓库在 GRAPH-11 与 DESIGN-23
两次被 CRLF 咬过，这次直接把它写成一条测试）。

**插槽里的数字不是示例数字**：`{{block:b-1}}` 的 `1` 先被遮掉再扫——
承 DESIGN-28 的实测教训（检查器把自己的产物拦了下来）。

## 5 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：四判据各 1~2 条（含双向插槽、未知 block/词条/插槽类型），
外加 `test_all_four_criteria_reported_together`（四条并列）、
`test_report_text_is_actionable`（输出文本四样）、`test_report_lists_one_line_per_issue`、
`test_clean_template_passes`（阴性对照）、`test_slot_digits_are_not_mistaken_for_example_numbers`、
`test_crlf_input_reports_the_same_lines`。共 14 条。
**②** 无冻结件偏离：纯判定模块，零触碰 `contracts/`。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：占位语法读 `flint/design/mock_syntax.py`（DESIGN-27 那张表），
未另抄一份；遮罩手法与 DESIGN-28 同源。
**⑤** 装载 ≈9k tokens，未超 40k。

## 6 一次 lint 返工

`ruff FLY002` 对「字面量列表直接 `join`」建议改 f-string。HTML fixture 用逐行列表更好读，
故把列表先命名再 `join`——既过规则，也保住「一行一句 fixture」的可读性。

## 7 verify

```
$ pytest tests/v04/design/test_solidify_validator.py -q  → 14 passed
$ pytest tests/v04/design -q                              → 121 passed
$ ruff check . --no-cache                                 → All checks passed!
$ mypy --strict flint                                     → 268 source files, no issues
```

卡上 cycles=2，实际 1。

## 8 产出

- `flint/design/solidify_validator.py`
- `tests/v04/design/test_solidify_validator.py`（14 条）
