# V0-WIRING trace — v0 设计版前端接真后端（**事后补记**）

## 0 补记声明（先读这段）

- **本条是事后补记，不是我做的工作。** 实际实现由 owner 另开的一个专职工作 AI 会话完成，
  该会话已由 owner 关闭。它交付了实物（代码 + 三份文档），但**没有写 `docs/progress.jsonl`、
  也没有写 `docs/trace/`**，违反 CLAUDE.md:105-111（S8 台账双写）。
- **补记人**：接手的工作 AI 会话，@2026-08-01。**补记动作**：只读盘点 + 写本 trace + 追加一条
  台账条目（走 `eval/ledger_append.py:14` `append_entry`）。**零实现、零契约改动、零联网、零付费。**
- **本文所有 file:line 由补记人回源核实**，未照抄该会话文档的自述。凡我没验证的，第 6 节据实列出。
- 该会话自己写的三份文档（结论以它们为准，**补记人未改动其任何结论**）：
  - `V0 files 前端设计/docs/契约镜像-diff报告.md`
  - `V0 files 前端设计/docs/边缘态验证清单.md`
  - `V0 files 前端设计/docs/改动说明.md`

## 1 装载清单（补记人实际读了什么）

- 上述三份文档全文；
- `harness/demo_server.py` 全文（121 行）、`harness/demo_seed_report.py` 文件头边界段；
- `contracts/models.py`（:274 / :640 / :652-654 / :709-710 / :812-823）、
  `flint/api/schemas.py`（:19-35 / :43）、`flint/api/views.py`（:97-114 / :204-215）；
- `V0 files 前端设计/lib/types.ts`（9 处修正逐条定位）、`lib/api/` 六文件清单、
  三个数据屏的 import 行、`scripts/` 四脚本、`next.config.mjs`、`package.json`；
- 真库（compose PG :55432）只读查询六条，见第 3 节。

## 2 实际交付物（file:line，补记人逐条核实）

### 2.1 后端侧（2 个文件，均属胶水层）

| 文件 | 改动 | 核实位置 |
|---|---|---|
| `harness/demo_server.py` | 挂上既有 deliverables app（**未改任何端点响应形状**） | import `:35`；装配 `create_deliverables_app(DeliverableApiDeps(dsn=DSN))` `:113`；挂载循环 `:114-115`；挂载面注释 `:9-13`；CORS 注释 `:6`（`allow_origins=["*"]` 在 `:93`，本来就是 `*`） |
| `harness/demo_seed_report.py` | **新增**：报告 Block 树夹具（opt-in） | 文件头边界段自述「夹具数据非产品生成物」「`del-demo-fixture-` 前缀即标记」「不跑它报告屏就如实显 404」 |

`flint/api/compose.py`（report/proposal 提交）**刻意未挂**，理由写在 `demo_server.py:12-13`：
demo 无 report worker，挂了只会造出永远 queued 的 job（假连通）。

### 2.2 契约镜像 `V0 files 前端设计/lib/types.ts`

9 处修正全部核到行：`ErrorCode` `:73-74`、`by_source: Partial<...>` `:99`、
`CompetitorStrength`（含 moderate）`:147-149`、`StrengthSignal` `:151-152`、
`PricingRecord` `:158-160`、`strength_signals`/`pricing` `:174-175`、
`JobState` `:242`、`TERMINAL_JOB_STATES` `:252`、`project_id: string | null` `:257`、
`partial_block` 支 `:268-273`、`chosen_topic_id: string | null` `:302`、
`code: ErrorCode | string` `:331`。

### 2.3 API 客户端 `V0 files 前端设计/lib/api/`（6 文件，全新增）

`base.ts`（4834B）· `plaza.ts`（644B）· `gate.ts`（2085B）· `deliverables.ts`（2052B）·
`workbench.ts`（1891B）· `index.ts`（650B）。`lib/mock/` 原样保留、与业务屏断开。

### 2.4 三个数据屏（mock → 真 fetch）

