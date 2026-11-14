# UIR-03 · 基础层：通用件、控件、字号、面板、人话（@2026-11-14）

卡单：`docs/trace/UIR-PLAN.md`。本卡合并了原卡单里的 `UIR-03`（空态）、`UIR-04`（报告屏居中）、
`UIR-05`（总览人话）、`UIR-06`（工作台字号）四张——动手之后发现它们是同一层的事，分开做要跑四遍门。
对应问题 2、3、4、6、7。

## 一、装载清单

`web/components/shell/` 下六个状态件 · `web/lib/ScreenFetchState.tsx` ·
`web/components/favorites-library/FavoritesLibrary.tsx:100-120` ·
`web/components/account-billing/AccountPanel.tsx`、`BillingPanel.tsx` ·
`web/components/project-overview/ProjectOverview.tsx` · `web/app/jobs/[id]/page.tsx` ·
`web/lib/i18n/enumLabel.ts` · `tests/v041/test_enum_labels.py:40-150` ·
`tools/check_design_constraints.mjs:150-165`（A5）· `_ds/tokens/typography.css`、`spacing.css` ·
`web/app/globals.css` 的 `.data-row`、`.screen--longform`、`.workbench` 三段。

## 二、看到的（比卡单里写的更普遍）

不只是广场。这些通用件在 `globals.css` 里**一条规则都没有**：

- `.state` 一族：空态、加载、错误、无权、断线（`web/components/shell/` 下五个组件共用）；
- `.screen__state` 一族：`ScreenFetchState` 的加载 / 未配置 / 失败；
- `.account*`、`.billing*`、`.overview` 本体、`.favorites__empty`；
- 所有没有类名的 `<button>`、`<select>`、`<input>`。

所以十几屏长成同一个样子：左上角几行 14px 的字，其余整屏空白。

另有一处既有的错：`.data-row__label { color: var(--text-label) }`，而 `--text-label` 是**字号** token（12px）。
当颜色用是无效值，浏览器回退成继承色——标签与值一直是同一个颜色。

## 三、改动

**样式**（`web/app/globals.css` 末尾追加，全部取 `_ds` token）：

| 段 | 做了什么 |
|---|---|
| 正文区字号 | `.screen__body` 默认 14 → 16；顶层段落限行长 |
| 数据行 | 限宽 60em，标签列定宽 9em，标签颜色改成 `--text-secondary`（更正上面那处错） |
| 没有类名的控件 | 兜底长相：高 36px、有边有底；只管 `:not([class])` 的，特异度为零 |
| 状态件 | `.state` / `.screen__state` 居中成一块；错误与无权是实线墨色边；断线是 `--ochre` 的一条；加载是三条灰带 |
| 收藏空态 | 与通用空态同一块长相 |
| 账户、计费、项目总览 | 各成一块有底有边的面板；账户的身份那几行排成两列 |
| 长文屏 | 那一列居中；字号行高取 `--text-longform` / `--lh-longform` |
| 最小字号 | `.screen__body` 与 `.workbench` 里把 `--fs-12` 重定义成 13px（工作台另把 `--fs-13` 提到 14px） |

**人话**（三处，原值都留在 `data-*` 上）：

| 屏 | 改前 | 改后 |
|---|---|---|
| 项目总览 · 作业 | `proposal`、`gate1_analysis` | 「计划书」「Gate① 分析」，原值在 `data-job-kind` |
| 项目总览 · 交付物 | id 印两遍 | id 一遍 + 「报告」，原值在 `data-deliverable-type` |
| 作业屏 · 状态 | `drafting`、`failed` | 「起草中」「失败」，原值在 `data-job-status` |

为此在 `web/lib/i18n/enumLabel.ts` 加了两族：`job_kind`（7 个值）、`deliverable_type`（7 个值），
真相源是冻结件里那两行 `Literal`；`zh.json` / `en.json` 各加 14 个键。
`tests/v041/test_main_chain_walk.py` 的取证改成先读 `data-job-status` 属性、读不到再读文字。

## 四、判据先行（人话那一半）

- `tests/v041/test_enum_labels.py`：族表对真相源那条参数化加两行，改前 `2 failed`；
- `web/__tests__/app/chain_ui.test.tsx`：加三条（作业标签、交付物标签与 id 只出现一次、作业屏状态），改前 `3 failed`。

实现后都过。样式那一半没有新写判据，理由与 `UIR-01` §四相同。

## 五、三次自己弄错、当场改掉的

1. **兜底控件样式漏进了带类名的控件**。第一版只把选择器包进 `:where()`（特异度为零）。压不过既有规则没错，
   可既有规则**没写到的属性**照样生效：广场卡堆那排小圆点（`.plaza-stack__dot`）没写 `min-block-size`，
   被撑成 36px 高的竖条。真浏览器里看到的。改成只管 `:not([class])`；改后圆点量回 8×8。
2. **错误态占用了被保留的强调色**。第一版给错误与无权用了那个只留给阻塞标、导出被拦、服务不可用三处的颜色，
   `tools/check_design_constraints.mjs` 的 A5 拦下，连带三条判据红。它拦得对，改成墨色实线边。
3. **一处诊断错了**。工作台字号提上去之后量到中栏栏头越出栏边 12px，我加了一条折行规则。
   随后把字号临时调回去再量，仍是 12px——那是它自己的负外边距，与字号无关。那条规则撤掉了。

## 六、验证

真浏览器，1920×1080：收藏空态居中成块；导出屏五行限宽、按钮有了长相；语言设置三个控件有边有底；
账户、计费、总览成面板；报告正文居中；总览里是「计划书 | 失败」「报告 | 第 1 版」；
工作台三栏 56 个文字节点从「50 个 12px、6 个 13px」变成「50 个 13px、6 个 14px」；
卡堆圆点 8×8；广场无横向溢出。
390×844：项目总览、报告、账户三屏 `scrollWidth == 390`。
暗色（`prefers-color-scheme: dark`）：广场底 `rgb(25,22,18)`、卡 `rgb(33,29,23)`、字 `rgb(249,240,226)`，跟着主题翻了。
`scripts/check_contrast.py`：两套主题 × 22 对组合全部达标。

五条门（最终树单跑）见台账本卡 verified 那一条。

## 七、没有做的

- `/clusters/[id]`、`/combo`、`/gate/[id]`、`/topics/[id]`、`/workbenches/[id]`、`/share/[token]`、
  质量卡 / vibe_pack / 干预记录三屏：只吃到了基础层（字号、控件、状态件），没有逐屏重排；
- 计费屏那句「本端点 NEVER 拿一个 0 元或一个假额度冒充已启用」是后端回的说明原样上屏，没有动
  （`BACKEND-PROSE-EMBEDS-RAW-ENUM` 同一类）；
- 报告正文里的 id（`fact-…`、`cit-…`）仍原样印着，要 owner 先说它们该显示成什么；
- 英文界面一屏都没看；新加的 14 个英文标签是我写的，没有进 `en.review.json` 的机审。
