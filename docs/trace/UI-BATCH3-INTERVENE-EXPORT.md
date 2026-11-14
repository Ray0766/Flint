# UI-BATCH3-INTERVENE-EXPORT trace — 干预与导出（P10/P13）+ 挂 interventions @2026-08-02

> owner 三批交付的**第二批**。第三批（P11/P12/P14/R1~R4）另行交付。

## 0 范围

P10 可干预页 `/deliverables/[id]/edit` · P13 导出面板 `/deliverables/[id]/export`
+ 后端胶水挂 interventions（owner 裁决：interventions 挂、compose 不挂）。

`web/` 一字未动（63 测复跑全绿）；`contracts/` 与 `flint/domain/` 未动；
**后端端点响应形状未动**；零联网装包；零付费。

## 1 两个坑

### 坑一 · aligner 同步 LLM 憋事件循环 —— 已修 + 有非空转回归测试

**回源定位（非转述）**：`flint/intervene/inject.py:76` 原文
`alignment = aligner.align(claim_text, doc, stage="verdict")` ——
在 **async** 函数 `inject_evidence` 里**同步**调用。`CitationAligner.align` 是同步的
（冻结 `LLMProvider` 协议本就同步，`LocalProvider` 底层同步 httpx，一次判定可达数十秒），
故它会憋死整个事件循环——与 DEMO-NONBLOCK 修过的是同一 bug 类。

**修法**：`alignment = await run_in_threadpool(aligner.align, claim_text, doc, "verdict")`。
只挪调用位置，**未改任何端点响应形状**。

**回归测试**：`tests/harness/test_inject_nonblocking.py`（与 `test_demo_nonblocking.py` 同构）——
慢同步 aligner + 每 10ms 一拍的心跳，量事件循环单次最长停顿，阈值 0.25s。

**这个测试我自己空转过一次，已修**：初版 `create_task(heartbeat)` 之后直接
`await inject_evidence(...)`，而 `inject_evidence` 在触到阻塞调用前**没有任何 await**，
心跳的第一拍因此排在阻塞**之后**才执行、基线时间戳错过了整段阻塞 →
**有 bug 的代码照样通过**。加 `await asyncio.sleep(HEARTBEAT_INTERVAL*3)` 让心跳先真正跑起来后：

| 代码形态 | 实测最长停顿 | 结果 |
|---|---|---|
| 阻塞版（`aligner.align` 裸跑） | **0.616s** | **FAIL**（> 0.25s） |
| 修后（`run_in_threadpool`） | < 0.25s | PASS |

对照实验是我真做的：改回阻塞版 → 跑 → 看到 FAIL → 再改回修复版 → 跑 → PASS。

### 坑二 · report job 的判别派发 —— 按 payload 形状，分不出来显式失败

**事实**：`flint/api/interventions.py:170` 的 regenerate 提交 `kind="report"`，
payload 带 `action ∈ {regenerate_section, regenerate_block}` + `deliverable_id` / `section_id` / `project_id`；
而 compose 新建报告用的**也是** `kind="report"`。

**落法**（`harness/demo_server.py`）：
- `_is_regenerate_payload(payload)`：按上述形状判别。
  形似 regenerate（action 命中）但**缺字段** → **抛 `ValueError`**，拒绝派发。
- `_enqueue`：`kind == "report"` 时，判别为 regenerate → `_run_regenerate`；
  **判不出来 → 抛 `ValueError` 并写明「demo 未挂 compose 提交端点，故 report 只应来自 regenerate」**。
  **NEVER 静默吞掉、NEVER 误派**——compose 将来挂上时，静默误派会是极难查的 bug。
- `_run_regenerate` 把整个作业经 `run_in_threadpool` 挪出事件循环；
  **协程在线程内部创建**（`asyncio.run(run_regenerate_job(...))` 写在 `_blocking()` 里）——
  在主 loop 上先造好协程再丢进线程会绑错事件循环。

## 2 挂载 interventions

