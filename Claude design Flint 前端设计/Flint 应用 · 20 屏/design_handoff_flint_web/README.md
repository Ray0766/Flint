# Handoff: Flint 燧石 · 功能屏全集（四批 · 20 屏）→ web/

## Overview
Flint 把四热点源日更沉淀成 热点簇 → 证据卡 → combo 关联假设 → 候选主题 → Gate① 判定 → 报告 → 计划书（human / vibe_pack 分叉）→ 导出。本包是全部功能屏的定稿设计（应用外壳 + P1~P14 + R1~R4 + S1 通用件），供 Claude Code 落进 flint 仓库的 `web/`（Next.js App Router + Tailwind + shadcn/ui）。

## About the Design Files
本包内的 `.dc.html` 是 **HTML 设计参考**（可直接在浏览器打开的交互原型，含 mock 接线与三态），不是可直接搬运的生产代码。任务是**在仓库既有环境里按既有模式重建**这些设计：套到既有组件（`PlazaView` / `GateView` / `BlockView` / `BlockTree`）的数据契约上，保留其零计算注释与 `data-*` 断言属性（`data-verdict` / `data-speculative` / `data-protected` / `data-chart-id` / `data-render`），不为视觉重写数据层。

`_ds/flint-design-system-…/` 是设计系统运行时（tokens CSS + 组件 bundle），供参考取值；正式 token 来源以 `/design-sync` 拉入的 Design System 为准，落到 `globals.css` + `tailwind.config.ts`，组件内不写死数值。

注：原始规则书 `01_DESIGN.md` 不在本包内（未随附件提供），入库时由 owner 放置。

## Fidelity
**High-fidelity**。颜色、字阶、间距、记号形状、状态材质（便条纹 / 划线纹 / 网点 / 缝线 / 压痕）均为定稿，按 token 精确重建。mock 数据、"mock 样例"预设链接与 Tweaks 场景开关是原型演示件，不进生产。

## Files（打开即用，重要交互都可点出）
- `Flint 批次四 · 分叉与收尾.dc.html` — **全集（20 屏都在，以此为准）**；hash 路由模拟正式路由
- 批次一/二/三 — 各批交付时的快照，留档
- `04_技术约束清单.md` — 验收清单（PR 描述里逐条贴结果）
- 每个文件内置「对照表」屏（#/spec）：全站路由表 + 每屏元素 ↔ 后端字段；「S1 通用件」屏（#/system）：复用件 props 契约

## Screens / Routes（路由 ↔ 界面 ↔ 主端点）
| 路由 | 界面 | 主端点 |
|---|---|---|
| /plaza/hot | P1 热点广场 | GET /plaza/hot?day= · GET /categories |
| /clusters/[id] | P2 工作台 | GET /clusters/{id}/evidence-cards |
| /combo/new | P3 combo 入口 | POST /projects/combo |
| /projects/[id]/topics | P4 主题列表 | GET /projects/{id}/topics |
| /topics/[id] | P5 主题详情 | GET /topics/{id} |
| /projects/[id]/analysis/new | P6 发起分析 | POST /projects/{id}/analysis |
| /jobs/[id] | P7 Job 进度 | GET /jobs/{id} + SSE /jobs/{id}/events |
| /jobs/[id]/verdict | P8 Gate① 判定 | GET /jobs/{id}/verdict（仓库路由习惯亦可用 /gate/[jobId]） |
| /deliverables/[id] | P9 报告 L0（human 计划书复用） | GET /deliverables/{id}/blocks + /deliverables/{id} |
| /deliverables/[id]/edit | P10 可干预页 | blocks 读 + lock / regenerate / disputes / evidence |
| /deliverables/[id]/export | P13 导出面板 | GET /deliverables/{id}/render?fmt= |
| /projects/[id]/proposal/new | P11 受众分叉 | POST /projects/{id}/proposal |
| /deliverables/[id]/pack | P12 vibe_pack 查看器 | 内容端点未接（pack 装配仅离线） |
| /projects/[id] | P14 项目总览 | 无专属端点：topics + jobs + deliverables 组合 |
| /account · /billing · /deliverables/[id]/quality | R1 / R2 / R3 占位屏 | 端点未建，明示占位 |
| R4（非路由） | 陈旧/重核横幅位 | 端点未建，挂交付物各屏顶部 |

