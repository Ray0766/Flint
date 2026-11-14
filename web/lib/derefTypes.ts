// TYPE-05：六条解引用端点的响应形状（`flint/api/deref.py`，FB-04~FB-09）。
//
// ## 为什么这几条此前「没有类型」
//
// `derefClient.ts` 的 `DerefResult` 把内容放在 `data: unknown` 里——
// **那是它自己那一层的正确选择**（它只判「拿到了还是没拿到」，不解释内容）。
// 但调用方拿到 `unknown` 之后就没有任何东西可依：
// 一个写错的字段名要到运行时才现形，而现形的样子是屏上一片空白。
//
// ## 尺子报的「field_mismatch」，六条里有五条是**认错了接口**
//
// `tools/check_fe_be_parity.py#_best_interface` 拿后端字段集去 `web/lib/**`
// 找最像的接口。门槛松时它会挑中一个**只是碰巧同名**的：
//
// | 端点 | 它挑中的 | 凭什么 |
// |---|---|---|
// | `/charts/{}` | `DisputeSubmitEcho` | 共有 `status` |
// | `/facts/{}` | `DisputeSubmitEcho` | 共有 `status` / `ledger_version` |
// | `/hints/{}` | `VerdictGap` | 共有 `missing_what` / `cause` / `action` |
//
// 所以本卡做的**不是「对齐那些接口」**——那会把 chart 的字段塞进一个争议回执里
// （`DEC-034` / `DEC-038` 反复禁的借槽）。本卡给它们**各建自己的类型**。
//
// ## 字段类型逐个对着后端读，NEVER 一律 `unknown`
//
// 全 `unknown` 能让尺子归零，而**那不是类型**：`tsc` 从此对这几条端点
// 一个字都不检查，而尺子是绿的。
// 只有真的是任意 JSON 的那一格才写 `unknown`（`value` / `evidence_snapshot`）——
// 那是**如实**，不是偷懒。

// ── `/facts/{id}`（FB-04）

/** 一条事实。前十项逐字对齐冻结件 `Fact`，后四项是端点加的上下文。 */
export interface FactDeref {
  fact_id: string;
  statement: string;
  /** 账本里那条的值。**真的是任意 JSON**（数字 / 字符串 / 结构体都出现过）。 */
  value: unknown;
  unit: string | null;
  citation_ids: string[];
  status: string;
  origin: string;
  created_in_version: number;
  source_claim_id: string | null;
  promoted_from: string | null;
  // —— 以下非冻结件字段：上下文，不参与三通道语义 ——
  project_id: string;
  ledger_version: number;
  channel: string;
  /** `status === "disputed"` 的派生位。后端算好给的，前端 NEVER 自己再判一次。 */
  disputed: boolean;
}

// ── `/charts/{id}`（FB-07）

/** 图上的一个点。它就是账本里那条 fact——**端点一个算术符号都没写**。 */
export interface ChartPoint {
  fact_id: string;
  statement: string;
  value: unknown;
  unit: string | null;
  citation_ids: string[];
  status: string;
  ledger_version: number;
}

export interface ChartDeref {
  chart_id: string;
  chart_type: string;
  derived_from: string[];
  points: ChartPoint[];
  /** 取不到的 fact 落这里，**NEVER 被丢掉**：少一个点的折线图看起来完全正常。 */
  unresolved: string[];
  /** `unresolved` 为空。调用方有权知道自己拿到的是不是残的。 */
  complete: boolean;
  /** 恒 `false`：这条端点不算任何东西。 */
  computed: boolean;
  channel: string;
}

// ── `/cards/{id}`（FB-08）

/** 卡所属簇的几个字段——带上它，正文里那个 `card-2026…` 一次请求就能换成人话。 */
export interface CardCluster {
  canonical_name: string;
  status: string;
  /** ISO 日（后端 `.isoformat()`）。前端不解析、不换算。 */
  first_seen: string;
  last_active: string;
}

export interface CardDeref {
  card_id: string;
  cluster_id: string;
  keyword_ids: string[];
  flags: string[];
  top_links: string[];
  cluster: CardCluster;
  channel: string;
}

// ── `/hints/{ref}`（FB-09）

/** 一条缺口。`is_conclusion` 恒 `false`——**缺口是缺口，不是一句站住的结论**。 */
export interface HintRow {
  missing_what: string;
  /** `missing_data` 去补资料 / `missing_permission` 去要权限——**两种修法完全不同**。 */
  cause: string;
  suggested_sources: string[];
  action: string;
  target_count: number | null;
  required_scope: string | null;
  /** 话术取自冻结件 `GapHint` 的 docstring，前端**原样显示**。 */
  why: string;
  is_conclusion: boolean;
}

export interface HintsDeref {
  hints_ref: string;
  hints: HintRow[];
  is_conclusion: boolean;
  channel: string;
}

// ── `/citations/{id}`（FB-06）与 `/price-entries/{id}`（FB-05）
// 这两条属 `TYPE-06`（它们是「根本没建类型」那一类），一并落在这里：
// 六条解引用通道的形状**同住一个文件**，读的人一次看全。

/** 引用指向的那篇文献。**正文本身不在这里给**——那是另一件事。 */
export interface CitationDoc {
  title: string;
  url: string;
  kind: string;
  /** ISO 日或 `null`（没有出版日期是常态，NEVER 编一个）。 */
  published_at: string | null;
  origin: string;
  access: string;
  /** 库里那份正文的指纹：下游据此判断「我手上这份与库里那篇是不是同一份」。 */
  content_sha256: string | null;
  /** 这篇正文被截断过——引文取自被截断的正文时，读者有权知道。 */
  content_truncated: boolean;
  content_note: string | null;
}

export interface CitationDeref {
  citation_id: string;
  doc_id: string;
  locator: string | null;
  quote_span: string | null;
  /** 钉住了具体段落。`false` = 失锚——**照实标记且照常返回**。 */
  anchored: boolean;
  /** 失锚时那一句说明；`anchored` 为真时是 `null`。 */
  anchor_note: string | null;
  doc: CitationDoc;
  /** 私有材料不外链（审5）。**依据交给下游**，下游猜不出来的规则等于没有规则。 */
  external_link_allowed: boolean;
  share_note: string | null;
  channel: string;
}

export interface PriceDeref {
  price_entry_id: string;
  item: string;
  unit: string;
  price_low: number;
  price_high: number;
  currency: string;
  region: string;
  source: string;
  quantity: number;
  /** 金额由**后端**算（`price × quantity`）；前端 NEVER 自己乘（FB-05 的判据）。 */
  amount_low: number;
  amount_high: number;
  stale: boolean;
  yellow_flag: boolean;
  price_year: number;
  price_data_note: string | null;
  channel: string;
}
