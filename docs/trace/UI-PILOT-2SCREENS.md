# UI-PILOT-2SCREENS trace — 前端视觉语言试点（2 屏定调）@2026-08-01

## 0 本轮范围

为后续 18 屏定调，只做 2 屏：**A 首页**（glow 语言全额表达）+ **B 报告 L0
`/deliverables/[id]`**（数据最密、诚实态最多，定「实用暗色」基准）。
工程骨架沿用 `V0 files 前端设计/`（Next 16 App Router + Tailwind v4 + lucide），
未换构建系统；`web/` 一个字未动；零联网装包；零付费。

## 1 装载清单

- 验收清单：`Claude design Flint 前端设计/.../design_handoff_flint_web/04_技术约束清单.md`（32 条全文）
- IA 立意：`Claude design Flint 前端设计/Flint 燧石首屏设计/Flint 首屏.dc.html`
  （「判定卡当主角——承认不知道，是这个产品最贵的表达」；纸感视觉未取）
- 数据层（直接复用，未另抄契约镜像）：`V0 files 前端设计/lib/types.ts`、`lib/api/*`
- 改造对象现状：`app/globals.css`、`app/page.tsx`、`app/deliverables/[id]/page.tsx`、
  `app/layout.tsx`、`components/report/*`、`components/honesty/*`、`components/primitives/*`、`package.json`
- 真实数据源：`harness/gate1_live.py replay-qwen`（录制回放）、`harness/demo_seed_report.py`（夹具）

## 2 视觉分区落地（硬约束）

| | 首页 | 其余全部功能屏 |
|---|---|---|
| 底 | `#0A0A0B` | 页底 `#0A0A0B` / 卡面 `#1A1A1C` / 抬升 `#232326` |
| 圆角 | `40px`（`--radius-hero`） | `4~6px`（`--radius` 4 / `--radius-card` 6） |
| 边框 | 8px 渐变描边（`background-clip: padding-box, border-box` 双层） | 1px 实线 `rgba(255,255,255,0.10)` |
| 光晕 | `blur(45px)` | **零** |
| 入场 | 淡入 + 上移 30px，`--enter-delay` 错开 | 无 |

两套语言的机械隔离：glow 只由 `.glow-frame` / `.glow-halo` / `.glow-bloom` / `.glow-text`
四个工具类承载，且**只允许 `app/page.tsx` 引用**（约束写在 `app/globals.css` 文件头）。

**越界实测（非声明，是 grep + 抓真实渲染 HTML）**：
- 源码面：`grep -rn "glow-" app components`（排除 page.tsx 与 globals.css）→ **零命中**
- 渲染面：`curl :3001/deliverables/del-demo-fixture-report | grep -oE "glow-[a-z]+"` → **零命中**
- 渲染面：`curl :3001/ | grep -oE "(text|bg|border)-spark"` → **零命中**（首页无告警色）

## 3 取色：实算，非目测

对比度按 WCAG 2.1 相对亮度公式实算（底 base `#0A0A0B` / card `#1A1A1C` / raised `#232326`）：

| 前景 | base | card | raised | 用途 |
|---|---|---|---|---|
| `--ink` `#F2F4F7` | 17.96 | 15.77 | 14.22 | 标题 / 主值 |
| `--ink-2` `#9CA3AF` | 7.79 | **6.84** | 6.17 | 正文（owner 指定值，实算与其口径 6.8 吻合） |
| `--ink-3` `#8A929E` | 6.30 | 5.53 | **4.99** | 元信息 |
| `--spark` `#FF6B4A` | 7.02 | **6.17** | 5.56 | 告警（owner 口径 6.1，吻合） |
| 对照 `#6B7280` | 4.09 | **3.59** | 3.24 | **未采用**：不达正文标准 |
| 对照 rust `#B4472C` | 3.65 | **3.21** | 2.89 | **未采用**：为纸感浅底所调 |

- **`--ink-3` 取 `#8A929E` 而非 `#6B7280`**：11px 元信息在本项目属正文级（沿用原浅色主题
  `globals.css` 既有口径）。`#6B7280` 在最亮的抬升层只有 3.24，**三阶均不过 AA**。
  `#8A929E` 在最亮底上仍有 4.99，是唯一三阶全过的候选，且仍明显低于 `--ink-2` 不塌层次。
- **`--spark` 由 `#B4472C` 提亮到 `#FF6B4A`**：原值在暗底 3.21 不达正文标准，NEVER 原值照搬。
- **源色**四色对 card 均 ≥6.13，仅作 2px 方形类别印记，不表强弱。

