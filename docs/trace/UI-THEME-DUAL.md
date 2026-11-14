# UI-THEME-DUAL trace — 整体转浅色 + 日夜双主题 + 报告屏移动端表格修复 @2026-08-01

## 0 本轮范围

三件：① 建日间/夜间双主题（默认跟随系统、可手动切换并持久化）；② 25 处调色板形状的类名转语义
token；③ 修报告屏表格在 390px 下被挤垮。附带：日间首页按新 landing 语言重做、首页 IA 精简、
新增对比度断言脚本。`web/` 一字未动；`contracts/` 与 `flint/domain/` 未动；零联网装包；零付费。

## 1 装载清单

- 探针：`scripts/ui_probe.py`（隔离环境 `C:\pwenv` 跑，playwright NEVER 进项目 .venv）
- 设计包：`前端设计/3D card carousel component/Flint 首页.dc.html`（hero 结构 + 文案）、
  `前端设计/Lumina landing page build/Flint Landing.dc.html`（IA + 页脚站点图）、
  `前端设计/*/_ds/.../tokens/colors.css`（纸感调色板权威值）
- 验收：`Claude design Flint 前端设计/.../04_技术约束清单.md`
- 改造对象：`app/globals.css`、`app/page.tsx`、`app/layout.tsx`、`components/theme-provider.tsx`、
  `components/report/*`、`components/honesty/channel-value.tsx`

## 2 双主题怎么建的

- `app/globals.css`：`:root` = 日间（默认）、`.dark` = 夜间；shadcn 映射块 `:root, .dark` 共用，
  值随语义 token 自动翻转。`@custom-variant dark (&:where(.dark, .dark *))` 让 Tailwind v4 认这个作用域。
- `app/layout.tsx:56-62`：接 `ThemeProvider`（next-themes 既有，无新依赖），
  `attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange`；
  `<html suppressHydrationWarning>`（next-themes 首帧前改 class，属预期差异，仅此一处）。
- `components/theme-toggle.tsx`：**三态**（日间 / 夜间 / 跟随系统）。刻意不是两态——
  「我没选过」与「我选了亮色」是两件事，不把默认伪装成用户意图。未挂载前不渲染选中态，避免 hydration 不一致。

**验收硬信号（本轮最关键）**：改造前 light/dark 两次截图字节数相同、token 取值相同 = 根本没有主题。
现在探针实测两套值**完全不同**：

| token | 日间 | 夜间 |
|---|---|---|
| `--background` | `#edeee6` | `#0a0a0b` |
| `--surface` | `#f7f8f3` | `#1a1a1c` |
| `--ink` | `#1b2a2e` | `#f2f4f7` |
| `--ink-2` | `#46565a` | `#9ca3af` |
| `--ink-3` | `#54646a` | `#8a929e` |
| `--spark` | `#b4472c` | `#ff6b4a` |

`html.class` 实测为 `light` / `dark`。

## 3 取色：实算，非目测

三条硬约束全部落地并写进 token 定义处的注释：

1. **`--spark` 双值**（`globals.css` 日间 `--spark` 段 / 夜间 `.dark` 段注释）：
   日间 `#B4472C`（纸底 4.63 PASS；`#FF6B4A` 在纸底只有 2.41 FAIL）；
   夜间 `#FF6B4A`（卡面 6.17 PASS；`#B4472C` 在暗底只有 3.21 FAIL）。owner 给的四个数我逐个实算复现，全部吻合。
2. **`--ink-3` NEVER 照抄 `_ds` 的 `#8B9799`**（纸底实测 2.57）。本项目 11px 元信息按正文级要求，
   故取 `#54646A`（最差底 4.84）。
3. **`--sulfur` NEVER 作文字色**（纸底 1.57），只作背景：黄底 + 深字 `--on-accent`（8.07）。
   脚本里以 `NEVER_AS_TEXT` 硬编码这条，一旦有人把它放进前景位即失败。

**我另外查出两处 owner 未点名的不达标**（据实记录，非邀功）：

- `_ds` 的 `--ink-2 #5A6A6E` 在**抬升层 `#E3E5DA`** 上只有 **4.43**，不达正文标准（纸底 4.83 才刚过）。
  故日间正文改取 `#46565A`（最差底 6.02）。
- `--rail` 原值（日间 `#B9BFAE` / 夜间 `rgba(255,255,255,0.20)`）压卡面均只有 **1.77 / 1.90**。
  rail 承载「虚线 = unknown / degraded / 保护只读」这套状态词汇，属传达信息的非文本元素，须过 3:1。
  改为日间 `#7E866F`（3.56）、夜间 `rgba(255,255,255,0.36)`（3.34）。
  **这是把 token 改到达标，NEVER 是把判据调松**——判据仍是 4.5 / 3.0 未动。
  （`--rule` 是纯分隔细线、不承载状态，故不入门。）

