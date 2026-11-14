// 冻结件 contracts/models.py 的 Block / BlockContent 判别联合的 TS 镜像。
// 后端 FE-000 端点经 asdict 输出，content 带 `kind` 判别字段——此处逐字对齐。
// 冻结件是唯一真相；此镜像只读消费，NEVER 反向改冻结件。

export interface TextSpan { kind: "text"; text: string; }
export interface ClaimSpan { kind: "claim"; claim_id: string; text: string; disputed_mark: boolean; }
export interface CitationMark { kind: "cite"; citation_id: string; }
export interface ProfileRef { kind: "profile"; field_path: string; }
export type InlineSpan = TextSpan | ClaimSpan | CitationMark | ProfileRef;

export interface TextCell { kind: "text"; text: string; }
export interface FactCell { kind: "fact"; fact_id: string; }
export interface PriceCell { kind: "price"; price_entry_id: string; quantity: number; }
export type TableCell = TextCell | FactCell | PriceCell;

export interface HeadingContent { kind: "heading"; level: number; text: string; }
export interface ParagraphContent { kind: "paragraph"; spans: InlineSpan[]; }
export interface TableContent { kind: "table"; header: string[]; rows: TableCell[][]; }
export interface ChartContent { kind: "chart"; chart_id: string; }
export interface DeclarationContent { kind: "declaration"; text: string; }
export interface QualityCardContent { kind: "quality_card"; card_ref: string; }
export interface CitationListContent { kind: "citation_list"; citation_ids: string[]; }
export interface GapNoticeContent { kind: "gap_notice"; hints_ref: string; }

export type BlockContent =
  | HeadingContent
  | ParagraphContent
  | TableContent
  | ChartContent
  | DeclarationContent
  | QualityCardContent
  | CitationListContent
  | GapNoticeContent;

export type BlockType = BlockContent["kind"];

export interface Block {
  block_id: string;
  deliverable_id: string;
  section_id: string;
  order: number;
  type: BlockType;
  content: BlockContent;
  claim_ids: string[];
  fact_ids: string[];
  author: "system" | "user";
  revision: number;
  locked: boolean;
  user_modified: boolean;
  needs_review: boolean;
  review_reason: string | null;
  review_severity: string | null;
}

export interface BlocksResponse {
  deliverable_id: string;
  blocks: Block[];
}

// 保护条件 (v0.3.2 / S2-5)：locked ∨ author=="user" ∨ user_modified 的 block,
// 前端强制只读——L0 全页只读，此判定为 L2 干预层前的常驻保护。
export function isProtected(block: Block): boolean {
  return block.locked || block.author === "user" || block.user_modified;
}

// ───────────────────────────────────────────────────────────────────────────
// §2.1 热点广场响应契约 · GET /plaza/hot
// 上方 Block 镜像为冻结件、只读；以下为另一组响应契约，字段逐字对齐 §2.1 示例 JSON,
// 仅声明 lib/mock/plaza.ts 事实源实际出现的字段，NEVER 发明新字段。
// ───────────────────────────────────────────────────────────────────────────
export type SourceKey = "arxiv" | "ghtrend" | "gtrends" | "weibo";

// 后端错误体的 code 枚举（flint/api/schemas.py#ErrorCode 逐字镜像）。
export type ErrorCode =
  | "LEDGER_CONFLICT"
  | "EXPORT_BLOCKED"
  | "PERMISSION_DENIED"
  | "BUDGET_EXCEEDED"
  | "NOT_FOUND"
  | "VALIDATION_FAILED"
  | "SERVICE_UNAVAILABLE";

export interface HotnessComponents {
  velocity: number;
  accel: number;
  cross_count: number;
  multi_boost: number;
  novelty_factor: number;
  decay: number;
}

export interface PlazaCluster {
  cluster_id: string;
  canonical_name: string;
  category_id: string;
  status: string;
  // 真端点（flint/api/views.py#plaza）只回**当日实际有热度点**的源，四源不保证齐全。
  // 故为 Partial：缺的源 = 该簇当日该源无数据，前端如实标「无数据」，NEVER 补 0。
  by_source: Partial<Record<SourceKey, number>>;
  total_heat: number;
  hotness: number;
  hotness_components: HotnessComponents;
}

