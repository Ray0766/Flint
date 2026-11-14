# CHAIN-UI-01-a · 屏上补齐 ②→③ 不依赖冻结件修订的那一半

**状态**：verified @2026-11-14。第 17 批第五张拆出来的前一半。

## 一、拆分记录（S5）

`CHAIN-UI-01` 卡面六件事：分析完成 → 「生成报告」（带 `analysis_job_id`）→ 作业页 →
产物从总览列表里找到；缺口块显示内容；受众版互链。

后两件要 `DEC-064` 的三个新字段（`GapNoticeContent.missing_what` / `why`、
`Deliverable.sibling_deliverable_id`），而 `CONTRACT-REV-01` 在停着（`docs/v0.4-问题单.md` 末节）。
前四件只用 `DEC-061`（`REPORT-SRC-01`）与 `DEC-063`（`OVERVIEW-01`）已经落地的东西。

| 卡 | 范围 | 状态 |
|---|---|---|
| `CHAIN-UI-01-a` | 前四件 | 本卡 |
| `CHAIN-UI-01-b` | 缺口块显示内容、受众版互链 | 未开工，随 `CONTRACT-REV-01` |

verify_cmd 两半共用卡面那一条：`cd web && npx vitest run __tests__/app/chain_ui.test.tsx`。

## 二、装载清单

`web/app/projects/[id]/page.tsx` · `web/components/project-overview/ProjectOverview.tsx` ·
`web/lib/screenAdapters.ts:60-100` · `web/components/chain/chainClient.ts` ·
`web/app/projects/[id]/analysis/page.tsx`（提交后进作业屏的既有写法）· `web/app/jobs/[id]/page.tsx` ·
`web/lib/jobClient.ts:29-175` · `web/__tests__/app/ui11.test.tsx`、`nav03.test.tsx`（既有搭法）·
`flint/api/compose.py:128-180` · `flint/api/project_overview.py`。

## 三、改前实况

- 屏上没有一处会带着分析作业号去成文。`web/app/workbench/page.tsx:118-123` 的注释还写着「今天走不了」；
- **项目总览里作业的状态槽在真数据上恒为空**：适配器读的是 `row.status`，而后端三份清单里
  没有一份带这个键（作业的状态在 `state`）。既有判据喂的是手写的视图对象，量不到这一层；
- 交付物清单只印 id 两遍（标题取不到就退回 id），不显示版本，点不进去；
- `.overview__*` 这一族在 `globals.css` 里一条样式都没有，屏上是 `job-…proposal失败` 连成一串。

## 四、改动

| 位置 | 改了什么 |
|---|---|
| `web/lib/screenAdapters.ts` | 作业状态读 `state`（`status` 留作后备）；多带 `kind` / `version` / `supersedes`，都是后端原值 |
| `web/components/chain/chainClient.ts` | 新增 `submitReport`：体里只有 `analysis_job_id` |
| `web/components/project-overview/ProjectOverview.tsx` | 跑完的分析旁画「生成报告」；交付物 id 变成链接，显示版本与「取代哪一份」；提交结果一行 |
| `web/app/projects/[id]/page.tsx` | 持有提交状态；成功后进 `/jobs/{id}?project={项目号}` |
| `web/app/jobs/[id]/page.tsx` | 跑完且地址栏带了项目号 → 「回项目总览找这次的产物」 |
| `web/messages/zh.json`、`en.json` | 6 个新键，两边对称 |
| `web/app/globals.css` | `.overview__*` 五条排版规则（只用既有 token） |

## 五、决定（含自己定的装饰性决定）

1. **「生成报告」只在 `gate1_analysis` 且 `done` 的作业旁出现**。这是前端按后端给的两格决定画不画一个键，
   不是判定：服务端照样逐条核，被拒时那句话原样上屏。
2. **请求体不带 `template_id`**。不带时服务端用自己的默认；前端填一个就多出一处要跟着改的默认值。
3. **项目号走地址栏 `?project=`**。作业快照（`GET /jobs/{id}`）不回项目号；作业屏要回总览只能靠带过去。
   没带就不画那个入口——给一个猜出来的链接，点过去是别人的项目或 404。
4. **NEVER 由作业号拼产物 id**。`del-{作业号}` 今天成立，但那是实现细节（`DEC-012`）。产物从总览清单里找。
5. 装饰性：按钮文案「生成报告」、入口文案「回项目总览找这次的产物」、版本写成「第 N 版」、
   「取代 {id}」；按钮复用 `.chain-form__submit`；行样式照数据行那一套 token。这几样是我定的。

## 六、判据先行

