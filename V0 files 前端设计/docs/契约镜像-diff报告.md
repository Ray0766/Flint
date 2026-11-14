# 契约镜像 diff 报告 · `lib/types.ts` ↔ 冻结件

**核对对象**：`lib/types.ts`（TS 镜像）逐字段比对 `contracts/models.py`（冻结件；与
`flint/domain/models.py` 字节一致，已核）+ 各端点的**实际响应形状**（`flint/api/*.py`
序列化处 + 库里真快照）。

**方向恒定**：冻结件是唯一真相。所有出入一律改 `lib/types.ts`，**未修改也未建议修改
`contracts/`**。

**核对日期**：2026-08-01。**结论**：发现 9 处出入，全部已按冻结件方向改完；另记录 4 处
「不算出入但需要知道」的口径。

---

## A. 已修正的出入（9 处）

| # | 位置 | 镜像原样 | 冻结件 / 真响应 | 后果（不改会怎样） | 处置 |
|---|---|---|---|---|---|
| A1 | `CompetitorStrength` | `"strong" \| "weak" \| "unknown"` | `contracts/models.py#Competitor.strength` = `Literal["strong","moderate","weak","unknown"]`；真快照 `snap-m2042-sse-verdict` 实际出现 `"moderate"` | 漏一支枚举。竞品行按"非 unknown 即照原样显"渲染，`moderate` 落进类型空档；一旦按强度分形态就会漏渲或错渲 | 补 `"moderate"` |
| A2 | `Competitor.pricing` | `string \| null` | `PricingRecord \| None`（`contracts/models.py#PricingRecord`：plan/price/currency/region/confidence/captured_at/url） | 把对象窄化成字符串。当前 `gate1.py` 落库恒 `pricing: null`，所以"跑起来不报错"——但定价一旦接上就是对象，前端会把 `[object Object]` 打在屏上 | 新增 `PricingRecord` 接口，`pricing: PricingRecord \| null`，并在 Gate 屏按字段拆开显（含 `price===null` → 「待确认」） |
| A3 | `Competitor.strength_signals` | `string[]` | `list[StrengthSignal]`，`StrengthSignal = Literal["funded_or_scaled","mature_pricing","same_target_user","active_last_12m"]` | 类型过宽，拼错的信号名不会被 TS 拦住 | 新增 `StrengthSignal` 联合并收窄 |
| A4 | `JobState` | 5 值（queued/retrieving/judging/done/failed） | 8 值：+ `drafting` / `validating` / `cancelled` | 漏三支。库里**已有** `state=drafting` 与 `state=cancelled` 的 report 线 job（`m3059-j1`、`m3057-2ca1ea5508`）——这些 job 的快照落进类型空档，终态判定（`done/failed/cancelled`）也会漏掉 `cancelled` 而永远等下去 | 补齐 8 值；并新增 `TERMINAL_JOB_STATES` 常量供 SSE 关流判定 |
| A5 | `JobEvent` 判别联合 | 3 支（status/step/failed） | `contracts/models.py#JobEventPayload` 4 支：+ `PartialBlockEvent{kind:"partial_block", block_id}` | 漏一支。渐进交付事件（M3-059 `emit_partial_blocks` 会发）到达时，穷尽分支的 `switch` 会掉进 `undefined` | 补 `partial_block` 支；`GateLive` 的 `describe()` 已覆盖四支 |
| A6 | `JobView.project_id` | `string` | `flint/api/schemas.py#JobView.project_id: str \| None`（系统级 job 无 project） | 可空字段当必填。`m2005-job` 等真数据 `project_id` 为 null | 改 `string \| null` |
| A7 | `PlazaCluster.by_source` | `Record<SourceKey, number>`（四源必齐） | `flint/api/views.py#plaza` 只回**当日实际有热度点**的源，`dict[str, float]` | 假设四源必齐。真数据里大量簇只有 1~2 源（本次实测某簇只有 `weibo`），原代码 `by_source[src]` 取到 `undefined` 直接打在屏上 | 改 `Partial<Record<SourceKey, number>>`；广场屏对缺源如实标「该源当日无数据」，**不补 0** |
| A8 | `TopicsResponse.chosen_topic_id` | `string` | `views.py#project_topics` 未知 project / 未选主题时显式回 `null`（非 404） | 可空当必填 | 改 `string \| null` |
| A9 | `ErrorBody` | `{code: string; message: string; detail: {blocking_block_ids: string[]} \| null}` | `flint/api/schemas.py#ErrorBody`：`code` 是 7 值 `ErrorCode` 枚举；`detail` 是自由 JSON，且 `model_dump(exclude_none=True)` 时 **`detail` 键整个不出现**；`fmt=pack` 门禁回的是 `{violations: [...]}` 而非 `blocking_block_ids` | `detail` 声明为必填 → 大多数错误体（没有 detail 键）不符类型；`violations` 形状缺席 | `code: ErrorCode \| string`（新增 `ErrorCode` 联合）；`detail?: {blocking_block_ids?; violations?} \| null` |

---

## B. 不算出入，但口径要写明（4 处）

| # | 事项 | 说明 |
|---|---|---|
| B1 | `Block` / `BlockContent` 判别联合 | **逐字段一致，零出入**。8 支 content、13 个 Block 字段、`author`/`locked`/`user_modified`/`needs_review`/`review_reason`/`review_severity` 全对得上。`isProtected(block) = locked ∨ author==="user" ∨ user_modified` 与 `contracts/models.py#Block` 文档串一致 |
| B2 | `Verdict.constraints_checked` | 冻结件 `VerdictResult.constraints_checked` 的类型是自由 `JSON`；`lib/types.ts` 里的 `ConstraintsChecked` 是 `flint/gate/engine.py#decide` **实际摊平**出的形状（已逐字比对，一致）。但库里存在早期快照只有 `{"verdict": "C_opportunity"}`（`snap-m2049-tam-verdict`）——故 `Verdict` 上除 `verdict` 外全部改成可选，屏上缺字段处如实标「未记录」，**不补默认值冒充已评估** |
| B3 | `Gap` ↔ `GapHint` | 字段逐字一致（missing_what / cause / suggested_sources / action / target_count / required_scope）。仅接口名不同（前端沿用 `Gap`），无语义差 |
| B4 | `VerdictKind` ↔ `Verdict` | 冻结件里四档档位的类型名是 `Verdict`，前端叫 `VerdictKind`（因为前端 `Verdict` 这个名字给了整个判定对象）。四个字面量逐字一致 |

---

## C. 顺带修的渲染面漏支（不属类型 diff，但同源）

- `components/report/block-renderer.tsx` 原只分派 **5 支** content（declaration / paragraph /
  table / chart / gap_notice），真后端可以发满 **8 支**。补齐 `heading` / `quality_card` /
  `citation_list`，末尾用 `assertNever(content)` 收口——将来冻结件加支，TS 会在这里报错，
  而不是静默漏渲一个块。
- `quality_card` / `citation_list` 的解引用端点尚未提供，故只显引用位（`card_ref` /
  `citation_id`），**不前端代算任何指标**。

---

## D. 结论

- 冻结件与 `contracts/` **未被触碰**；本次全部改动落在 `lib/types.ts` 与前端渲染面。
- A1 / A4 / A5 / A7 是**会真出事**的四条：`moderate` 与 `drafting/validating/cancelled`
  在库里已有真数据，`partial_block` 在 report 线一定会发，`by_source` 缺源本次实测就命中。
- 其余五条是"当前实现恰好没踩到"的窄化，按冻结件拓宽以免以后踩。