export interface WeakSignal {
  cluster_id: string;
  canonical_name: string;
  category_id: string;
  status: string;
  weak_score: number;
  agg: number;
  velocity: number;
  drift: number;
  burst_weight: number;
}

export interface PlazaHotResponse {
  day: string;
  clusters: PlazaCluster[];
  weak_signals: WeakSignal[];
}

// §2.2 工作台证据卡响应契约 · GET /clusters/{cluster_id}/evidence-cards
export interface EvidenceCard {
  card_id: string;
  cluster_id: string;
  keyword_ids: string[];
  flags: string[];
  top_links: string[];
}

export interface EvidenceCardsResponse {
  cluster_id: string;
  evidence_cards: EvidenceCard[];
}

// contracts/models.py:303 Alignment（**四值**，含 pending —— 逐字镜像，NEVER 少抄一支）。
// 契约不变量：alignment=="partial" 的 claim NEVER 被提升为 Fact（S2-4）。
export type Alignment = "pending" | "supports" | "partial" | "unsupported";

// §2.12 大类目录 · GET /categories（flint/api/app.py → flint/repo/categories.py）
// 人工固定资产（assets/categories.yaml，12 类），端点只读。
// S0 外壳的筛选用它；**筛选仅隐藏行，NEVER 重排主榜**（主榜序由后端 hotness 给定）。
export interface Category {
  category_id: string;
  name: string;
}

// ───────────────────────────────────────────────────────────────────────────
// §2.5 Gate 判定响应契约 · GET /jobs/{job_id}/verdict
// 仅声明 lib/mock/verdict.ts 事实源实际出现的字段，NEVER 发明新字段。
// ───────────────────────────────────────────────────────────────────────────
export type VerdictKind =
  | "A_infeasible"
  | "B_red_ocean"
  | "C_opportunity"
  | "D_insufficient";

// 冻结件 contracts/models.py#Competitor.strength 是**四值**（含 moderate）。
// 真快照 snap-m2042-sse-verdict 实际出现 "moderate"——曾漏此值，前端会漏渲。
export type CompetitorStrength = "strong" | "moderate" | "weak" | "unknown";

// contracts/models.py#StrengthSignal
export type StrengthSignal =
  | "funded_or_scaled"
  | "mature_pricing"
  | "same_target_user"
  | "active_last_12m";

// contracts/models.py#PricingRecord。当前 Gate① 快照恒 pricing:null（gate1.py
// 落库时不带定价），但契约上是对象——按冻结件镜像，NEVER 按当前实现窄化成 string。
export interface PricingRecord {
  plan: string;
  price: number | null;
  currency: string;
  region: string;
  confidence: number;
  captured_at: string;
  url: string;
}

export interface Competitor {
  name: string;
  url: string;
  strength: CompetitorStrength;
  strength_signals: StrengthSignal[];
  pricing: PricingRecord | null;
}

export type GapCause = "missing_data" | "missing_permission";
export type GapAction = "search" | "ask_user" | "upload" | "request_permission";

export interface Gap {
  missing_what: string;
  cause: GapCause;
  suggested_sources: string[];
  action: GapAction;
  target_count: number | null;
  required_scope: string | null;
}

export interface RuleA {
  satisfied: boolean;
  used_user_evidence_only: boolean;
  blocked_pending_optin: boolean;
}

export interface RuleB {
  satisfied: boolean;
  by_count: boolean;
  by_strength: boolean;
  reachable_count: number;
  strong_names: string[];
}

export interface RuleC {
  satisfied: boolean;
  failed_conditions: string[];
  blocking_competitors: string[];
}

export interface ConstraintsChecked {
  order: VerdictKind[];
  demoted_by_alignment: boolean;
  rule_a: RuleA;
  rule_b: RuleB;
  rule_c: RuleC;
  gap_count: number;
}