补齐 demo 缺的三件：`ledger_store=PgLedgerStore(dsn)`、
`scorer=DualScaleScorer(ScorerContext(today=…))`、
`aligner=LLMCitationAligner(LocalProvider(免费本地 qwen))`；
复用已有的 `runner` / `role_resolver` / `owner_scope_for_project`。

`UserProfile` 逐字照冻结件字段构造（identity/research/team/assets/constraints/
track_record/locale/sensitivity_overrides/updated_at 全给全空值）——demo 无真实档案，
**NEVER 编造涉我信息**。

**`flint.api.pack` 仍 NEVER 挂**（与 `deliverables` 撞 `GET /deliverables/{id}/render`）。
**挂 interventions 后实测 render 路由未受影响**：
`markdown/html/docx → 409`、`pack → 503`、`pdf → 503`。

## 3 逐条自检（04 清单 D 组 20/21/26/27/28）

| # | 条目 | 结果 | 证据 |
|---|---|---|---|
| 20 | 保护块**不渲染**任何控件（非置灰）；门控唯一真相；lock 204 后即时转保护 | ✅ **已实屏验证** | 门控唯一真相 `lib/interventions-gate.ts#availableBlockInterventions`（受保护 → 空数组，调用方据此**不渲染**控件区）。夹具 3/9 受保护：**bf-01(locked) / bf-08(author="user") / bf-09(user_modified) 屏上各零按钮**，只显「受保护 · 不提供编辑控件（控件未渲染，非置灰）」。断言逐块取该块 HTML 片段、正则确认无控件文案。lock 成功（204）后本地把 `locked` 置 true → 门控函数即时返回空数组 → 控件消失 |
| 21 | advisory 可折叠不阻断 / blocking 阻断并高亮 blocking_block_ids，一眼可辨 | ✅ **已实屏验证** | P10：blocking（bf-04）实心 spark 方块 +「阻断 · 挡导出」+ 卡片 spark 描边；advisory（bf-03）中空 Eye +「提示 · 不挡导出」。P13：块清单同样两分，409 命中块加 spark 底并可跳锚点 |
| 26 | 乐观锁：带 expected_version；409 取 detail.current_version 提示 → 带 confirmed_version 重提；不静默重试、不丢输入 | ✅ 已建 · ⚠️ **未实机触发 409** | `FlintApiError.currentVersion` 从 `detail.current_version` 取（后端未携带则 `null`，NEVER 猜一个数）。409 时进确认屏「账本已前进至版本 N，你的争议理由已保留」，两个出口：确认重提（带 `confirmed_version`）/ 先不提交（保留输入）。**首次提交 MUST 不带 confirmed_version**（带了等于绕过乐观锁）。造一次真实版本冲突需并发改账本，本轮未做 |
| 27 | evidence 只显后端回值；`alignment=="partial"` 标「部分支持、未成事实」 | ✅ 已建 · ⚠️ **未实机取到 partial** | 结果面逐字显 `alignment / fact_added / ledger_version / score_axis / attempts / optin`，并注「以上逐字取自后端响应，前端不自判对齐结果」。`partial` 时虚线卡 + 「部分支持、未成事实——契约上 partial 的 claim NEVER 被提升为 Fact」 |
| 28 | 503 显「该格式暂不可用」，不转圈不伪装下载 | ✅ **已实屏验证（后端真 503）** | pdf/pack 实测 503；屏上克制中性虚线卡 + `CircleSlash` +「该格式暂不可用…报告内容本身不受影响」 |

**「导出由后端说了算」**：五个格式按钮**一个都不预先禁用**，全部真打
`GET /deliverables/{id}/render?fmt=`，409/503/200/其它各走各的分支（断言
`P13 不预判 409`）。这是上一轮修掉的老毛病，本轮没有回退。

## 4 验证（真实数字，全部本人跑）