外壳（S0）：顶栏 wordmark（display 字体排「Flint 燧石」，无 logo）+ 导航 + 大类筛选（GET /categories）+ 用户位（X-User-Id: self 占位）。S1 通用件：LoadingSkeleton / EmptyState / ErrorState / NotFound404 / SseDisconnectNotice，props 契约见 #/system 屏。

## Interactions & Behavior（功能正确性，与视觉冲突时以此为准）
- **零计算**：plaza 按后端序渲染、无排序控件；by_source 四源独立等宽列不合成不堆叠；quantity 原样不乘算；chart 只渲染 ChartPlaceholder（零数据点、零图表库）。
- **状态字段直读** → StatusMark 八态映射（speculative / review / blocking / disputed / sealed / degraded / void / verified）；无可靠度分值 → 全站无进度条/百分比/星级/雷达图。
- **保护块**：`locked ∨ author=="user" ∨ user_modified` → 控件**不存在**（非置灰）；门控唯一真相 `availableBlockInterventions(block)`（保护块返回 `[]`）。lock 成功（204）后块即时转保护、控件移除。
- **SSE**：一切 `{job_id}` 转交 `openJobStream(jobId) → /jobs/{id}/events`；断线 → 先 GET /jobs/{id} 快照 → 带 Last-Event-ID 续订 → 按 seq 去重 → 终态自动 close()。P7 有可视化的断线重连演示。
- **乐观锁**：dispute / evidence 带 expected_version；409 LEDGER_CONFLICT → 取 detail.current_version 提示「账本已前进至版本 N，确认后重提」→ 二次带 confirmed_version；不静默重试、不丢输入。
- **导出门禁**：409 EXPORT_BLOCKED → detail.blocking_block_ids 高亮待处理块并挡导出；pdf/pack 503 →「该格式暂不可用」，不转圈不伪装下载。
- **受众分叉**：单选无默认；ai_executor 锁定 template_id=vibe_pack；混用 → 422 如实报。
- **未建接口留位**：citation_id / chart_id / card_ref / hints_ref / 三通道值解引用 → 取数位 + 浮层「接口未提供」，不用生成文字填。
- 色彩纪律：`--rust` 全站仅三处 —— 阻塞级复核标、409 EXPORT_BLOCKED、503。

## State Management
每屏三态（loading 骨架 / 空态 / 错误态）均已设计，空态≠错误（未知簇、未知 project 返回空数组非 404；未知 topic / deliverable / verdict 才是 404）。原型 Tweaks 场景开关对应 mock 分层需求：comboResponse、analysisResponse、jobOutcome、disputeResponse、evidenceResponse、interventionAuth、exportBlocking —— 落库时以 `NEXT_PUBLIC_FLINT_MOCK=1` 的 `lib/mock/*` 承接同一组样例（degraded / D_insufficient / unknown 竞品 / advisory+blocking / alignment=partial / 409 两种 / 503 / 422 / SSE failed）。

## Design Tokens（详见 _ds/tokens/*.css，落到 globals.css + tailwind.config.ts）
- 色：paper #EDEEE6 · paper-2 #E3E5DA · surface #F7F8F3 · ink #1B2A2E · ink-2 #5A6A6E · ink-3 #8B9799 · rule #D2D6C9 · indigo #2E4A7D · sulfur #E8B93C · rust #B4472C（仅三处）· moss #6B7A5A + 派生淡色（indigo-soft/mist、moss-soft、sulfur-soft、rust-soft）
- 字体：display「Smiley Sans Oblique」（仅页面级标题）· body Inter + Noto Sans SC · mono IBM Plex Mono + tabular-nums（一切带出处数值/id/时间戳）
- 字阶 12/13/14/16/20/25/31/48/72/112；间距 4/8/…/160（功能屏取下端）；圆角 2px 数据面 / 8px 卡片 / 999 标签纸
- 材质：--tex-paper（≤4% 噪点）· --tex-halftone（降级网点）· --tex-hatch（争议划线）· --tex-note（便条横线）· --tex-stitch（缝线）· --tex-press + --emboss（压痕）；阴影仅 --shadow-sticker / --shadow-overlay

## Assets
无位图/图标字体/emoji。全部识别物为组件内联几何记号 + mono 短标签；空态单线插画内置于 EmptyState 组件（spark / lens / page 三题材）。

## 已知缺陷提醒
`web/lib/viewsClient.ts` 将 verdict 的 `constraints_checked` 误标为 boolean —— 后端实为对象（order / demoted_by_alignment / rule_a / rule_b / rule_c / gap_count），挂 Gate 视图时修正（P8 已按对象渲染成可展开判定依据）。