// 冻结件 VerdictResult.constraints_checked 类型是 JSON（自由字典），上面的
// ConstraintsChecked 是 flint/gate/engine.py#decide 实际摊平出的形状。历史快照
// （如 snap-m2049-tam-verdict = {"verdict":"C_opportunity"}）可能缺字段——故
// Verdict 上除 verdict 外全部按 Partial 消费，前端缺字段处如实标「未记录」，
// NEVER 补默认值冒充已评估。
export interface Verdict {
  verdict: VerdictKind;
  all_satisfied?: VerdictKind[];
  key_citation_ids?: string[];
  rationale_fact_ids?: string[];
  competitors?: Competitor[];
  constraints_checked?: ConstraintsChecked;
  gaps?: Gap[];
}

export interface VerdictResponse {
  job_id: string;
  verdict: Verdict;
}

// §2.6 分析 Job + SSE · GET /jobs/{job_id} 与 /jobs/{job_id}/events
// contracts/models.py#JobState 是**八值**——曾漏 drafting/validating/cancelled，
// report 线 job（真库里已有 state=drafting/cancelled 的行）会落进 TS 的类型空档。
export type JobState =
  | "queued"
  | "retrieving"
  | "judging"
  | "drafting"
  | "validating"
  | "done"
  | "failed"
  | "cancelled";

export const TERMINAL_JOB_STATES: readonly JobState[] = ["done", "failed", "cancelled"];

export interface JobView {
  job_id: string;
  kind: string;
  project_id: string | null;   // flint/api/schemas.py#JobView：可空（系统级 job 无 project）
  state: JobState;
  progress: number;
  partial_output_ref: string | null;
  budget: number;
  cost_accum: number;
  error: string | null;
  created_at: string;
  updated_at: string;
}

// contracts/models.py#JobEventPayload 判别联合（四支）——曾漏 partial_block，
// 渐进交付事件到达时会 crash 在穷尽分支上。
export type JobEvent =
  | { kind: "status"; state: JobState }
  | { kind: "step"; step_name: string; phase: "start" | "end"; cost: number | null }
  | { kind: "partial_block"; block_id: string }
  | { kind: "failed"; reason: string };

// §2.4 主题列表 · GET /projects/{project_id}/topics
export interface TopicEvidence {
  event: string;
  event_date: string;
  citation_id: string;
}

export interface TopicWhyNow {
  claim: string;
  speculative: boolean;
  evidences: TopicEvidence[];
}

export interface Topic {
  topic_id: string;
  seed_id: string;
  one_liner: string;
  target_user_tag: string;
  form_factor_tag: string;
  why_now: TopicWhyNow;
  keyword_mapping: Record<string, string[]>;
}

export interface TopicsResponse {
  project_id: string;
  // 真端点未知 project / 未选主题 → null（views.py 显式回 null，非 404）。
  chosen_topic_id: string | null;
  topics: Topic[];
}

// GET /topics/{topic_id} 单主题（views.py#topic_detail 外层包 {topic:...}）
export interface TopicDetailResponse {
  topic: Topic;
}

// §2.3 combo 创建响应
export interface ComboCreateResponse {
  project_id: string;
  topic_ids: string[];
  degraded: boolean;
}

// §2.7 交付物元信息 · 随 blocks 一同用于报告头
export interface DeliverableMeta {
  deliverable_id: string;
  type: string;
  version: number;
  ledger_version: number;
  reproducible: boolean;
}

// 通用错误体 · 409 EXPORT_BLOCKED / 409 LEDGER_CONFLICT / 503 SERVICE_UNAVAILABLE 等
// 后端 detail 是自由 JSON：md/html/pdf/docx 门禁回 {blocking_block_ids}，
// fmt=pack 门禁回 {violations}，干预层乐观锁冲突回 {current_version}，
// 其余端点回 null（exclude_none 时该键直接不出现）。
export interface ErrorBody {
  code: ErrorCode | string;
  message: string;
  detail?: {
    blocking_block_ids?: string[];
    violations?: string[];
    // interventions.py：LedgerVersionConflict → 409 LEDGER_CONFLICT，
    // detail.current_version = 账本已前进到的版本（可能为 null，后端未携带时）。
    current_version?: number | null;
  } | null;
}
