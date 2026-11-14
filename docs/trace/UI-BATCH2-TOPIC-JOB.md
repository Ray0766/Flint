# UI-BATCH2-TOPIC-JOB trace — 主题层与作业层 5 屏（P4/P5/P6/P7/P8）@2026-08-02

> 这是 owner 三批交付的**第一批**（屏号沿用设计包的 P 编号）。
> 后两批（P10/P13 干预与导出、P11/P12/P14/R1~R4）另行交付，各自跑门、各自写台账。

## 0 本轮范围与真数据

5 屏：P4 主题列表 `/projects/[id]/topics` · P5 主题详情 `/topics/[id]` ·
P6 发起分析 `/projects/[id]/analysis/new` · P7 Job 进度（SSE）· P8 Gate 判定（后两者同路由 `/gate/[jobId]`，
**由后端当时的 state 决定看到哪一屏**，前端不预判）。

`web/` 一字未动；`contracts/` 与 `flint/domain/` 未动；**后端端点响应形状未动**；零联网装包；零付费。

**真数据（本轮我自己跑出来的，非臆测）**：
- `harness.gate1_live replay-qwen` → `job-gate1-live-qwen`：`D_insufficient` + 4 缺口 + 2 个 `unknown` 竞品
- `harness.demo_seed_report` → 报告夹具（本批不直接用，为保持库完整而重灌）
- **`POST /projects/combo` 真跑一次**（免费本地 qwen，26.3s）→ `proj-demo31290ca905` + **5 个真主题**
  （库里 projects/topics 此前是 0，被清空过）

## 1 逐条自检（04 技术约束清单 C 组 13~19）

| # | 条目 | 结果 | 证据 |
|---|---|---|---|
| 13 | `speculative==true` 降权且**抑制溯源入口** | ✅ 已建 · ⚠️ **无真数据未实屏验证** | `components/topic/why-now.tsx`：推测态走虚线边 + `CircleDashed` + 次级墨色（降权），并**不把 `citation_id` 渲染成引用位**，改写「未经证据对齐，因此此处不提供溯源入口」。非推测态才把 `citation_id` 作为引用位呈现。**本轮 5 个真主题 `speculative` 全为 false**，该分支代码在场但未被真实数据触发 |
| 14 | 进度按真实 `state/step_name/phase`，NEVER 编百分比 | ✅ | `gate-live.tsx` 只渲染后端 `state` / `progress` / `budget` / `cost_accum` / `updated_at`，事件行直接 `describe(payload)` 输出 `step_name · phase`；**全屏无百分比、无进度条**（断言 `P7 不画百分比` + `P8 判定屏不出现百分比进度`） |
| 15 | `state=="failed"` 显示 `error/reason` 原文 | ✅ **已实屏验证** | `page.tsx#FailedView` 直出 `job.error`；`error` 为 null 时明写「后端未记录失败原因，此处不代为解释」。断言用真 job `m4029-dagfail` 比对后端 error 原文前 24 字 |
| 16 | SSE：快照 → `Last-Event-ID` 续订 → `seq` 去重 → 终态 close | ✅ **本轮加强** | 快照由服务端 `GET /jobs/{id}` 取好传入（`page.tsx`）；续订依赖原生 `EventSource`（自动带 `Last-Event-ID`）；`seq <= 已见最大值` 幂等忽略；终态 `es.close()` + `router.refresh()`。**本轮新增把三阶段做成可见**（`snapshot / resubscribe / restored`）并显示已去重条数——原先这三件事只在注释里 |
| 17 | verdict 直取；`constraints_checked` 按**对象**处理；瘦快照标「未记录」 | ✅ **已实屏验证** | `ConstraintsDetail` 逐字段摊开 `order / demoted_by_alignment / rule_a / rule_b / rule_c / gap_count`，**未当 boolean**；`cc === undefined`（瘦快照）→「constraints_checked 未记录 … 不反推、不补默认值」。断言比对后端真 `gap_count` |
| 18 | `missing_permission` 走「请 owner 授权」，`missing_data` 走「补充资料」 | ✅ 两组件分开 · ⚠️ **permission 分支无真数据** | `MissingDataGap`（实线卡 + action 图标 + `suggested_sources`）与 `MissingPermissionGap`（虚线卡 + `Lock` + `required_scope` +「请 owner 授权后重跑判定」+「这是权限缺口，不是数据缺口」）是两个独立组件、形态不同。**本轮真数据 4 条缺口全是 `missing_data`**，permission 分支未被真实数据触发 |
| 19 | `unknown` 与 `weak` **不同形**并标「未知」 | ✅ **已实屏验证** | `unknown` → **虚线中空** + `HelpCircle` + 文字「strength · 未知」；非 unknown → 实线边 + `strength · {值}`。真数据 LightRAG / graphrag 两个 unknown 竞品已在屏上看过 |

