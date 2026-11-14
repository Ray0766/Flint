# HOTSPOT-03 trace — 分析界面骨架（默认展示 Gate① 既有判定，零新计算）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md` 全文、卡片 `tasks-v04.json#HOTSPOT-03`；
- context_refs：`WORKORDER-v04.md#5-C`（C6/C7 两行）、`WORKORDER-v04.md#6`（H 组复用清单）、
  `contracts/models.py` 的 `Cluster/Job/VerdictResult/AnalysisContext` 四类；
- 前置产物（按 inputs 定位，非全仓浏览）：`flint/api/views.py`、`web/lib/viewsClient.ts`、
  `web/lib/i18n/{t.ts,config.ts}`、`web/messages/{zh,en}.json`、
  `web/components/hotspot-card/HotspotCard.tsx`（缺失逐槽隐藏纪律）、
  `web/views/library-empty/LibraryEmpty.tsx`（空态即明确状态）、
  `tests/fe_views/test_read_endpoints.py`（既有端点测试惯例）、
  `tests/v04/fav/test_batch_ops.py`（v04 后端测试惯例）。
- 实测装载 ≈ 21k tokens，未超 40k 预算。

## 2 一处规格与真件不符（已上报，非阻塞）

卡片 inputs 写 `GET /clusters/{id}/verdict(既有)` —— 真件无此端点，判定按 **job 键**
落在 `snapshots['snap-{job}-verdict']`；`Job` 无 cluster 字段、`VerdictResult` 无 cluster_id、
`jobs` 表无 cluster_id，**cluster→判定 的对应关系当前没有持久化真相**。

处理：按 §1.4 写 `docs/blocked/HOTSPOT-03.md` 上报 + `DECISIONS-v04.md#DEC-010` 记决定，
**NEVER 自行择一后不留痕**。未记 `blocked` 事件的理由写在明处：本卡两条 acceptance
（渲染既有判定与证据概览且零新分析调用 / 界面语言=系统语言）**都不依赖那个端点路径**，
对应关系改由调用方给出即可交付，属 §3「缺口的交互部分按绕行界限做可交付态」。
owner 若判定该走乙案（真建 cluster 键端点），本卡产出无须回炉，只需新增一张端点卡。

## 3 test-first 顺序（§4.2）

1. 先写 `web/views/analysis/AnalysisView.test.tsx`（8 条）→ 跑 → 红
   （`Failed to resolve import "./AnalysisView"`，Test Files 1 failed / no tests）；
2. 再写 `tests/v04/hotspot/test_analysis_view_api.py`（7 条）→ 跑 → 红（3 failed / 4 passed，
   `pytest.mark.asyncio` 无 asyncio_mode 支持）；
3. 后端改用仓库既有惯例 `run(coro) = asyncio.run(coro)`（同 `tests/fe_views`）→ 7 passed；
4. 实现 `AnalysisView.tsx` + 补 10 条 i18n key（zh/en 各 27 键，键集一致）→ 前端 8 passed。

## 4 acceptance ↔ 测试映射

**① 进入即渲染既有判定与证据概览；无任何新分析调用（网络层 spy）**

| 测试 | 断的是什么 |
|---|---|
| 进入即渲染既有判定 | 判定值**逐字**来自后端（`C_opportunity`）+ `data-verdict` 可机读；前端 NEVER 自判 |
| 进入即渲染证据概览 | 两张证据卡各自成条、`data-card-id` 对得上、计数取自后端字段 |
| 无任何新分析调用 | spy 全程只有 GET；`/analysis` 一次不出现；**且 `calls.length >= 2`** |
| 尚无既有判定 | 渲染未判定态、`analysis-verdict` 不存在、文案 NEVER 含四分类值、仍零写请求 |
| 未给 job 时不猜 | 不发 `/verdict` 请求（NEVER 拿 cluster_id 拼一个 job id 去试） |
| 读端点复用既有客户端 | 正向断 `from "../../lib/viewsClient"`，反向断源码无 `/jobs/`、无 `/evidence-cards` |
| （后端）读端点只读 | 两个端点方法 ⊆ {GET, HEAD}；整张读端点表零写路由 |
| （后端）只跑 SELECT | 假连接记 SQL：≥1 条且零 INSERT/UPDATE/DELETE（判定读、证据读各一） |
| （后端）阴性对照 | 写语句检查器认得出 INSERT/update/DELETE，且不误伤 SELECT |
| （后端）判定缺失 | 404 且响应体不含四分类任一值 —— NEVER 当场造一个 |
| （后端）import 面 | `flint/api/views.py` 不 import anthropic / flint.gate / flint.jobs / flint.llm / flint.compose |