**glow 品牌渐变刻意取冷色**（`#6E8BFF` → `#A855F7` → `#22D3EE`）：与告警暖色最大分离，
使 `--spark` 的告警语义不被品牌色稀释。首屏无告警态，两者永不同屏。**这是我的判断，见 §9-①。**

## 4 屏 A · 首页（`app/page.tsx` 全文重写）

- **立意照 Claude 包 IA**：hero 让一张写着「暂无法判定」的**真实判定卡**当主角。
- **卡上每个值都是真的**：取自 `harness/gate1_live.py replay-qwen` 真跑的引擎产出
  （录制回放，零联网、零付费），落库为 `snap-job-gate1-live-qwen-verdict`，我逐字段读出：
  `verdict=D_insufficient` / `gaps` 4 条（原文上屏）/ `competitors` 2 个均 `strength=unknown`
  （LightRAG、graphrag）/ `key_citation_ids=[]` / `rationale_fact_ids=[]`。
  屏上标注出处与「非实时」，NEVER 冒充实时数据。
- **`by_source` / hotness 读数**沿用原屏，逐字取自说明书 §2.1 样例响应并标注出处。
- 入场错开：`enter(i)` 把序号换算成 `--enter-delay`（90ms 步长），纯 CSS 零动效库。

**修掉一处既存违规（技术约束清单第 5 条）**：改造前的首页把 `--spark` 用于**品牌装饰**——
燧石被敲击的亮棱（`stroke="var(--spark)"`）与八道迸溅火星（`bg-spark`），且原文末尾自述
「强调色 spark 仅用于品牌隐喻的被敲击亮棱」。这正是清单第 5 条点名的「挪用即废掉阻塞标」。
现已全部移除，品牌表达改由冷色 glow 渐变承载，首屏 spark 类零出现（§2 渲染面实测）。

**顺带更正三个现状标签**（据实，非美化）：13 步旅程里 step 07（Gate 判定）、09（报告 L0）、
12（导出）原标「已建·未挂载」，实测已随 v0 会话挂载 `deliverables` app 且三屏已建，改标
「已建·已挂载」；step 01 原注「/plaza 路由未建」在本工程已不成立，注释删除。
step 08（report 提交）、10（干预）仍为「未挂载」——`compose`/`interventions` app 确未挂。

## 5 屏 B · 报告 L0（`app/deliverables/[id]/page.tsx`）

- **暗色化主战场在 token 一处**：既有组件全部走语义 token（`bg-card` / `border-rule` /
  `text-ink-2` / `text-spark`），故 `globals.css` 翻转即整屏改观，**功能语义一行未动**。
- 页头元信息改为抬升层（`#232326`）数据条，四字段等宽 + `tabular-nums`。
- 圆角 `2px → 4px`（owner 口径 4~6px），只改**报告路径 11 个文件**；
  gate / plaza / styleguide 不在本轮范围，未动（见 §9-④）。
- 页脚「字段清单」收进卡面，仍逐条指回真端点。
- **新增加载态** `app/deliverables/[id]/loading.tsx`（技术约束清单第 6 条：三态齐全）。
  明说「正在读」，NEVER 预渲染正文 / 版本号 / 复核结论；骨架条 `aria-hidden` 不承载语义。

## 6 技术约束清单逐条自检（只跑与这 2 屏相关的条目）

### A 全批通用

| # | 条目 | 结果 | 证据 |
|---|---|---|---|
| 1 | 有没有凭空造数 | ✅ | 全屏无进度条 / 百分比 / 星级 / 雷达；grep `进度条\|百分比\|星级\|雷达` 命中的 2 处均为「声明其不存在」的注释。判定档位直取后端值 |
| 2 | 有没有造端点或造字段 | ✅ | 首页 hero 逐字段读自 `snap-job-gate1-live-qwen-verdict`；报告屏字段全部来自 `lib/types.ts`（监管已比对冻结件）。未发明字段 |
| 3 | 未建接口有没有含糊过去 | ✅ | `citation_id` 只显 id；`chart_id` 占位 + `derived_from` 明写「接口未建」（`chart-placeholder.tsx:12-13`）；`card_ref` 明写 NEVER 前端代算覆盖率/对齐率（`block-renderer.tsx`）；`hints_ref` 物理切口 + id（`gap-notice.tsx:11`） |
| 4 | 状态标记有非颜色载体吗 | ✅ | 出处槽六类印记各有**图形**（Eye 复核 / GitBranch 争议 / CircleDashed 推测 / Lock 保护 / Scissors 缺口 / 实心方块 阻断）+ 中文词；unknown 竞品用**虚线中空**；三通道用**字形** F / ¥ / P。灰度下可分辨 |
| 5 | `--rust`(spark) 有没有被挪用 | ✅ **本轮修复** | 改造前首页用 spark 画品牌亮棱与火星（违规）；现首页 spark 类**零出现**（渲染面实测）。spark 现仅存于 blocking 印记 / 409 / 其余错误告警 |
| 6 | 空态 / 错误态 / 加载态齐了吗 | ✅ **本轮补齐** | 报告屏：空（`blocks: []` 真实空态）/ 错误（`ApiErrorNotice`，5xx 与不可达两种屏）/ 未生成（404 专屏）/ **加载（本轮新增 `loading.tsx`）**。首页为静态无 API 屏，三态不适用 |
| 7 | 无专属端点的屏标注了吗 | ✅ | 首页为介绍屏、无 API，屏底「本屏元素 → 后端字段对照」逐条写明每个数字的出处与「非实时」 |