## 4 「25 处硬编码」的实情（**修正一处前提**）

owner 交代「25 处硬编码颜色…它们现在不会跟随主题翻转」。我回源核了，**前半对、后半不对**，据实更正：

- **实测这 21 处不是硬编码**：`bg-stone-100` 在 Tailwind v4 的 `@theme inline` 下解析为
  `background-color: var(--stone-100)`（我从 `:3001` 抓真实编译 CSS 逐字确认），
  也就是说**它们本来就是 token 驱动、会跟随主题翻转**。CSS 里也查无 Tailwind 默认 stone 值
  （`#f5f5f4` / `#e7e5e4` / `#fafaf9` 命中数 0）。
- **另 4 处 hex**：我用精确正则在 `className` / `style` 里搜，**真实硬编码颜色为 0 处**；
  松正则命中的 5 行全是 HTML 实体 `&#123;` 与注释里的说明文字，不是颜色。
- **但改名仍然必要，我照做了**：`--stone-50` 在暗色下取值为 `#0A0A0B`——一个叫「最浅石」的名字
  取值近黑，语义自相矛盾；再铺 18 屏就会被复制 18 次。故按语义改名，**21 处全部替换，零残留**：

| file:line | 原 | 现 |
|---|---|---|
| `app/deliverables/[id]/loading.tsx:32` | `bg-stone-100` | `bg-raised` |
| `app/deliverables/[id]/page.tsx:39` | `bg-stone-100` | `bg-raised` |
| `app/deliverables/[id]/page.tsx:56` | `bg-stone-100` | `bg-raised` |
| `app/gate/[jobId]/not-found.tsx:6` | `bg-stone-50` | `bg-base` |
| `app/gate/[jobId]/page.tsx:54` | `bg-stone-50` | `bg-base` |
| `app/gate/[jobId]/page.tsx:99` | `bg-stone-100` | `bg-raised` |
| `app/gate/[jobId]/page.tsx:114` | `bg-stone-100` | `bg-raised` |
| `app/gate/[jobId]/page.tsx:191` | `bg-stone-100` | `bg-raised` |
| `app/gate/[jobId]/page.tsx:352` | `bg-stone-100` | `bg-raised` |
| `app/page.tsx:120` | `text-stone-50` | `text-primary-foreground` |
| `app/page.tsx:204` | `text-stone-50` | `text-primary-foreground` |
| `app/page.tsx:211` | `bg-stone-100` | `bg-raised` |
| `app/page.tsx:322` | `bg-stone-100` | `bg-raised` |
| `app/page.tsx:444` | `bg-stone-100` | `bg-raised` |
| `app/plaza/loading.tsx:15` | `bg-stone-100` | `bg-raised` |
| `app/plaza/page.tsx:110` | `bg-stone-100` | `bg-raised` |
| `app/plaza/page.tsx:216` | `bg-stone-100` | `bg-raised` |
| `components/gate/gate-live.tsx:99` | `bg-stone-100` | `bg-raised` |
| `components/honesty/api-error.tsx:26` | `bg-stone-100` | `bg-raised` |
| `components/report/block-renderer.tsx:191` | `bg-stone-100` | `bg-raised` |
| `components/report/report-shell.tsx:88` | `text-stone-50` | `text-primary-foreground` |

（`app/page.tsx` 的三处在其后的重写中已随文件更新；行号为替换当时的位置。）
新增语义色：`--base` / `--raised` / `--indigo` / `--sulfur` / `--on-accent` / `--cta-bg` / `--cta-fg`。

## 5 首页：日间新语言 + IA 精简

- **日间**（`app/page.tsx`）：纸底 + 88px 级大标题 + 克制留白 + **硫磺黄底 CTA**，
  「可行」二字走 `.accent-word`（日间 = 硫磺高亮划线）。**零 glow**——
  `.glow-frame` / `.glow-halo` / `.glow-bloom` 在 `globals.css` 里全部挂在 `.dark` 作用域下，
  日间自动退化为 1px 实边卡 / 光晕不渲染，故浅底上不会糊成脏污。
- **夜间**：沿用已建 glow 版（8px 渐变描边 + 45px 光晕 + 渐变字），同一份 JSX，零主题分支逻辑。
- **文案**采纳设计包：标题「每日热点，敲成可行的报告。」，副标即三条铁律本身——
  「知道什么就说什么，不知道就明说——每个数字都带出处，每个空缺都留着形状。」
- **IA 精简**：首页 **4100px → 1685px（日间）/ 1754px（夜间）**。
  13 步旅程与字段对照表迁往**新建的 `/how-it-works`**；首页只留 导航 + hero + 4 条证据点 + CTA + 页脚。