`web/__tests__/app/chain_ui.test.tsx`（12 条）先写，实现前 `8 failed | 4 passed`，实现后 12 passed。
已经绿的 4 条是「没给动作不画键」「没带项目号不给入口」「没跑完不给入口」这类否定面，改前自然成立。

## 七、连带触发的 11 条 Python 侧守门

第一遍全量 `pytest`：`11 failed`。逐条处理，没有一条是靠放宽判据过的：

| 判据 | 为什么红 | 处置 |
|---|---|---|
| `test_reachability` ×2、`test_main_chain_walk` ×1 | 源码里多了 3 条导航边，屏图没声明 | `assets/screen_graph.json` 两个方向各补 3 条 |
| `test_reachability` 两条阴性对照（上一条修完才露出来） | 报告那一族、项目那一族各多了一条来路，「摘一条边就成孤岛」的前提过期 | 人造图里把新增的那条来路一并摘掉；量的能力没少（与 `NAV-05` 那次同一种改法） |
| `test_ui11::test_the_page_never_stitches_three_requests` | 它只认 `href=` 是导航，提交成功后的 `window.location.assign(` 被判成拼请求 | 判据补认这一种导航；页面把路径字面量与跳转写在同一行。`fetch(` 那句没动 |
| `test_analysis_entry_screens` | 钉着写端点恰好 2 条 | 改成 3 条并点名第三条是 `/report` |
| `test_gauge_map_b2` ×2 | 多了一个前端测试文件，落盘清点过期 | 重算 `assets/gauge_map_b2.json`（保持 CRLF） |
| `test_i18n_keys_defined` ×4 | **`tools/i18n_key_defined.mjs` 的 `--json` 输出在 65536 字节处被截断** | 见下 |

**那个截断是一个 macOS 上的真缺陷**：脚本末行是 `process.exit(main(...))`，`process.exit()` 不等 stdout 排空。
stdout 接管道时（pytest 的 `capture_output`），macOS 的管道缓冲是 64KB，超出的那一截直接丢掉。
报告原本 65K 出头，加了 6 个键涨到 66583 字节，正好越线，读的人拿到半截 JSON。
改成 `process.exitCode = main(...)`。同样写法的还有四个脚本没有动（输出还远小于 64KB）：
`tools/check_screen_composition.mjs`、`check_design_constraints.mjs`、`check_vitest_filters.mjs`、
`no_scaffold_on_screen.mjs`。

## 八、验证

五条门，最终树单跑：`tsc --noEmit` 无输出 · `vitest` 86 文件 870 条 · `ruff` All checks passed ·
`mypy --strict flint eval harness` 371 文件零条 · `pytest` `5426 passed, 422 skipped`。

**真浏览器**（应用内浏览器，演示栈重起后的新代码）：

- 往演示库放了一条 `done` 的 `gate1_analysis` 作业（`chainui-probe-analysis`，挂在 `proj-demo-fixture`）；
- 1920×1080：总览七条作业里只有这一条旁边有「生成报告」；作业状态显示出来了（改前是空的）；
  交付物行是链接、显示「第 1 版」；无横向溢出；
- 点「生成报告」：`POST /projects/proj-demo-fixture/report → 200`，跳到
  `/jobs/job-28c5ced4-…?project=proj-demo-fixture`，屏上状态 `drafting`、5 条步骤；
- 390×844：`scrollWidth == 390`，没有元素越出视口；
- **没看到的那一段**：作业跑完后的「回项目总览」入口。本机没接模型，那条成文作业在 `draft` 这一步
  `LocalProviderUnavailable` 失败了。这一段只有 vitest 的证据。

验证完把探针作业、那条成文作业、它的事件与步骤、以及它 `freeze` 那一步在演示项目上多出来的
一个账本版本（2 条 fact）都删了，演示库回到验证前的样子。

## 九、顺带看到、登记的

1. **失败的作业屏上一直转**：上面那条成文作业库里已是 `failed`，而作业屏停在 `drafting`、
   没有失败提示。`mark_failed` 只改库不写事件（`docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md`
   里最要紧的那一处），这次是在屏上亲眼见到。
2. `WorkbenchAnnotate` 仍停在「已提交」。`REGEN-EVT-01` 与 `OVERVIEW-01` 之后它可以订阅作业并去总览找新版本，
   但那一屏的绕行被 `tests/v041/test_wb_annotate.py` 的五条判据钉着，取证还要 playwright 与模型，没有动。
3. 总览里作业的标签是 kind 原值（`gate1_analysis`、`proposal`），交付物的标签退回成 id（印了两遍）。
   这两处是既有行为，属 `BACKEND-PROSE-EMBEDS-RAW-ENUM` 那一类，没有在本卡改。