### D 批次三（交付物）—— 报告 L0 相关

| # | 条目 | 结果 | 证据 |
|---|---|---|---|
| 20 | 保护块是「不存在」还是「置灰」 | ✅ | `protected-block.tsx:31-34` 保护成立时 `controls` 分支**根本不进入渲染树**；脚本断言「保护块不渲染『编辑』按钮」通过；实测 3 / 9 块受保护 |
| 21 | 两级复核标分得开吗 | ✅ | advisory → `<details>` 可折叠 + 「可折叠（不挡导出）」+ Eye 印记；blocking → 实心方块印记 + 「阻断」+ 块级描边 + 真挡导出（后端 409）。形状 / 文字 / 是否阻断三重区分 |
| 22 | 三通道混了吗 | ✅ | `channel-value.tsx` 三通道靠字形 F / ¥ / P 区分、**同为墨色不靠颜色**；三者各自独立组件互不混用；值一律 `.tabular`（等宽 + `tabular-nums`） |
| 23 | `quantity` 算了吗 | ✅ | `channel-value.tsx:40` 原样 `× {quantity}`，无任何乘算 |
| 24 | 图表零计算吗 | ✅ | `chart-placeholder.tsx` 零数据点、不 import 任何图表库，只显 `chart_id` + `derived_from` 出处 |
| 25 | 缺口被填了吗 | ✅ | `gap-notice.tsx` 保持 `.gap-cut` 物理切口 + 「缺口如实呈现，未以占位数据填充」，无生成文字 |
| 26 | 乐观锁 409 走确认流了吗 | — | **不适用本轮**：`LEDGER_CONFLICT` 属干预层（L2），报告 L0 只读，本轮未做干预 |
| 27 | evidence 结果自判了吗 | — | **不适用本轮**：补证据属干预层 |
| 28 | 503 装死了吗 | ✅ | `fmt=pdf` / `fmt=pack` 真打后端得 503（实测），前端显克制中性降级条「该格式的渲染依赖暂不可用……报告内容不受影响」，无转圈、无伪装下载 |

**能不能导出由后端说了算** ✅：`report-shell.tsx` 四个格式全部真打 `/render?fmt=`，
409 / 503 / 200 / 其余各走各的分支，`blocking_block_ids` 取自后端 `detail`，
前端 NEVER 预判、NEVER 提前灰掉按钮。实测 markdown → **409**、pdf → **503**。

（B 批次一 / C 批次二条目属广场与 Gate 屏，不在本轮 2 屏范围，未自检。）

## 7 验证（真实数字，全部我亲手跑）

| 项 | 命令 | 结果 |
|---|---|---|
| 类型门 | `npx tsc --noEmit` | **exit 0**（加 loading.tsx 后复跑仍 0） |
| 后端诚实态 | `node scripts/check-connectivity.mjs` | **94 / 94，失败 0，exit 0** |
| 前端渲染诚实态 | `node scripts/check-screens.mjs` | **51 / 51，失败 0，exit 0** |
| 坏链路 · 5xx | `node scripts/check-degraded.mjs 500` | **15 / 15，失败 0，exit 0** |
| 坏链路 · 不可达 | `node scripts/check-degraded.mjs down` | **18 / 18，失败 0，exit 0** |
| `web/` 未受影响 | `cd web; npm test -- --run` | **11 文件 / 63 测全绿** |
| 后端真状态 | curl `/render?fmt=` | markdown **409** · pdf **503** · blocks **200** |