- **页脚站点图**取自 Lumina，但**只把已建的目的地做成链接**；未建的渲染为不可点文字 + 「· 未建」标记，
  并在页脚底部写明这条规则。NEVER 做成看起来能点的假链接（技术约束清单第 32 条同精神）。

## 6 报告屏表格移动端修复（本轮最实质的功能修复）

**根因（回源确认，非猜）**：`components/honesty/channel-value.tsx` 原把 `display` 按
`text-[31px]` 主值渲染；而 `block-renderer` 在表格里传的是 `display={cell.fact_id}`——
因为**冻结契约的 `FactCell` 只有 `fact_id`，没有可读数值**。于是标识符被按标题级字号画出来：
390px 下 `fact-demo-vecdb-cost` 占掉四行大字，把同行人读内容「向量库托管」挤成一字一行。
引用标识符比内容本身还响 = 主次颠倒。

**修法**（两处）：

1. `channel-value.tsx` 全文重写：标识符降为 **12px 等宽 + `break-all` + `min-w-0`**，
   通道字形印记 `F / ¥ / P` 不变（非颜色载体保持）。`quantity` 仍原样 `× {quantity}`，NEVER 乘算。
2. `block-renderer.tsx` 表格：**同一份 DOM**，靠 display 切换——
   `<768px` 时 `thead` 走 `sr-only`（仍供读屏）、每个 `tr` 变一张卡、每个 `td` 前置自己的列名；
   `≥768px` 恢复标准表格。**NEVER 靠横向滚动硬挤列**（原 `overflow-x-auto` 已移除）。
   行首列（人读的行名）升为 15px medium 主体，宽屏再给 `md:w-[26%] md:min-w-[8em]`，
   避免被长标识符挤到断词。

**实测（探针截图，我逐张看过）**：390px 下每行成卡，「向量库托管」「推理算力」各自一行完整可读，
标识符退到 12px 从属层级；**横向溢出 0**（探针 `问题计数: 0`）。日夜两套主题均已看过。

## 7 新增 `scripts/check_contrast.py`（把硬约束变成机器可验）

- 直接读 `globals.css` 两个作用域的真实 token 值，按 WCAG 2.1 实算 **22 对**实际会同屏出现的组合 × 2 套主题；
  正文 <4.5 或大字 <3.0 即打印明细并 **exit 非零**。
- 额外锁死：`--sulfur` 出现在前景位即失败；两套主题若关键 token 同值即失败（防「主题没真正翻转」回归）。
- **脚本自己踩过两个坑，已写死在注释里**：① 选择器要在行首匹配，否则
  `@custom-variant dark (&:where(.dark, .dark *))` 里的 `.dark` 先命中；
  ② **要先剥 CSS 注释**，否则文件头注释里写的 `:root = 日间` / `.dark = 夜间` 会被当成选择器，
  把紧随的块误认作该作用域——表现正是「两套主题取值相同」的假象。我第一版就被自己这个 bug 骗过一次。

## 8 验证（真实数字，全部本人跑）

| 项 | 命令 | 结果 |
|---|---|---|
| 对比度门 | `.venv/Scripts/python.exe scripts/check_contrast.py` | **两套主题 × 22 对全部达标，exit 0** |
| 类型门 | `npx tsc --noEmit` | **exit 0** |
| 后端诚实态 | `node scripts/check-connectivity.mjs` | **94 / 94，exit 0** |
| 前端渲染诚实态 | `node scripts/check-screens.mjs` | **51 / 51，exit 0** |
| 坏链路 5xx | `node scripts/check-degraded.mjs 500` | **15 / 15，exit 0** |
| 坏链路 不可达 | `node scripts/check-degraded.mjs down` | **18 / 18，exit 0** |
| 探针 | `ui_probe.py`（两主题 × 桌面/移动 × 首页/报告） | **问题计数 0**（横向溢出 / 控制台 error / 打不开） |
| `web/` 未受影响 | `cd web; npm test -- --run` | **11 文件 / 63 测全绿** |
| 后端 lint | `ruff check .` | **All checks passed** |
| 后端类型 | `mypy --strict flint` | **224 文件净** |

`check-screens` 是 DOM 断言、与主题无关，**51/51 保持全绿**——说明整套换肤没有破坏功能正确性。

**顺带修了 `ruff check .` 的既存红**：`scripts/ui_probe.py` 带 3 个 ruff 错误
（`B023` ×2：两个事件处理器闭包捕获循环变量 `errs`，属**真实潜在 bug**——
`errs` 每轮重新赋值，处理器可能写进后一轮的列表；`BLE001` ×1）。
探针是本轮才加入仓库的文件，故全局 ruff 门在我接手时已是红的。
已修：用默认参数把 `errs` 绑进闭包；宽捕获处加 `# noqa: BLE001` 并写明理由（playwright 失败型别较杂，
探针只需如实记一笔并继续）。修后 `ruff check .` 全绿。