**「零新计算」为什么必须两边各断一次**：前端 spy 只能证明浏览器没发写请求；
后端若把一次 GET 做成「查不到就跑一次」，用户每次点开都付一次钱，且同一个热点
**什么都没做、判定却变了**——判定本身就不再可被引用。后端那条 import 断言正是为了让
「改天有人在端点里补一句就地重算」在 import 面上先红。

**② 界面语言=系统语言（C11）**

| 测试 | 断的是什么 |
|---|---|
| 文案经 t() 取词条 | 源码代码行零 CJK + 引 `lib/i18n/t`；且渲染文案**不等于 key 原样**（t() 缺 key 时回落成 key，只断非空会绿） |
| 视图不持有语言状态 | 源码无 `navigator.language` / `Accept-Language`；props 面无 `lang`/`locale`；不 `resolveLocale`、不由 region 反推（A3 反例第一/三条） |

## 5 四态不互相冒充

加载中 / 已判定 / 未判定 / 读失败各自一态。**未判定与读失败尤其不能合并**：
前者是这个热点还没过 Gate①，后者是我们没读到——用户据此做的下一步动作完全不同
（去点分析 vs 刷新重试）。证据概览同理分四态，空态是明确状态而不是加载失败
（沿用 FAV-06 口径）。未判定态也 NEVER 用 `—`/`暂无` 占位（沿用 HOTSPOT-01 口径）。

## 6 verify（卡上 verify_cmd 是合取，两段分别在各自 cwd 跑）

```
$ cd web && npm test -- --run views/analysis     → 8 passed (1 file)
$ pytest tests/v04/hotspot/test_analysis_view_api.py -q  → 7 passed
```

回归：前端全套 **160 passed / 26 files**；`npm run typecheck` 干净；
`ruff check . --no-cache` 全绿；`mypy --strict flint` 250 files 净；
`node tools/i18n_scan.mjs web/views --fail-on-cjk` exit 0（6 源文件、CJK 0、白名单 0、B7 0）。

## 7 一处观测（不属本卡 acceptance，留给 I18N 线）

`i18n_scan` **按目标目录**跑：`web/views`、`web/components` exit 0，但
`node tools/i18n_scan.mjs web --fail-on-cjk`（整个 web 树）exit 1，报 7 个文件。拆开看两类：

- **工具假阳性 3 个**：`lib/i18n/config.ts`、`lib/i18n/t.ts`、`stores/prefs.ts` ——
  命中的都是 **JSDoc 块注释行**（`* 取一条文案。`）。工具自己的口径是「注释行不算」，
  但 `cjkLines()` 只剥 `//` 与**单行** `/* ... */`，跨行块注释漏网。
- **真命中 4 个**：`app/deliverables/[id]/page.tsx`、`app/jobs/[id]/page.tsx`、
  `app/layout.tsx`（title）、`lib/i18n.ts`（v0.3 遗留的另一份词条表，与 `messages/` 重复）。

即 SELFCHECK-V2 里那句「i18n_scan --fail-on-cjk exit 0」成立的前提是**扫描面为组件/视图目录**，
而非整个 `web/`。已在 `docs/trace/SELFCHECK-V2.md` 追一节说明（NEVER 回改原文）。
修法（剥块注释 + 收 app/ 与 lib/i18n.ts）属 I18N-02 那条线，不在本卡 acceptance 内。

## 8 产出

- `web/views/analysis/AnalysisView.tsx`、`web/views/analysis/AnalysisView.test.tsx`（8 条）
- `tests/v04/hotspot/test_analysis_view_api.py`（7 条）
- `web/messages/zh.json` / `web/messages/en.json`：各 +10 key（27 键，键集一致）
- `docs/blocked/HOTSPOT-03.md`（非阻塞上报单）、`DECISIONS-v04.md#DEC-010`