## 2 各屏要点

- **P4**：`chosen_topic_id` 直取后端；为 `null` 时如实写「null（尚未选主题）」且**不挑一个当选中**（断言 `unseen` 选中徽记）。
  未知 project 后端回**空数组而非 404** → 走空态，断言 HTTP 200。
- **P5**：未知 topic 后端 **404**（单资源语义，与 P4 的空数组不同）→ 走 404 屏，断言状态码。
  `keyword_mapping` 逐组摊开；`citation_id` 只显引用位并写明「解引用端点未提供」（清单 A-3）。
- **P6**：主题**强制单选、无默认**——只有用户从某主题点进来（URL 带 `topic_id`）才预选，那是用户的显式意图；
  后端 `chosen_topic_id` 只作「项目里已选」标注，**NEVER 自动当成本次分析的选择**。
  `budget_cny` 契约必填，如实要用户给，且**不显示任何「预计花费」**（后端没有预估值，断言 `unseen`）。
  `Idempotency-Key` 显示出来，让「重复点不会造第二个 job」可见。
- **P7/P8**：同一路由，分派由后端 state 决定；四种出口（判定 / 进行中 SSE / failed / 终态无快照）互不掩盖。

## 3 本轮真实修掉的两个缺陷（都是我自己引入的，探针抓住）

### 3.1 P6 hydration mismatch

**症状**：探针控制台断言报 `Hydration failed because the server rendered text didn't match the client`，
4 次（light/dark × desktop/mobile 各一）。

**根因**：我把幂等键写成 `useMemo(() => \`p6-${projectId}-${Math.random()...}\`)`。
`useMemo` 在 SSR 阶段也会执行 → 服务端与客户端各生成一个不同的随机串，且该串被渲染进 DOM → 必然不匹配。

**修法**：改为 `useState(null)` + `useEffect` 在客户端挂载后生成；未生成前提交按钮不可用，
文案显示「（客户端挂载后生成）」。修后探针 12/12 零控制台错误。

### 3.2 `loading.tsx` 让 `notFound()` 失去 404 状态码

**症状**：我给 `/gate/[jobId]` 加了 `loading.tsx`（为满足清单 A-6 三态齐全），
结果既有断言「未知 job → HTTP 404」变成 **200**。

**根因（已实验证实，非猜）**：`loading.tsx` 会给该路由开启流式渲染，
HTTP 状态在流开始时就已提交为 200；之后 `notFound()` 虽然仍渲染 not-found 界面，
**却已无法把状态码改成 404**。移走 `loading.tsx` 后立即恢复 404（我做了移走→复测→删除的对照）。

**取舍与决定**：**要 404，不要骨架屏。**
未知资源必须回 404 是硬正确性（且有既有断言把守）；加载骨架是体验项。
让一个不存在的 job 回 200 + 一张「没有这个 job」的页面，正是「看起来对、量起来错」——
状态码是给机器看的，机器会被骗。
故 `/gate/[jobId]` **不设 `loading.tsx`**，并把这条权衡写在此处。
**副作用如实记**：该路由因此**没有加载骨架**，清单 A-6 的「加载态」在本路由以 SSR 直出替代
（服务端取完数据才出首字节）——这是有意的取舍，不是遗漏。

## 4 验证（真实数字，全部本人跑）