| 项 | 结果 |
|---|---|
| `pytest tests/harness/test_inject_nonblocking.py` | **PASS**；对照实验：阻塞版 **FAIL（0.616s > 0.25s）** |
| `npx tsc --noEmit` | **exit 0** |
| `node scripts/check-screens.mjs` | **118 / 118，失败 0，exit 0**（99 → 118，本批新增 **19** 条） |
| `node scripts/check-connectivity.mjs` | **94 / 94，exit 0** |
| `scripts/check_contrast.py` | 两主题 × 22 对 + 硫磺圈地 0 违规，**exit 0** |
| `ui_probe`（P10/P13 × 2 主题 × 桌面/移动） | **8 张，问题计数 0** |
| `ruff check .` | All checks passed |
| `mypy --strict flint` | 224 文件净（另单测 `harness/demo_server.py` + `flint/intervene/inject.py` 净） |
| `cd web; npm test -- --run` | **63 测全绿** |
| `pytest -q` | **见文末实跑尾行** |

## 5 我真看过的 / 没验证的

**真看过（逐张 Read）**：
- P10 日间桌面：9 块列表，**3 个保护块各零按钮**、6 个非保护块各 4 个控件、
  bf-04 rust 阻断卡、bf-03 中空提示
- P13 夜间桌面：5 个格式按钮（**无一预先禁用**）、块清单标出 blocking / advisory

**没验证（不背书）**：
- **四个干预动作我一个都没真点过**。lock/regenerate/dispute/evidence 的
  **成功屏与错误屏均未实屏验证**——点下去会真改账本、真派发作业。
  端点已挂、客户端已接、门控已验，但**「点了会怎样」我没看过**。
- **409 LEDGER_CONFLICT 未实机触发**：需并发改账本造版本冲突。确认流是代码在场。
- **`alignment == "partial"` 未实机取到**：需要一条真被判 partial 的证据。
- **regenerate 的派发链未端到端跑通**：判别逻辑与线程池挪移已建并经 mypy/ruff，
  但**没有真提交过一次 regenerate 看它跑完**（会调本地 qwen 生成整节）。
  坑二的「显式失败」分支同样**未实机触发**（构造不可判别的 report job 需绕过端点直接写 runner）。
- P10/P13 的**移动端两主题**只有探针「0 溢出 / 0 控制台错误」量测，未逐张看图。
- `next build` 未跑。

## 6 顺带记一条真数据观察

本轮为恢复被清空的库又跑了一次 `POST /projects/combo`，这次回的是
**`degraded: true`**（上一批那次是 `false`）。也就是说批次一 trace 里记为
「代码在场、未被真实数据触发」的 degraded=true 分支，**在真实运行中确实会出现**。
本轮未再走一遍 P3 屏去看它的呈现，故仍不算「已实屏验证」，但它不是理论分支。

## 7 落盘清单

| 文件 | 改动 |
|---|---|
| `flint/intervene/inject.py` | `aligner.align` 经 `run_in_threadpool` 挪出事件循环（坑一） |
| `tests/harness/test_inject_nonblocking.py` | **新建**（非空转，已做失败对照） |
| `harness/demo_server.py` | 挂 interventions（补三件）；`_enqueue` 按 payload 形状派发 report，判不出来显式失败（坑二） |
| `V0 files 前端设计/lib/interventions-gate.ts` | **新建**（门控唯一真相） |
| `V0 files 前端设计/lib/api/interventions.ts` | **新建**（四端点客户端） |
| `V0 files 前端设计/lib/api/base.ts` | `FlintApiError.currentVersion`（409 取 detail） |
| `V0 files 前端设计/lib/types.ts` | 补 `Alignment` 四值镜像；`ErrorBody.detail.current_version` |
| `V0 files 前端设计/app/deliverables/[id]/edit/page.tsx` | **新建**（P10） |
| `V0 files 前端设计/components/intervene/intervene-workbench.tsx` | **新建**（P10 交互） |
| `V0 files 前端设计/app/deliverables/[id]/export/page.tsx` | **新建**（P13） |
| `V0 files 前端设计/components/export/export-panel.tsx` | **新建**（P13 交互） |
| `V0 files 前端设计/scripts/check-screens.mjs` | 新增本批 19 条断言；并修掉样本缺失时**崩栈**改为如实报失败 |

**未动**：`contracts/`、`flint/domain/`、后端端点响应形状、`web/`、`flint/api/**`、`components/ui/**`。
