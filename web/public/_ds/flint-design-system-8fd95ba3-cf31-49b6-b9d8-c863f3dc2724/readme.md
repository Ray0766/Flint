# Flint 燧石 · Design System

Flint 把每日热点线索沉淀成可行性判定与深度报告。这套设计系统的隐喻是**一本手工装订的野外研究笔记本**：麻纸肌理、藍染封皮、贴上去的标签纸、盖过的印、手绘标本图、特意留出的空白。

三条性格：
1. **有手作的温度** — 纸纹、印记、插画、手绘线条是正当材料，不是装饰噪音。
2. **有色彩，但有纪律** — 色彩用在材质与叙事上，不用来编码数据状态。
3. **精确的地方绝对精确** — 数据区安静、对齐、等宽。温度在四周，准确在中间。

营销面（首屏）与工具面（功能屏）共用同一套材质与色彩，但**浓度不同**：首屏满浓度（字阶与间距取上端、纸纹 8%），功能屏是低饱和版本（下端、纸纹 ≤4%）。

**来源**：用户提供的 `DESIGN.md` 规则书（粘贴文本，无 Figma / 无代码库 / 无 logo 资产）。界面语言：简体中文。目标载体：Next.js App Router + Tailwind + shadcn/ui。

**没有 logo**：来源未提供任何品牌标识。凡需要品牌落款处，用 display 字体排「Flint 燧石」字样，不要绘制标志。

## CONTENT FUNDAMENTALS

- **语言**：全部简体中文；英文只出现在术语、id、单位与全大写小标签（如 `SOURCE`、`REPORT`）。
- **语气**：克制、笃定、如实。系统知道什么就说什么，不知道就明说 —— 空态与缺口写「接口未提供出处」「资料缺口」，NEVER 用生成文字或含糊话填补。
- **人称**：对用户不称"您"，用"你"或不出现人称；系统自述用"Flint"。
- **句式**：短陈述句，少感叹号。营销面允许一句有力的隐喻（"把热点敲出火花"），功能面只写事实。
- **数字**：散文正文里不出现裸数字；一切数值走 `ChannelValue`（带类型化出处）。
- **emoji**：NEVER。图标也不用 emoji / 图标字体，用小尺寸单色记号 + mono 短标签。
- 示例（功能面）：「该判定基于 3 条已证事实。」「此段为推测，无证据支持，不提供溯源。」「导出被阻断：存在 1 项待处理复核。」

## VISUAL FOUNDATIONS

- **色彩**：生纸底 `--paper #EDEEE6`（微灰绿，NEVER 暖奶油）+ 深青黑墨 `--ink #1B2A2E`。三个性格色：藍染 `--indigo #2E4A7D`（结构、链接、印记、已证）、硫磺 `--sulfur #E8B93C`（重点、CTA、首屏主角）、铁锈 `--rust #B4472C`（唯一告警色，全站只出现三处：阻塞级复核标、导出被阻断 409、服务不可用 503）。苔绿 `--moss #6B7A5A` 只做插画与纹理辅助。装饰域随便用；语义域按 tokens/·§状态标记体系受限。
- **字体**：display = 得意黑（Smiley Sans Oblique，斜切紧凑，只用于首屏大字与页面级标题，NEVER 退回宋体）；body = Inter + Noto Sans SC（中英分栈）；mono = IBM Plex Mono + `tabular-nums`（一切带出处的数值、id、时间戳）。中文 NEVER 假粗；正文字距 0；仅全大写英文标签 0.04em。
- **字阶** 12/13/14/16/20/25/31/48/72/112 · 界面正文 14 · 长文 16（行高 1.8，栏宽 max 34em）· 首屏大字 72–112（行高 1.15）。
- **间距** 4/8/12/16/24/32/48/64/96/160；首屏取上端，功能屏取下端。
- **圆角**：2px 表格与数据面 / 8px 卡片、贴纸 / 999 仅标签纸。
- **背景与材质**：全站底层麻纸噪点（SVG 生成，≤4%，首屏 8%）；贴纸 = `--paper-2` 底 + ≤1.5° 旋转 + 极淡投影；压痕 = 内阴影 `--emboss`；网点、划线、便条横线、缝线等纹理见 `tokens/texture.css`。无渐变、无玻璃拟态、无发光。
- **插画**：单线手绘 + 单色平涂，配色 indigo/sulfur/moss；题材：燧石与火花、标本册、印章、放大镜、留白的页。只出现在空态、缺口占位、首屏、引导页，NEVER 进数据区。不用 3D、渐变网格、吉祥物、摄影图。
- **阴影**：几乎没有。贴纸 `--shadow-sticker` 极淡；浮层 `--shadow-overlay`。卡片默认无影，靠 1px `--rule` 边与亮一档的 `--surface` 分层。
- **交互态**：hover = 底色加深一档或下划线变硫磺；press = 位移 1px + 投影收拢（凸版按下去的感觉）；focus = 2px indigo 外描边。禁用 = opacity .45。
- **动效**：首屏允许一段 ≤1.2s 编排入场（一次讲完不循环）+ 滚动分段揭示；功能屏只有浮层展开/折叠等克制过渡。尊重 `prefers-reduced-motion`。
- **图表**：表是真相，图只是摘要 —— 图表区只渲染占位（`ChartPlaceholder`），零数据点，不引图表库。可靠度 NEVER 用进度条/百分比/星级/雷达图。
- **状态标记铁规**：每个状态必须同时有非颜色载体（记号形状/边缘质地/字体/底纹）。八态详见 `components/status/`。

## ICONOGRAPHY

来源未提供图标集。本系统**不用图标字体、不用 emoji、不引 CDN 图标库**；识别物是「印记」：小尺寸单色几何记号（实心方 = 事实、空心方 = 价格、括线 = 涉我、三角 = 阻塞、斜纹方 = 争议）+ `--font-mono` 短标签，全部由组件内联渲染。少量单线插画（空态用）在 `components/status/EmptyState.jsx` 内，取材燧石/火花/纸页。若产品后续需要通用图标集，建议补充 1.5px 描边的单线集并经用户确认 —— 目前刻意不添加。

## 目录索引

- `styles.css` — 全局入口（只有 @import）
- `tokens/` — colors / typography / spacing / texture / base
- `fonts/fonts.css` — 得意黑（cn-fontsource CDN）+ Inter/Noto Sans SC/IBM Plex Mono（Google Fonts）
- `guidelines/` — 基础规范卡片（色彩、字体、间距、材质）
- `components/core/` — Button · Input · Tabs · Dialog
- `components/data/` — DataTable · ChannelValue · CitationMark
- `components/status/` — StatusMark（八态）· VoidBlock · SealedBlock · ChartPlaceholder · EmptyState · DegradedNotice
- `components/surfaces/` — PaperSurface · StickerTag
- `ui_kits/marketing/` — 营销首屏（满浓度）
- `ui_kits/app/` — 功能屏：线索 → 报告（低浓度）
- `SKILL.md` — Agent Skill 入口

### Intentional additions
无。组件清单 = DESIGN.md §8 点名的识别物 + 其点名的常规原子件（按钮、输入、标签、表格、卡片、浮层、Tab）。

### 字体替代说明
得意黑通过 cn-fontsource 切片 CDN 加载（家族名 `Smiley Sans Oblique`）。若需自托管，请提供 woff2 文件替换 `fonts/fonts.css`。
