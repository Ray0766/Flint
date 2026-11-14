# DESIGN-28 trace — [隔离·G3] 固化管道（示例 → 插槽 → 注册）@2026-08-03

> **隔离带卡 + owner_review**。按 DEC-000 默认照做；开工前复查 `DECISIONS-v04.md`
> 无划除记录（工单 §11-③：认同，明确不推荐划掉）。
> 本卡在 **DESIGN-31（G6 门）之后**做——顺序理由见 `docs/trace/DESIGN-31.md#1`。

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-28`；
- context_refs：`WORKORDER-v04.md#11`（③承重墙全文）、`WORKORDER-v04.md#4-I10`
  （`TemplateRecord` 的 slots 非空与 checksum 绑定）、`contracts_v04#SolidifyResult`；
- 前置产物：`flint/design/templates/registry.py`（DESIGN-30）、
  `flint/design/prod_render.py`（DESIGN-31 的插槽口径）、
  `web/design/mock-identity/mock-syntax.json`（DESIGN-27 定的占位语法表）。
- 实测装载 ≈ 11k tokens，未超 40k。

## 2 固化在做的是一件很具体的事

把探索期那份「长得对但内容是假的」样板，变成一份**只剩形状**的模板。
换不干净的后果不是不好看——那段示例数字会跟着模板进入生产渲染，
**而生产渲染只认模板、不再看内容**（G6 已立）。这一步是最后一次能拦住它的地方，
所以宁可拒绝也不放行。

**水印属于样板不属于模板**：留着的话正式产物上会印着「这是样板」，
那比漏一个示例数字更难解释。

**一个槽都没标 = 不是模板**：那是一张静态页，固化它没有意义却会占着 template_id
（与契约 `TemplateRecord.slots` 非空同款理由）。

## 3 占位语法表只有一份（跨语言共用）

四条模式写在 `web/design/mock-identity/mock-syntax.json`（DESIGN-27 定），
本卡新增 `flint/design/mock_syntax.py` **读同一份**、不另抄一遍。

两份表分叉的后果很具体：一个数字能过固化却在导出时被拒（或反过来），
而两边各有一半的道理。表放在 `web/` 只是因为它诞生于前端闸门——
**位置不重要，只有一份才重要**。

## 4 一处「检查器把自己的产物拦下来」的实测

首轮 8 条红，根因一句话：`{{block:b-1}}` 里的 `1` 被「具体数字」模式命中，
于是刚换好的插槽反过来被判成「示例数字残留」。

改法是扫残留前先把插槽本身**遮掉**（空格化）——与 DESIGN-27 里「先摘来源再扫数字」
是同一手法。这类 bug 的共同形态是：**同一段文字被两把尺子量到**，
而其中一把量的是另一把刚写下的东西。

## 5 自审报告（§4.6，本卡 self_review=true）

**①** acceptance ↔ 测试：

| acceptance | 测试名 |
|---|---|
| 固化产物注册进 G5 | `test_solidified_template_lands_in_the_registry` |
| 插槽清单与内容一致 | `test_registered_slots_match_the_html`（两侧各算一遍再比）、`test_marked_regions_become_slots` |
| solidify_result 事件 | `test_event_carries_empty_violations_on_success`（accepted=True / reason=None / kind 逐字） |
| （示例不残留） | `test_example_content_is_gone_after_solidifying`、`test_leftover_example_number_is_rejected`、`test_blocked_solidify_reports_every_violation` |
| （其它纪律） | `test_watermark_is_stripped_from_the_template`、`test_unmarked_mock_is_rejected`、`test_registry_unavailable_blocks_solidify_but_says_what_still_works`（E6：报错要说清探索仍可继续）、`test_module_never_writes_its_own_registry` |
| （闭环） | `test_solidified_template_renders_in_production`——固化出来的东西，G6 门认得 |

**②** 无冻结件偏离：零触碰 `contracts/` 与 `contracts_v04/`；checksum 用契约那份
（承 DESIGN-31 的教训），`SolidifyResult` 四字段逐字。
**③** 无禁用词：三份产出 0 命中。
**④** 复用断言在位：注册走 `register_template`（AST 断言且不建第二份存储）；
占位语法读 DESIGN-27 那张表；插槽正则与 DESIGN-31 的 `SLOT_PATTERN` 在测试里对齐。
**⑤** 装载 ≈11k tokens，未超 40k。

## 6 verify

```
$ pytest tests/v04/design/test_solidify_pipeline.py -q  → 12 passed
$ pytest tests/v04/design -q                             → 107 passed
$ ruff check . --no-cache                                → All checks passed!
$ mypy --strict flint                                    → 267 source files, no issues
$ cd web && npm test -- --run design/mock-identity        → 17 passed（DESIGN-27 断言不受影响）
```

卡上 cycles=2，实际 1。

## 7 产出

- `flint/design/solidify.py`、`flint/design/mock_syntax.py`（跨语言共用占位语法表）
- `tests/v04/design/test_solidify_pipeline.py`（12 条）
