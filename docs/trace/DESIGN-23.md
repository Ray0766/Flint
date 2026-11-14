# DESIGN-23 trace — 禁置信度可视化 + 图标纪律（lint）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`（三条铁律）、`worker.md`、卡片 `tasks-v04.json#DESIGN-23`；
- context_refs：`WORKORDER-v04.md#5-G`（G29/G30 一行）；
- 前置产物：`web/public/_ds/…/_ds_bundle.js`（几何印记 `Mark` 的画法，DESIGN-05 查过）、
  `tools/no_external_fonts.mjs` 与 `tools/no_hardcoded_models.mjs`（同族扫描器）。
- 实测装载 ≈ 8k tokens，未超 40k。

## 2 为什么禁「置信度可视化」

一根 78% 的进度条画在一条结论旁边，读者会把它当成「这件事有 78% 的把握」——
而系统里**根本没有这个数**：Gate① 出的是 A/B/C/D 四分类，证据要么在要么不在。
那根条子是画上去的，它把一个不存在的精度感塞给读者，而他会据此下注。

所以进度条只准绑两种东西：`JobView.progress`（一次运行真的跑到哪了）与骨架屏
（还没加载出来）。两者都是「进度」，不是「把握」。

## 3 修掉一处真违规：`BlockView` 的 ⚠

扫描发现 `web/components/blocks/BlockView.tsx:22` 用 `⚠ ` 当争议记号——
那是 v0.4 之前的 L0 组件，早于 G30 的图标纪律。

改法照 `_ds` 的既有语义：争议 = **斜纹方**（几何印记，组件内联渲染），
故渲染一个带 `data-testid="disputed-mark"` 与 `aria-label` 的标记元素，emoji 去掉。
连带更新它的既有测试：断言从「文本里有 ⚠」改成「标记元素在场 **且** 文本里没有 ⚠」——
需求本来就是「争议要可见」，不是「⚠ 要可见」，所以这是判据回到语义，不是放水。

emoji 当图标的三个问题（写进扫描器 docstring）：各平台字形不同、颜色不受 token 控制、
读屏会把它读成「警告标志」而不是这套系统里的「争议」。

## 4 扫描器的两次自伤，以及为什么抽了共享模块

本卡写扫描器时，剥注释那段逻辑连着出了两次问题，**方向相反**：

1. **假绿**（DESIGN-21 已记）：`//` 前不判冒号 → `https://fonts…` 被当成注释起点，
   整条 URL 被剥掉，扫描器报「0 处」而其实一处没看见。
2. **假红**（本卡实测）：不归一 CRLF → 行尾留着回车符，JS 里 `.` 不匹配它、
   无 `m` 的 `$` 只认串尾，于是整行注释一个字符都剥不掉，CRLF 文件里的注释被当成代码。
   这与 GRAPH-11 在 `i18n_scan` 上实测到的是**同一个坑**。

两次都在同一处逻辑上，而这段逻辑已经被三把扫描器各抄了一遍。故抽出
`tools/_scan_lib.mjs#codeOnly`，三把尺子改用同一份：**改一次，三把一起对**。
（前端测试侧的 `web/test-utils/source.ts`、Python 测试侧的 `tests/v04/_source_scan.py`
是同一动作的另两个落点。）

## 5 自审报告（§4.6，本卡 self_review=true）

**①** acceptance「进度条绑定仅 JobView.progress/骨架屏；emoji 图标零命中」↔ 八条阴性对照（实跑）：

| 场景 | 期望 | 实测 |
|---|---|---|
| `width: ${confidence*100}%` | 命中 | exit 1 |
| `className="confidence-bar"` | 命中 | exit 1 |
| `width: ${job.progress*100}%` | 放行 | exit 0 |
| `className="skeleton"` + width | 放行 | exit 0 |
| 代码里 `"✅ done"` | 命中 | exit 1 |
| 注释里的 ⚠ | 放行 | exit 0 |
| 注释里的 ⚠（**CRLF 文件**） | 放行 | exit 0 |
| 测试文件里的 ✅ | 放行 | exit 0 |

**②** 无冻结件偏离：零触碰 `contracts/`；`BlockView` 改的是渲染形态，判别联合与字段未动。
**③** 无禁用词：本卡产出 0 命中。
**④** 复用断言在位：三把扫描器共用 `_scan_lib#codeOnly`；争议记号语义取自 `_ds`（斜纹方）。
**⑤** 装载 ≈8k tokens，未超 40k。

## 6 verify

```
$ node tools/lint_no_confidence_viz.mjs web   → 置信度可视化 0 处、emoji 0 处，exit 0
```

回归：前端全套 **473 passed / 55 files**（含被改过的 `components/blocks` 13 条）；
typecheck 干净；`i18n_scan web/components` exit 0；`scan_ds_assets` exit 0；
`no_external_fonts web` exit 0；`no_hardcoded_models web` exit 0。

## 7 产出

- `tools/lint_no_confidence_viz.mjs`、`tools/_scan_lib.mjs`（三把扫描器共用剥注释口径）
- `tools/no_external_fonts.mjs`、`tools/no_hardcoded_models.mjs`（改用共享口径）
- `web/components/blocks/BlockView.tsx`（⚠ → 几何印记）、`BlockView.test.tsx`（判据回到语义）
- `web/messages/{zh,en}.json`：各 +1 key（90 键，键集一致）
