# DESIGN-15 trace — 导出接线（三种导出走既有管线）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-15`；
- context_refs：`WORKORDER-v04.md#6`（H3 行）、`contracts/protocols.py#Renderer` 注释；
- 前置产物：`flint/render/gatekeeper.py`（`check_export` / `guarded_render` / `ExportBlocked`）、
  `flint/render/pdf.py`、`flint/spec/pack_zip.py#build_zip`、`tests/v04/_source_scan.py`。
- 实测装载 ≈ 9k tokens，未超 40k。

## 2 为什么一行渲染逻辑都不写

**导出门禁是「blocking 未处理就不许导出」这条铁律的唯一落点**。设计台若自建一条
导出路径，那条路上没有门禁——一份还挂着 blocking 复核的产物就能直接导出去交给客户，
而界面上看不出任何异常。

同理，新写一个 HTML/PDF 渲染器意味着同一份内容有两种排版：用户在预览里看到的、
与导出拿到的会在某处不一样，而没人说得清哪一份才算数。

所以本模块只做三件事：**校验产物非空 → 过既有门禁 → 交既有管线**。
它不 import `zipfile`、不 import `weasyprint`、不定义任何 `render_*`（三条断言各一）。

**三条路都过同一道门**：HTML / PDF / vibe_pack zip 各有一条「blocking 时抛
`ExportBlocked`」的测试——只测一条的话，另外两条完全可能绕开门禁而没人发现。

**advisory 不拦**（审11 口径）：拦住的话用户会以为自己被系统卡死了，而那些是提示级的。

**产物字节逐字进入导出**：承 DESIGN-02 零构建、DESIGN-03 三接口不改字节，
用一段带 `style`/`data-x`/`&` 的样本验进出相同。

## 3 一次判据修（写窄了）

`零新导出器` 初版用「本模块定义的函数集合恰等于三个入口」来断，于是把私有校验器
`_require_design` 与 PDF 那条转调用闭包也算成了违规。判据改为：
**无 `render_*` 定义** + **公开的 `export_*` 恰是三个**。
把辅助函数也算进去只会逼人给它们改名，而不会挡住真正的重复实现。

## 4 自审报告（§4.6，本卡 self_review=true）

**①** acceptance「三种导出调用栈 import 自既有管线（H3）；零新导出器」↔ 测试：

| 测试名 | 覆盖点 |
|---|---|
| `test_module_imports_the_existing_pipeline_only` | AST：`flint.render.gatekeeper` / `guarded_render` / `flint.spec.pack_zip` / `build_zip` |
| `test_module_defines_no_renderer_of_its_own` | 无 `render_*` 定义 + 公开 `export_*` 恰三个 |
| `test_no_zipfile_or_weasyprint_touched_directly` | 不绕过管线直接玩 zip/PDF 库 |
| `test_*_blocked_when_blocking_review_open` ×3 | 三条路各自过门禁 |
| `test_advisory_does_not_block_any_of_the_three` | advisory 不拦 |
| `test_html_export_keeps_the_design_bytes_verbatim` | 导出不是二次渲染 |
| `test_empty_design_is_rejected` | 空产物不导出 |

**②** 无冻结件偏离：零触碰 `contracts/`；`Block` 形状按既有字段构造。
**③** 无禁用词：两份产出 0 命中。
**④** 复用断言在位：H3 三条（见上表）；源码扫描走共享 `tests/v04/_source_scan.py`。
**⑤** 装载 ≈9k tokens，未超 40k。

## 5 verify

```
$ pytest tests/v04/design/test_export_reuse.py -q  → 10 passed
$ pytest tests/v04/design -q                        → 51 passed
$ ruff check . --no-cache                           → All checks passed!（--fix 归位一处 import 排序）
$ mypy --strict flint                               → 261 source files, no issues
```

## 6 产出

- `flint/design/export.py`
- `tests/v04/design/test_export_reuse.py`（10 条）