四支脚本合计 **178 项断言全绿**。其中 `check-screens` 覆盖了报告屏的全部诚实态断言
（8 支 content 全渲染 / 保护块不渲染编辑按钮 / 争议原文保留 / blocking `bf-04` / 缺口 /
未生成不退回 mock），**说明本轮视觉改造未破坏任何功能正确性**。

编译产物复核（抓 `:3001` 真实 CSS）：`--stone-50:#0a0a0b`、`--surface:#1a1a1c`、
`--stone-100:#232326`、`--rule:#ffffff1a`(=0.10)、`--spark:#ff6b4a`、`--radius-hero:40px`、
`background-clip` 3 处、`blur(45px)`、`translateY(30px)` 均在场。

## 8 我验证的 / 我没验证的

**已验证**：§7 全部数字；§2 越界检查（源码面 + 渲染面双查）；§3 对比度（实算）；
hero 判定卡每个字段（读真库快照）；报告屏后端 409/503/200 真状态；`web/` 63 测未受影响。

**未验证（不背书）**：
- **屏幕实际观感未看**——我没有截图能力，没有用眼睛看过这两屏长什么样。
  我能证明的是「token 值正确、类被正确渲染、CSS 机制在场、断言全绿」，
  **不能证明「好看」**。观感是否达标须 owner 亲自打开 `:3001/` 与
  `:3001/deliverables/del-demo-fixture-report` 判断。
- 移动端断点（`md:` 以下）未实测。
- `next build` 生产构建未跑（只跑了 dev + tsc）。
- 明暗对比在真实显示器 / 不同色域下的表现未测。
- 减少动效（`prefers-reduced-motion`）分支代码已写（`.enter` 显式复位），**未实机验证**。

## 9 给 owner 的判断点（我不代拍）

1. **glow 渐变取冷色**（靛 `#6E8BFF` → 紫 `#A855F7` → 青 `#22D3EE`）。理由：与告警暖色
   `#FF6B4A` 最大分离，避免品牌色稀释 spark 的告警语义。代价：燧石「击打火星」的暖色隐喻
   被让掉了。若你要暖色品牌调，我改，但那时须另想办法保住 spark 的唯一性。
2. **hero 用真实判定卡（D_insufficient）当主角**——取自 Claude 包立意。它把「我不知道」放在
   首屏最大位置。若你认为对外首屏应先展示能力而非诚实边界，这一屏要重排。
3. **另有 5 个同族垃圾依赖**：`three`、`expo`、`expo-asset`、`expo-file-system`、`expo-gl`
   （前者是 `@react-three/fiber` 的配套包，后四者是 `react-native` 的）。你只点名删两个，
   我**只删了两个**，其余登记待你裁。
4. **本轮只改了报告路径的圆角**：gate / plaza / styleguide 三屏未在范围内，它们已自动继承
   暗色 token，但圆角仍是 2px、且未按新语言排版——**现在它们处于「暗了但没定调」的中间态**，
   下一轮铺 18 屏时补齐。
5. **依赖删除后未跑 install**：`package.json` 与 lockfile 暂不同步（零联网红线，未自行装包）。
   下次有联网许可时跑一次 `pnpm install` 即可对齐；不跑也不影响当前 dev / build。

## 10 落盘清单

| 文件 | 改动 |
|---|---|
| `V0 files 前端设计/app/globals.css` | **重写**：暗色三阶 token + 告警色提亮 + glow 四工具类 + 入场动效 + reduced-motion 复位 |
| `V0 files 前端设计/app/page.tsx` | **重写**：glow 首屏 + 真实判定卡 hero + 移除 spark 挪用 + 三个状态标签更正 |
| `V0 files 前端设计/app/deliverables/[id]/page.tsx` | 页头元信息改抬升层数据条、页脚收进卡面、圆角 4px |
| `V0 files 前端设计/app/deliverables/[id]/loading.tsx` | **新增**：加载态（清单第 6 条） |
| `V0 files 前端设计/package.json` | 删 `react-native`、`@react-three/fiber` 两个无关依赖 |
| 报告路径 11 个文件 | `rounded-[2px]` → `rounded-[4px]`（`report-shell` 5 处 / `deliverables/page` 2 处 / 其余各 1 处） |

**未动**：`contracts/`、`flint/domain/`、任何后端端点响应形状、`web/`、`lib/types.ts`、
`lib/api/*`、三份 v0 文档的任何结论、gate / plaza / styleguide 三屏。