| 屏 | 真端点 import | mock import |
|---|---|---|
| `app/plaza/page.tsx` | `:5` `fetchPlazaHot` | **零**（grep 无命中） |
| `app/gate/[jobId]/page.tsx` | `:10` `fetchJobSnapshot, fetchVerdict` | **零** |
| `app/deliverables/[id]/page.tsx` | `:8` `fetchBlocks, fetchDeliverableMeta` | **零** |

配套件（均已确认存在）：`app/plaza/loading.tsx`（新增）、`app/gate/[jobId]/not-found.tsx`、
`components/gate/gate-live.tsx`（新增 SSE）、`components/honesty/api-error.tsx`（新增）、
`components/report/block-renderer.tsx`（5 支 → 8 支 content + `assertNever` 收口）、
`components/report/report-shell.tsx`（导出由前端模拟改为真打 `/render?fmt=`）。

### 2.5 验证脚本 `V0 files 前端设计/scripts/`（4 个，全新增）

`check-connectivity.mjs`（18714B）· `check-screens.mjs`（11484B）·
`check-degraded.mjs`（2849B）· `stub-backend.mjs`（1707B）。

### 2.6 工程配置

`next.config.mjs:3` 移除 v0 出厂的 `typescript.ignoreBuildErrors`（该开关会让契约镜像偏离在
构建期静默通过）；`package.json:7,9` `-p 3001`（避开 `web/` 的 :3000）、`:10` `typecheck`、
`:11` `check:api`；`.env.local` 新增（`NEXT_PUBLIC_FLINT_API` / `NEXT_PUBLIC_FLINT_USER_ID`）。

## 3 9 处契约 diff 的结论（补记人回源复核，方向恒为「冻结件是唯一真相」）

**冻结件未被触碰**：`contracts/models.py` 与 `flint/domain/models.py` 的 SHA256 实测**完全相同**
（`b760c2eeb4e96a9624433258afce407143b2d2b8f61c66df38d4e18efd0f6c2b`），
`contracts/protocols.py` = `c5664938e16469ff2e48967bd2f46cae175c4f0dcd7a3a652a6729f03d9d3b9d`；
mtime 分别为 2026-07-27 与 2026-07-30（S2-1 基线未动）。全部 9 处出入一律改镜像侧。

| # | 出入 | 冻结件/真响应出处（补记人核到行） | 结论 |
|---|---|---|---|
| A1 | `CompetitorStrength` 漏 `moderate` | `contracts/models.py:652` 四值 Literal | 补 `moderate` |
| A2 | `Competitor.pricing` 被窄化成 string | `contracts/models.py:274` `PricingRecord`；`:654` `pricing: PricingRecord \| None` | 新增 `PricingRecord` 接口并按字段拆显 |
| A3 | `strength_signals` 过宽（`string[]`） | `contracts/models.py:640` `StrengthSignal` Literal；`:653` `list[StrengthSignal]` | 收窄为联合 |
| A4 | `JobState` 只有 5 值 | `contracts/models.py:709-710` **8 值**（+drafting/validating/cancelled） | 补齐 8 值 + `TERMINAL_JOB_STATES` |
| A5 | `JobEvent` 漏 `partial_block` | `contracts/models.py:812-813` `PartialBlockEvent`；`:823` 四支联合 | 补第四支 |
| A6 | `JobView.project_id` 当必填 | `flint/api/schemas.py:43` `project_id: str \| None` | 改可空 |
| A7 | `by_source` 假设四源必齐 | `flint/api/views.py:97,107,114`：只收当日有热度点的源 | 改 `Partial<Record<...>>`，缺源如实标注、**不补 0** |
| A8 | `chosen_topic_id` 当必填 | `flint/api/views.py:204` 未选主题时显式回 `None`（非 404） | 改可空 |
| A9 | `ErrorBody` 形状偏离 | `flint/api/schemas.py:19-27` `ErrorCode` **7 值**；`:33` `code: ErrorCode`；`:35` `detail: JSON \| None = None` | 新增 `ErrorCode` 联合；`detail` 改可选 |

**该会话标为「会真出事」的四条（A1/A4/A5/A7），补记人用真库独立验证，全部成立**：