| 项 | 结果 |
|---|---|
| `npx tsc --noEmit` | **exit 0** |
| `node scripts/check-screens.mjs` | **99 / 99，失败 0，exit 0**（由 71 增至 99，本批新增 **28** 条断言） |
| `node scripts/check-connectivity.mjs` | **94 / 94，失败 0，exit 0** |
| `scripts/check_contrast.py` | 两主题 × 22 对达标 + 硫磺圈地 0 违规，**exit 0** |
| `ui_probe`（P4/P5/P6 与 P7/P8 各 2 主题 × 桌面/移动） | **两轮各 12 张，问题计数 0** |
| `ruff check .` | All checks passed |
| `mypy --strict flint` | 224 文件净 |
| `cd web; npm test -- --run` | **11 文件 / 63 测全绿**（一字未动） |
| `pytest -q` | **见文末实跑尾行** |

## 5 我真看过的 / 没验证的

**真看过（逐张 Read）**：
- P4 日间桌面（5 个真主题、`chosen_topic_id · null（尚未选主题）· 无推测态主题`、
  每条 `why_now` 的 claim 与 evidences、`citation_id` 带「解引用端点未提供」）
- P6 夜间桌面（5 个 radio **全未选中**、`budget_cny` 输入、`Idempotency-Key`、
  「请先选一个主题」、提交按钮置灰）
- P8 日间桌面（`D_insufficient`、4 条缺口各带 action 图标与 `suggested_sources`、
  2 个 unknown 竞品的**虚线中空**徽记、`constraints_checked (gap_count 4)` 可展开）

**没验证 / 无真数据（不背书）**：
- **`speculative == true` 的主题屏没见过**：本轮 combo 真跑出的 5 个主题该位全是 `false`。
  降权与抑制溯源的分支**代码在场、断言写了「无真数据」的如实记录**，但**未被真实数据触发过**。
- **`missing_permission` 缺口屏没见过**：真数据 4 条缺口全是 `missing_data`。同上处置。
- **`A_infeasible` / `strong` / `weak` 竞品没见过**：库里没有这些样本（owner 已实测告知）。
  四档与各强度的分支按契约写全且不 crash，但只有 `D_insufficient` 与 `unknown` 被真实数据走过。
- **P5 与 P7 的图我没逐张看**：只看了上面列出的 3 张；P5/P7 我有探针的「0 溢出 + 0 控制台错误」量测与断言，
  **但没用眼睛逐张确认版式**。
- **SSE 的断线→续订→恢复三阶段没实机触发过**：`m2005-job` 是 `retrieving` 态但后端此刻不再推事件，
  我**没有制造一次真实断线**来看 `resubscribe`/`restored` 文案。三阶段逻辑与去重计数是代码在场、未实证。
- **P6 的提交没真点过**：会造出真 job 并跑 Gate①（分钟级），本轮未点。
  提交后的跳转与错误屏**未实屏验证**。
- `next build` 生产构建未跑；平板断点未测。

## 6 落盘清单

| 文件 | 改动 |
|---|---|
| `V0 files 前端设计/components/topic/why-now.tsx` | **新建**（清单 13 的承载件） |
| `V0 files 前端设计/app/projects/[id]/topics/page.tsx` | **新建**（P4） |
| `V0 files 前端设计/app/topics/[id]/page.tsx` | **新建**（P5） |
| `V0 files 前端设计/app/projects/[id]/analysis/new/page.tsx` | **新建**（P6 服务端） |
| `V0 files 前端设计/components/analysis/analysis-submit-form.tsx` | **新建**（P6 交互，含 hydration 修法） |
| `V0 files 前端设计/app/gate/[jobId]/page.tsx` | 并入 S0 外壳、圆角 2px→4px（P8） |
| `V0 files 前端设计/components/gate/gate-live.tsx` | 新增 SSE 三阶段可见 + 去重计数、圆角（P7） |
| `V0 files 前端设计/scripts/check-screens.mjs` | 新增本批 28 条断言 |

**未动**：`contracts/`、`flint/domain/`、后端端点响应形状、`web/`、`components/ui/**`、`lib/mock/**`、`flint/**`。