## 9 我真看过的截图 / 我没验证的

**真看过（`.ui-probe/*.png`，逐张 Read 过）**：
- 日间首页桌面、夜间首页桌面（glow 仅在夜间出现、日间为实边卡，已肉眼确认）
- 日间报告屏桌面（修列宽前后各一次）、夜间报告屏移动、日间报告屏移动
- 日间 / 夜间 styleguide 全屏（确定度阶梯 / 三通道 / advisory vs blocking / verdict 四档 /
  保护块 / 图表与缺口占位 / 出处槽六印记——两套主题下都可分辨）
- 日间 / 夜间 5xx 错误屏

**据此可以说的**：两套主题都成立、状态记号在两边都有非颜色载体（图形 / 虚实 / 切口）、
移动端表格不再溢出。

**没验证（不背书）**：
- **409 / 503 的屏上呈现未截图**：它们要点「导出」才出现，探针是只读的、不点按钮。
  两者的**功能面**已验（后端 curl 实测 markdown→409、pdf→503；`check-connectivity` 94 项含这两条；
  `report-shell` 真打后端不预判），但**没看过那两张屏在日夜两套主题下的样子**。
- `speculative` 态只在 styleguide 词汇表里看过，**未在真实报告数据上出现过**（夹具无 speculative span）。
- `next build` 生产构建未跑（只跑 dev + tsc）。
- 移动端只测了 390px 一个宽度；平板区间未测。
- `prefers-reduced-motion` 分支代码在场，未实机验证。
- 真实显示器 / 广色域下的观感未测（探针是无头 Chromium）。

## 10 给 owner 的判断点（我不代拍）

1. **`--ink-2` 与 `--rail` 我改动了 `_ds` 的权威值**（理由见 §3：原值实算不达标）。
   若你要严格保 `_ds` 原值，那就得接受抬升层上的正文低于 AA，或把抬升层调亮——两条路都要你拍。
2. **fact 值的字号**：为修「ID 比内容响」，`FactValue` 统一降到 12px。副作用是 styleguide 里
   那个**真数值** `12,480` 也跟着变小了。生产路径上契约只给标识符、没有数值，故我按标识符处理；
   若将来契约给出真数值，应按「数值大、ID 小」再分一层。
3. **日间 CTA 用硫磺黄底**（设计包语言）。它与告警铁锈是不同色相、且铁锈只在告警态出现，
   但两者同属暖色族——若你觉得首页黄按钮会削弱告警色的独特性，我改成中性反白按钮。
4. **页脚 9 个「未建」标记**会直接暴露在营销首屏上。这是诚实做法，但对外观感偏「未完成」。
   若你要更成品的观感，可以先删掉未建条目只留 3 条真链接——**那是产品取舍，我不替你删**。
5. **费用估算器按你指示本轮未并入**（无出处第三方价格 / 粉橙渐变挪用告警暖色族 / ¥1,299 报价而支付未建），
   已登记待你改造后再议。

## 11 落盘清单

| 文件 | 改动 |
|---|---|
| `V0 files 前端设计/app/globals.css` | **重写**：`:root` 日间 + `.dark` 夜间双作用域、语义改名、glow 收进 `.dark`、`.accent-word` 双形态 |
| `V0 files 前端设计/app/layout.tsx` | 接 `ThemeProvider`（system 默认 + 持久化）、`suppressHydrationWarning` |
| `V0 files 前端设计/components/theme-toggle.tsx` | **新增**：日间/夜间/跟随系统 三态切换 |
| `V0 files 前端设计/app/page.tsx` | **重写**：日间 landing 语言 + 夜间 glow 共存、IA 精简、页脚站点图（未建即标注） |
| `V0 files 前端设计/app/how-it-works/page.tsx` | **新增**：承接 13 步旅程 + 三层数据 + 字段对照 |
| `V0 files 前端设计/components/honesty/channel-value.tsx` | **重写**：标识符降为从属层级、可断行 |
| `V0 files 前端设计/components/report/block-renderer.tsx` | 表格窄屏堆叠（同一 DOM）、行首列升为主体、去掉横向滚动 |
| 21 个 token 类名替换 | 见 §4 表 |
| `scripts/check_contrast.py` | **新增**：双主题对比度门 |
| `scripts/ui_probe.py` | 修 3 个 ruff 错（B023 闭包绑定 = 真实潜在 bug；BLE001 加理由 noqa） |

**未动**：`contracts/`、`flint/domain/`、任何后端端点响应形状、`web/`、`lib/types.ts`、`lib/api/*`、
`components/ui/**`、`lib/mock/**`。