| 断言 | 补记人实测（compose PG :55432，只读） |
|---|---|
| 库里真有 `moderate` | `snapshots` 中 3 行含 `moderate`，含 diff 报告点名的 `snap-m2042-sse-verdict` |
| 库里真有 `drafting` / `cancelled` | `select distinct state from jobs` = queued/retrieving/drafting/done/failed/**cancelled** |
| `project_id` 真为 null | `jobs` 中 `project_id is null` 共 **51** 行 |
| 簇的源真不齐 | 按簇统计不同 source_id：**192 个簇只有 1 源**，1 个簇 2 源（无四源齐的簇） |
| 瘦快照真存在（B2 口径） | `snap-m2049-tam-verdict` 全文 = `{"verdict": "C_opportunity"}` |

（首次查 `moderate` 时补记人写错了查询——`payload` 是 bytea，`::text` 出来是十六进制导致
LIKE 匹配不上、误得 0 行；改用 `convert_from(payload,'UTF8')` 后得到上表结果。**0 行那次是
查询无效，不是「不存在」**，记录在此以免后人复用错查询。）

## 4 边缘态验证怎么跑（口径：不做截图，做可重复跑的断言）

该会话报告的本次实测结果：连通性 **94/94**、屏渲染 **51/51**、坏链路 **33/33**（5xx 15 +
不可达 18），`tsc --noEmit` exit 0，`next build`（已开类型门）通过。
**补记人未复跑这三支脚本**（需后端 :8000 与前端 :3001 同时在跑），故上述数字属该会话自述，
见第 6 节的诚实边界。复跑步骤（原文见 `边缘态验证清单.md` §0）：

```powershell
# ① 后端（项目根）
$env:FLINT_DEMO_DSN='postgresql://flint:flint@localhost:55432/flint'
.\.venv\Scripts\python.exe -m harness.demo_server              # :8000

# ② 边缘态样本（两条都是后端真产物，零联网，可反复跑）
.\.venv\Scripts\python.exe -m harness.gate1_live replay-qwen   # D_insufficient 判定（回放录制）
.\.venv\Scripts\python.exe -m harness.demo_seed_report         # 报告 Block 树夹具

# ③ 前端（V0 files 前端设计）
pnpm install ; pnpm dev                                        # :3001

# ④ 三支验证
$env:FLINT_JOB='m2042-sse'; $env:FLINT_JOB_USER='u-owner'; $env:FLINT_FOREIGN_JOB='m2042-sse'
pnpm check:api                                                 # 后端诚实态
$env:FLINT_FOREIGN_JOB='m3060-ref'                             # 须为「他人发起且无判定快照」的 job
node scripts/check-screens.mjs                                 # 前端渲染
# 坏链路（要换 API 基址重起前端，故单列）：
#   node scripts/stub-backend.mjs 500 → NEXT_PUBLIC_FLINT_API=http://localhost:8010 起前端
#                                     → node scripts/check-degraded.mjs 500
#   NEXT_PUBLIC_FLINT_API=http://localhost:8099 起前端 → node scripts/check-degraded.mjs down
```

**演示库与测试库是同一个 PG**：作业期间别的进程跑测试/ingest 回放会清掉 snapshots /
deliverables / heat_points 窗口，所以 ② 的两条要在验证前现跑。`check-connectivity` 已做成
「样本不在库 → 打出重建命令并跳过，NEVER 当通过」。

样本来源（诚实交代，原文见清单 §5）：判定样本 `job-gate1-live-qwen` 是产品自己的 `run_gate1`
全流水线真算的（LLM 与 github/arxiv 走既有录制回放，零联网）；报告样本
`del-demo-fixture-report` 的**正文文本是脚本写死的夹具、不是模型产出**，但保护/争议/阻断/409
均由真端点与真门禁（`guarded_render`）算出。

## 5 已知未决三件（待 owner 示下，补记人不代拍）

### ① 夹具标记与去留 —— **当前夹具不在库中，报告屏现为 404**

补记人实测（只读）：`deliverables` 表 `del-demo%` 命中 **0 行**，`del-demo-fixture%` 的 blocks
**0 行**。即 `harness/demo_seed_report.py` 未跑（或产物已被清库清掉），此刻打开报告屏拿到的是
404「该交付物尚未生成」——按该会话的设计这**是正确行为**，不是缺陷。
待定：夹具是否长期保留、`del-demo-fixture-` 前缀标记是否够、是否要在 UI 上显式标注「夹具数据」。

### ② `degraded=true` 无屏可渲染

该字段只出现在 `POST /projects/combo` 的响应里，v0 前端**没有 combo / 主题屏**，故本轮
未能验证。客户端 `lib/api/workbench.ts#createCombo` 已按真端点备好，屏一建即可接。
（与 CLAUDE.md S4 / 问题单里 Q-009 主题 surfacing、Q-010 关联假设 surfacing 同一条线。）

### ③ 四处解引用端点缺失（前端要、后端没有）

id 全部来自冻结件，缺的是读端点。**处置一律是：只显引用本身 + 写明端点未建，NEVER 前端编内容。**

| 引用 | 冻结件出处 | 缺的端点 | 当前如实呈现 |
|---|---|---|---|
| `CitationMark.citation_id` | `contracts/models.py#CitationMark` | `GET /citations/{id}` | 只显 id，不编标题 |
| `ChartContent.chart_id` | `#ChartContent` → `#ChartSpec.derived_from` | `GET /charts/{id}` | 占位框 + chart_id；`derived_from` 明写「接口未建」 |
| `QualityCardContent.card_ref` | `#QualityCardContent` | `GET /quality-cards/{ref}` | 只显 card_ref，明写 NEVER 前端代算覆盖率/对齐率 |
| `GapNoticeContent.hints_ref` | `#GapNoticeContent` → `#SectionState.gap_hints` | `GET .../gap-hints/{ref}` | 物理切口 + hints_ref |

另有两项该会话如实登记为「本轮没能验证」：Gate 进行中的**前端** SSE 逐帧上屏（需一个真正在跑
的 job，分钟级）、`fmt=pdf` 成功路径（本机 GTK 缺失，Q-003，后端如实回 503）。

## 6 补记人验证了什么 / 没验证什么（诚实边界）

**已验证（我亲手跑或亲眼读到行）**：第 2 节全部 file:line 与文件存在性；第 3 节 9 处 diff 的
冻结件出处逐条回源；两份冻结件 SHA256 与 `flint/domain/models.py` 一致；三屏 mock import 零命中
且真 import `@/lib/api`；`next.config.mjs` 无生效的 `ignoreBuildErrors`；第 3 节表格的五条库内
事实（真库只读查询）；夹具不在库中。

**未验证（不为其背书）**：三支脚本报告的 94/51/33 与 `next build` 通过（未复跑，需前后端同时在跑）；
屏上文案的实际视觉呈现（未起前端、未截图）；`lib/api/` 六文件与各屏组件的**逐行实现质量**
（只核了 import 与文件存在，未逐行审）；`check-*.mjs` 断言本身是否空转（未逐条审断言体）；
该会话在 v0 目录下**是否还改了本文未列出的其他文件**（我按其自述 + 目录列举核对，未做全目录 diff——
该目录不在 git 下，无法出权威 diff，故这条**不确定**）。

**我未改动**：`contracts/`、`flint/domain/`、`V0 files 前端设计/` 下任何文件、该会话三份文档的
任何结论。本次唯一写入项目的是本文件与一条台账条目。

## 7 台账纪律缺口（本补记要了结的问题本体）

该会话的交付实物在，但 `docs/progress.jsonl` 与 `docs/trace/` 零记录 —— 违反 CLAUDE.md:105-111
（S8：台账双写、append-only、台账是进度唯一真相）。后果：`harness/demo_server.py` 被改动过而
台账查不到出处，接手者无从判断其归属与状态（前任交接 `docs/工作AI交接-WORKER-HANDOFF.md` §8.1
已把这点作为风险点写明）。本补记 + 对应台账条目即为该缺口的了结记录；**补记并非复核通过**——
第 6 节「未验证」项仍需 owner 或监管另行决定是否复核。
