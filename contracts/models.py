"""燧石 Flint · 领域模型冻结件 (M0, 执行顺序 ③)

纯类型定义, 无实现。Python >= 3.11。
覆盖: PDD v0.1~v0.3.2 + M0 决策记录 (D1~D13) + 审核 1~11 (v0.3.1 附录 C) + 终轮补丁 (v0.3.2)。
冻结规则: 本文件的任何改动只能来自 ⑧ 对抗性推演产出的 v0.4 修订; 纸面评审轮次已停止。
[D*] 对应 M0 决策记录; [B*][C*][A*] 对应 PDD v0.2; [审N] 对应 v0.3.1 审核意见。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

Vector = list[float]
JSON = dict[str, Any]

# ═════════════════════ 身份与多租户 [D5]

Role = Literal["owner", "admin", "member", "viewer"]


@dataclass
class User:
    user_id: str
    email: str
    display_name: str
    created_at: datetime


@dataclass
class Org:
    org_id: str
    name: str
    created_at: datetime


@dataclass
class Membership:
    user_id: str
    org_id: str
    role: Role


@dataclass
class Principal:
    """一切顶层资源的归属: 个人或组织 (= PDD 的 OwnerScope)。个人使用无需先建 Org。
    授权原则: 访问 = 归属直属, 或经 Membership.role 解析。"""
    kind: Literal["user", "org"]
    id: str


# ═════════════════════ 数据与索引层 [A1~A4]

@dataclass
class Keyword:
    keyword_id: str
    canonical: str          # 规范化后形态 (A3 管道产物)
    lang: str
    aliases: list[str]
    embedding: Vector
    first_seen: date


ClusterStatus = Literal["active", "dormant", "merged"]


@dataclass
class Cluster:
    cluster_id: str                  # 稳定 ID, 跨日不变 [A1]
    canonical_name: str
    category_id: str                 # 大类 (人工固定目录)
    centroid: Vector
    status: ClusterStatus            # dormant 永不物理删除
    first_seen: date
    last_active: date
    parent_cluster_ids: list[str]    # 血缘: 分裂/合并来源
    merged_into: str | None
    aliases: list[str]


@dataclass
class HeatPoint:
    cluster_id: str
    source_id: str
    day: date
    raw_value: float                 # 原始单位, 跨源不可直接比较 [A2]
    norm_score: float                # 源内 90 天分位 0~100


SignalFlag = Literal["novelty", "momentum", "revival"]  # [A4] 直接喂 why now


@dataclass
class EvidenceCard:
    card_id: str
    cluster_id: str
    keyword_ids: list[str]
    flags: list[SignalFlag]
    top_links: list[str]


# ═════════════════════ 血缘日更产物 [A1][v0.4 增补 Q-002, owner 决策清单 2026-07-27]

@dataclass
class ContinuedEvent:
    kind: Literal["continued"]
    cluster_id: str                  # 既有簇, ID 跨日稳定
    keyword_ids: list[str]           # 当日归入关键词 (M1-024 assignments)


@dataclass
class SplitEvent:
    kind: Literal["split"]
    new_cluster_id: str
    parent_cluster_ids: list[str]    # 列表, 与合并同形 (决策④)
    keyword_ids: list[str]


@dataclass
class MergedEvent:
    kind: Literal["merged"]
    new_cluster_id: str
    merged_cluster_ids: list[str]    # 旧簇全部 merged_into=new_cluster_id
    keyword_ids: list[str]


@dataclass
class NewClusterEvent:
    kind: Literal["new"]
    cluster_id: str
    parent_cluster_ids: list[str]    # 1:1 弱链接来源, 可空
    keyword_ids: list[str]
    naming_degraded: bool            # LLM 命名降级为 top 关键词 (M1-027)


@dataclass
class RevivedEvent:
    kind: Literal["revived"]
    cluster_id: str                  # dormant → active, ID 复用
    keyword_ids: list[str]           # 取当日 assignments; 复活簇只记本条,
                                     # 不再重复出 ContinuedEvent (决策①②)


LineageEvent = (
    ContinuedEvent | SplitEvent | MergedEvent | NewClusterEvent | RevivedEvent
)


@dataclass
class CentroidDriftAudit:
    """漂移防护留痕: 单日簇心 cosine 位移超限被拒绝。全系统唯一命名 (决策③),
    实现层不得另设同义类型。"""
    cluster_id: str
    attempted_shift: float
    max_shift: float
    action: Literal["rejected"]


@dataclass
class LineageResult:
    """血缘日更批产物 (决策⑤): append-only, lineage_id (uuid) 为主键、day 为
    索引列; 三阈值参数快照使批次可复现 (铁律 3)。保留策略 (路A): 血缘关系边
    永久留存于 clusters 表血缘字段; 每日全量重批记录只留最近 15 个自然日,
    过期清理。审计视图口径 (决策⑥) 归 M1-029 实现。"""
    lineage_id: str
    day: date
    events: list[LineageEvent]
    dormant_cluster_ids: list[str]
    drift_audits: list[CentroidDriftAudit]
    tau_match: float
    tau_link: float
    dormant_after_days: int
    generated_at: datetime


# ═════════════════════ 入口与主题 [D1-a][C1][C2]

OriginKind = Literal["combo", "idea", "domain", "competitor", "document"]


@dataclass
class Origin:
    """Combo 降级为 Origin 的一种实现。payload 按 kind 约定:
    combo:      {card_ids, hypothesis}   # 关联假设仅此路径必填
    idea:       {text}
    domain:     {category_id | text}
    competitor: {name, url}
    document:   {file_ref}
    主题数量: combo 5~8; 其余 1~3 (n<2 时差异约束豁免)。
    """
    origin_id: str
    kind: OriginKind
    owner: Principal
    payload: JSON
    created_at: datetime


@dataclass
class TopicSeed:
    seed_id: str
    origin_id: str
    keywords: list[str]
    hypothesis: str | None           # combo 必填, 其余可空
    context_text: str


@dataclass
class WhyNowEvidence:
    event: str
    event_date: date
    citation_id: str


@dataclass
class WhyNow:
    claim: str
    evidences: list[WhyNowEvidence]
    speculative: bool                # evidences 为空 → True [C2]


@dataclass
class Topic:
    topic_id: str
    seed_id: str
    one_liner: str
    target_user_tag: str             # 差异约束维度一 [C1]
    form_factor_tag: str             # 差异约束维度二
    why_now: WhyNow
    keyword_mapping: JSON
    embedding: Vector


# ═════════════════════ 证据、引用与定价 [B4][B5][审5][审7]

EvidenceOrigin = Literal["retrieved", "user_provided"]
EvidenceAccess = Literal["public", "private"]
DocKind = Literal["paper", "patent", "news", "product", "repo", "webpage", "user_upload"]


@dataclass
class Doc:
    """PDD 中称 Evidence。access="private"(用户材料): 产品内可点开原文段落;
    导出/分享强制标注「引自用户提供材料, 外部不可核验」, 链接不外链 [审5]。"""
    doc_id: str
    source_id: str
    kind: DocKind
    title: str
    url: str
    published_at: date | None
    meta: JSON
    origin: EvidenceOrigin           # [D2][审7] 双尺评分的判别字段
    access: EvidenceAccess           # [审5]


@dataclass
class Citation:
    citation_id: str
    doc_id: str
    locator: str | None              # 页码 / 段落
    quote_span: str | None


@dataclass
class EvidenceScore:
    """双尺 [审7]: retrieved 用 B4 学术/新闻/专利公式;
    user_provided 用 40·可核验性 + 35·一手性 + 25·时效。
    UI 分区展示、区内排序, 跨类不比较分数。"""
    strength: int                    # 0~100; 权重初值入 Open Questions
    axis: EvidenceOrigin
    components: JSON


@dataclass
class PricingRecord:
    plan: str
    price: float | None
    currency: str
    region: str
    confidence: float                # 低置信 → 前端「定价待确认」[B5]
    captured_at: datetime
    url: str


@dataclass
class Query:
    text: str
    source_kinds: list[DocKind]
    intent: Literal["support", "refute", "landscape"]
    locale: str


@dataclass
class TrendItem:
    keyword: str
    score: float
    region: str
    url: str
    captured_at: datetime


# ═════════════════════ Claim / Fact / Ledger [D1-b][v0.3.2 §1]

Alignment = Literal["pending", "supports", "partial", "unsupported"]
# speculative 不是对齐结果, 是 Claim.confidence (v0.3.2); 未过对齐 → 去引用并降 confidence。


@dataclass
class Claim:
    """Deliverable 内生成的一句结论。作用域 = 本 Deliverable, 变更不跨文档传播
    (重生成即处理), 因此 diff/stale 机制不覆盖 Claim (v0.3.2 §1)。"""
    claim_id: str
    deliverable_id: str
    block_id: str
    text_span: str
    confidence: Literal["cited", "speculative"]
    citation_ids: list[str]
    alignment: Alignment
    promoted_fact_id: str | None = None   # 提升后回填


DerivationReason = Literal["initial", "inject_evidence", "dispute", "revalidation"]
FactStatus = Literal["frozen", "disputed", "retired"]
# retired = fact 被移除 → 引用它的 block 标 needs_review(fact_removed, blocking) [审11]


@dataclass
class Fact:
    """跨 Deliverable 引用的唯一载体; 全系统被钉住次数最多的对象 (v0.3.2 §1)。
    提升不变量: origin="promoted_claim" 必须来自 confidence=="cited"
    且 alignment=="supports"(第二段通过) 的 claim; partial 不可提升。
    disputed 在后续生成中排除 [D2][审10]。"""
    fact_id: str                     # 跨版本稳定
    statement: str
    value: str | float | None
    unit: str | None
    citation_ids: list[str]
    status: FactStatus
    origin: Literal["promoted_claim", "injected"]
    created_in_version: int
    source_claim_id: str | None = None    # promoted_claim 时必填
    promoted_from: str | None = None      # 来源 deliverable_id


@dataclass
class FactsLedger:
    """不可变。inject_evidence / dispute / revalidation 派生新版本, 旧版永存;
    下游 Deliverable 经 ledger_version 判 stale。并发经 LedgerStore.derive 乐观锁 [审4]。"""
    ledger_id: str
    project_id: str
    version: int
    parent_version: int | None
    derivation_reason: DerivationReason
    facts: list[Fact]
    created_from: list[str]          # deliverable_ids
    created_at: datetime
    actor: str                       # 派生发起方: user_id / job_id [审4]


@dataclass
class FactDiff:
    """changed_fact_ids = diff(v_new, v_pinned); 只有引用变更 fact 的 block 标 needs_review。
    映射: changed→fact_changed(advisory), removed(retired)→fact_removed(blocking),
    disputed→fact_disputed(advisory) [审11]。"""
    changed: list[str]
    removed: list[str]
    disputed: list[str]


class LedgerVersionConflict(Exception):
    """derive 版本不匹配时抛出, 携带当前状态。冲突处置按来源分派 [审4]:
    inject_evidence → 自动重放(≤3); dispute → 提示用户重新提交;
    revalidation → 整个 job 失效重跑。"""

    def __init__(self, current_version: int, current_facts: list[Fact]) -> None: ...


# ═════════════════════ Deliverable / Block [D3][D6][D12][审3][审8][审9][审11]

DeliverableType = Literal["analysis", "report", "proposal", "vibe_pack", "spec", "chart", "revalidation_report"]
# vibe_pack (v0.3.3): audience=ai_executor 时计划书+spec 合并为单一 AI 执行包
StaleReason = Literal["ledger_changed", "world_changed"]


@dataclass
class Staleness:
    reason: StaleReason
    detail: str
    detected_at: datetime
    revalidation_report_id: str | None


@dataclass
class Deliverable:
    deliverable_id: str
    project_id: str
    type: DeliverableType
    version: int                     # 语义 = 钉住的 ledger 版本 + 各 block revision 组合 [D1-b]
    supersedes: str | None
    inputs: list[str]                # 前置 deliverable_ids
    ledger_version: int | None
    generation_record_id: str
    stale_reasons: list[Staleness]   # 多来源并存, UI 一条横幅列全部 (v0.3 §1.4)
    created_at: datetime
    reproducible: bool = True        # redaction 后置 False [审9]


# —— Block.content 判别联合 (审16: 冻结件不留裸 dict) ——

@dataclass
class TextSpan:
    kind: Literal["text"]
    text: str


@dataclass
class ClaimSpan:
    kind: Literal["claim"]
    claim_id: str
    text: str
    disputed_mark: bool = False      # ⚠ + hover 显示 dispute 原因 [审10]


@dataclass
class CitationMark:
    kind: Literal["cite"]
    citation_id: str


@dataclass
class ProfileRef:
    """涉我内容的类型化出处通道 (v0.3.2 §1): 只允许引用 Profile 条目, 缺则留白。"""
    kind: Literal["profile"]
    field_path: str                  # 如 "research.publications[2]"


InlineSpan = TextSpan | ClaimSpan | CitationMark | ProfileRef


@dataclass
class HeadingContent:
    kind: Literal["heading"]
    level: int
    text: str


@dataclass
class ParagraphContent:
    kind: Literal["paragraph"]
    spans: list[InlineSpan]


@dataclass
class TextCell:
    kind: Literal["text"]
    text: str


@dataclass
class FactCell:
    kind: Literal["fact"]
    fact_id: str


@dataclass
class PriceCell:
    """预算数字的类型化出处通道 (v0.2 §6.5): 每格引用 entry_id, 可审计。"""
    kind: Literal["price"]
    price_entry_id: str
    quantity: float


TableCell = TextCell | FactCell | PriceCell


@dataclass
class TableContent:
    kind: Literal["table"]
    header: list[str]
    rows: list[list[TableCell]]


@dataclass
class ChartContent:
    kind: Literal["chart"]
    chart_id: str                    # → ChartSpec (derived_from 铁律)


@dataclass
class DeclarationContent:
    """决策边界声明 [D12]: 模板注入、不可编辑删除, 钉在质量卡上方。"""
    kind: Literal["declaration"]
    text: str


@dataclass
class QualityCardContent:
    kind: Literal["quality_card"]
    card_ref: str                    # → QualityCard


@dataclass
class CitationListContent:
    kind: Literal["citation_list"]
    citation_ids: list[str]


@dataclass
class GapNoticeContent:
    kind: Literal["gap_notice"]
    hints_ref: str                   # → SectionState.gap_hints


BlockContent = (
    HeadingContent | ParagraphContent | TableContent | ChartContent
    | DeclarationContent | QualityCardContent | CitationListContent | GapNoticeContent
)

BlockType = Literal[
    "heading", "paragraph", "table", "chart",
    "declaration", "quality_card", "citation_list", "gap_notice",
]

ReviewReason = Literal["fact_changed", "fact_removed", "fact_disputed"]
ReviewSeverity = Literal["blocking", "advisory"]
# fact_removed=blocking: 导出/分享/终稿前必须处理(重生成/删除/确认保留标 speculative),
# 未处理导出被拒; 其余 advisory 黄标折叠 [审11]。


@dataclass
class Block:
    """结构化 block 树为唯一真相; md/pdf/docx/html 均为渲染目标, 不回写 [D3]。
    保护条件 (v0.3.2): locked 或 author=="user" 或 user_modified 的 block,
    regenerate / shrink / expand 一律不得改写。
    指标口径: 质量卡覆盖率/对齐率只统计 author=="system" 且未被用户修改的 block [审3]。"""
    block_id: str
    deliverable_id: str
    section_id: str
    order: int
    type: BlockType
    content: BlockContent            # 判别联合 [审16]
    claim_ids: list[str]             # 本 Deliverable 内结论
    fact_ids: list[str]              # 跨 Deliverable 冻结引用 (v0.3.2 §1)
    author: Literal["system", "user"]     # 创建者, 永不翻转 (v0.3.2)
    revision: int
    locked: bool                     # [D2] 系统块(declaration 等)恒 True
    user_modified: bool = False      # 用户编辑过 system block → True (v0.3.2)
    needs_review: bool = False       # [审3]
    review_reason: ReviewReason | None = None
    review_severity: ReviewSeverity | None = None


# ═════════════════════ 章节与模板 [D13][D3 铁律][审8]

@dataclass
class GapHint:
    """expand 拒绝注水的出口 [D13]。missing_permission 绝不伪装成缺资料 [审8]:
    missing_data → 「补充以下任一即可」+ 一键注入;
    missing_permission → 「需 {required_scope}, 你当前无权访问」→ 请 owner 授权。"""
    missing_what: str
    cause: Literal["missing_data", "missing_permission"]
    suggested_sources: list[str]     # cause=missing_data 时有效
    action: Literal["search", "ask_user", "upload", "request_permission"]
    target_count: int | None = None
    required_scope: str | None = None     # cause=missing_permission 时: 所需字段组


@dataclass
class ChartSpec:
    chart_id: str
    chart_type: str
    derived_from: list[str]          # deliverable_id | fact_ids, 必填不许编


@dataclass
class Ratio:
    share: float
    min_words: int
    max_words: int
    unit: Literal["words", "tokens"] = "words"   # v0.3.3: vibe_pack 用 tokens, min/max 按 token 计


@dataclass
class SectionSpec:
    section_id: str
    inputs: list[str]
    check_questions: list[str]
    charts: list[ChartSpec]


@dataclass
class SectionState:
    section_id: str
    deliverable_id: str
    locked: bool                     # [D2] 章节级锁定
    gap_hints: list[GapHint]         # [D13][审8]
    check_results: JSON              # check questions 逐条自检结果


@dataclass
class TemplateSpec:
    template_id: str                 # generic/thesis/startup/engineering/grant | vibe_pack
    locale: str                      # 规则表按 locale 分别维护, 非翻译
    sections: list[tuple[str, Ratio]]
    audience: Literal["human_reader", "ai_executor"] = "human_reader"  # v0.3.3
    # audience="ai_executor" → 固定章节族 S1~S9 (Charter/Invariants/Contracts/
    # DecisionLog/TaskDAG/ContextManifest/VerifyHarness/ProgressLedger/Escalation)
    # + Human Digest 附件(不进 AI 上下文); Ratio.unit=tokens。


# ═════════════════════ 干预层 [D2][审10]

@dataclass
class UserEvidence:
    evidence_id: str
    owner: Principal
    kind: Literal["file", "url", "text"]
    content_ref: str
    note: str
    created_at: datetime


@dataclass
class Dispute:
    """接受 → fact 标 disputed → 新生成排除该 fact、既有引用 block 标 advisory [审10];
    解决 → 派生新 ledger 版本, 清除 disputed 与相关 review。"""
    dispute_id: str
    deliverable_id: str
    target_kind: Literal["block", "fact", "citation"]
    target_id: str
    reason_text: str
    status: Literal["open", "resolved_kept", "resolved_replaced"]
    created_by: str
    created_at: datetime


# ═════════════════════ 可行性判定 [D7][审1][审2]

Verdict = Literal["A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"]

StrengthSignal = Literal[
    "funded_or_scaled", "mature_pricing", "same_target_user", "active_last_12m",
]


@dataclass
class Competitor:
    """strong = 满足任二 signal; 信号不足 → unknown (不是 weak) [审1]。
    定价允许「待确认」, 但强度判定不接受待确认——只是丢一个 signal。
    unknown 阻断 C 是刻意保守: 判错 C 代价大于判错 A/D。"""
    name: str
    url: str
    strength: Literal["strong", "moderate", "weak", "unknown"]
    strength_signals: list[StrengthSignal]
    pricing: PricingRecord | None


@dataclass
class VerdictResult:
    """判定顺序写死 A > B > C > D [审2]; all_satisfied 记录全部命中档位,
    展示最高优先者, 用户可展开「同时命中 B」。
    硬规则 (任一不满足 → 按顺序落到下一档):
    A: ≥1 条 stage="verdict" 对齐通过的证伪证据
       (默认须 origin="retrieved"; user_provided 需用户显式确认,
        开关记入 GenerationRecord.user_evidence_verdict_optin)
    B: (≥3 个竞品记录、各有可达来源) 或 (≥1 个 strength="strong" 竞品) [审1]
    C: refute 检索已执行且 hit_rate ≥ θ_rel
       + 竞品覆盖达标 (≥2 源查询且 Top 结果全部解析)
       + ≥1 条对齐通过的支持证据
       + 无 strength ∈ {strong, unknown} 的竞品 [审1]
    D: 兜底; 必须输出缺口清单 + GapHint
    """
    verdict: Verdict
    all_satisfied: list[Verdict]     # [审2]
    key_citation_ids: list[str]
    rationale_fact_ids: list[str]
    competitors: list[Competitor]    # [审1]
    constraints_checked: JSON


@dataclass
class AnalysisContext:
    project_id: str
    budget_cny: float                # 超限走 B7 降级阶梯, 逐级记入质量卡
    locale: str


Audience = Literal["human_reader", "ai_executor"]


@dataclass
class ProposalContext:
    """计划书生成启动参数 (v0.3.3)。audience 为必选分叉, UI 在报告→计划书之间强制单选:
    human_reader → 五模板计划书 (现有流程, 后接 spec_export);
    ai_executor  → vibe_pack (计划书+spec 合并为单一 AI 执行包)。
    生成后可再生成另一受众版本, 钉同一 ledger 版本, 两版互链, 不做同文档混排。"""
    project_id: str
    report_id: str
    template_id: str
    profile_id: str | None
    audience: Audience
    budget_cny: float
    locale: str


# ═════════════════════ 作业模型 [D4][D8][审6][审16]

JobKind = Literal["gate1_analysis", "report", "proposal", "spec_export",
                  "revalidation", "daily_ingest", "pricebook_scan"]
JobState = Literal["queued", "retrieving", "judging", "drafting",
                   "validating", "done", "failed", "cancelled"]


# —— checkpoint 判别联合 (审16): JobStep.snapshot_ref 指向其序列化 ——

@dataclass
class AnalysisCheckpoint:
    kind: Literal["gate1_analysis"]
    executed_query_ids: list[str]
    phase: Literal["retrieve", "judge", "validate"]
    draft_claim_ids: list[str]


@dataclass
class DraftCheckpoint:
    kind: Literal["draft"]           # report / proposal 共用
    completed_section_ids: list[str]
    ledger_version: int


@dataclass
class IngestCheckpoint:
    kind: Literal["daily_ingest"]
    day: date
    sources_done: list[str]


@dataclass
class RevalidationCheckpoint:
    kind: Literal["revalidation"]
    target_deliverable_id: str
    checked_sources: list[str]


@dataclass
class PricebookScanCheckpoint:
    kind: Literal["pricebook_scan"]
    scanned_until_entry: str | None


@dataclass
class SpecExportCheckpoint:
    kind: Literal["spec_export"]
    validated_packages: list[str]
    task_ids_done: list[str]


JobCheckpoint = (
    AnalysisCheckpoint | DraftCheckpoint | IngestCheckpoint
    | RevalidationCheckpoint | PricebookScanCheckpoint | SpecExportCheckpoint
)


@dataclass
class JobStep:
    name: str
    state: JobState
    started_at: datetime | None
    ended_at: datetime | None
    cost: float
    snapshot_ref: str | None         # 断点续跑检查点: 序列化的 JobCheckpoint [审16]


@dataclass
class Job:
    """权限 [审6]: 取消权 = initiated_by 本人或 owner_scope 内 role∈{owner,admin};
    SSE 订阅 = 同上 + member 只读; 系统级 job (daily_ingest/pricebook_scan)
    owner_scope = 系统租户, 仅管理员可见。"""
    job_id: str
    kind: JobKind
    project_id: str | None
    owner_scope: Principal           # 与根资源一致, 继承自 Project [审6]
    state: JobState
    steps: list[JobStep]
    progress: float
    partial_output_ref: str | None   # 服务端持久化 [D8]
    budget: float
    cost_accum: float
    cancel_requested: bool           # 阶段边界生效
    error: str | None
    initiated_by: str                # user_id [审6]
    created_at: datetime
    updated_at: datetime


# —— JobEvent.payload 判别联合 (审16 同源要求) ——

@dataclass
class StatusChanged:
    kind: Literal["status"]
    state: JobState


@dataclass
class StepEvent:
    kind: Literal["step"]
    step_name: str
    phase: Literal["start", "end"]
    cost: float | None


@dataclass
class PartialBlockEvent:
    kind: Literal["partial_block"]
    block_id: str


@dataclass
class JobFailedEvent:
    kind: Literal["failed"]
    reason: str


JobEventPayload = StatusChanged | StepEvent | PartialBlockEvent | JobFailedEvent


@dataclass
class JobEvent:
    job_id: str
    seq: int                         # 单调递增, SSE Last-Event-ID 补发依据 [D8]
    ts: datetime
    payload: JobEventPayload


# ═════════════════════ 复核 [D6][v0.3.2 §2.2]

RevalidationTrigger = Literal["scheduled", "user", "event"]


@dataclass
class VerdictShift:
    """v0.3.2: rerun_analysis_id 必填——没有完整重跑 §2.2 规则表产出的新 Analysis,
    就不存在 verdict_shift。系统内只有一套判定逻辑, 不做启发式偏移。"""
    old: Verdict
    new: Verdict
    rerun_analysis_id: str


@dataclass
class RevalidationReport:
    """只做检测, 不直接改状态; 用户接受 → ledger 派生(reason=revalidation)
    → 下游走 D1-b 的同一 stale 机制。"""
    report_id: str
    deliverable_id: str
    new_papers: list[str]
    new_competitors: list[str]
    heat_shift: JSON
    verdict_shift: VerdictShift | None    # 必经完整重跑 (v0.3.2)
    trigger: RevalidationTrigger
    generated_at: datetime
    accepted: bool | None


# ═════════════════════ UserProfile [D10]

Sensitivity = Literal["team", "owner_only"]   # v0.3.1 §1.8 冻结两级

DEFAULT_PROFILE_SENSITIVITY: dict[str, Sensitivity] = {
    "constraints.budget_range": "owner_only",
    "*": "team",
}


@dataclass
class UserProfile:
    profile_id: str
    owner: Principal
    identity: JSON                   # 姓名/机构/角色
    research: JSON                   # 论文(ORCID/DOI)、方向、项目经历
    team: list[JSON]
    assets: JSON                     # 设备/算力/数据集
    constraints: JSON                # 预算区间、可投入时间、期限
    track_record: list[JSON]
    locale: str
    sensitivity_overrides: dict[str, Sensitivity]  # 键=字段路径
    updated_at: datetime


# ═════════════════════ PriceBook [D11]

@dataclass
class PriceEntry:
    entry_id: str
    item: str
    unit: str
    price_low: float
    price_high: float
    currency: str
    region: str
    year: int
    source: str                      # url / citation / "user_override"; 无出处不可被引用
    updated_at: datetime
    stale_after_months: int = 12     # 过期仍可用: 质量卡标注 + GapHint 提示刷新 (v0.3.1 §3.2)


# ═════════════════════ 质量与可复现 [F2][F3][F4][审9]

@dataclass
class RedactionRecord:
    """铁律三的唯一例外留痕 [审9]: 「发生过删除」永久可查。"""
    deliverable_id: str
    redacted_at: datetime
    scope: str
    actor: str


@dataclass
class GenerationRecord:
    record_id: str
    deliverable_id: str
    job_id: str
    prompt_version: str
    model: str
    params: JSON
    retrieval_snapshot_id: str
    ledger_version: int | None
    pricebook_version: str | None
    user_evidence_verdict_optin: bool  # [D2] 自供证据参与判 A 的显式确认
    ts: datetime
    cost: float
    alignment_rate: float | None = None       # draft 段红线 ≥0.95 (v0.2 §4.4)
    structured_output_failures: int = 0       # [D9] 全部失败记录在案


EditAction = Literal["delete_claim", "edit_text", "remove_citation", "reorder",
                     "choose_topic", "lock", "dispute"]


@dataclass
class EditEvent:
    """F3 数据资产: 主动行为 > 关联假设。edit_text 命中 system block → user_modified=True。"""
    event_id: str
    deliverable_id: str
    section_id: str | None
    block_id: str | None
    action: EditAction
    before: JSON | None
    after: JSON | None
    user_id: str
    ts: datetime


@dataclass
class QualityCard:
    evidence_count: int
    evidence_age_median_days: int
    citation_coverage: float         # 只统计 author=="system" 且未改的 block [审3]
    alignment_rate: float            # 红线 ≥0.95 (draft 段)
    degradations: list[str]          # B7 降级记录, 对用户可见
    user_supplied_evidence_count: int
    private_evidence_ratio: float    # [审5] private 占比高 → 外部说服力本质不同
    disputed_facts: int              # [审10] 「争议中的依据: N 条」
    blocking_reviews_open: int       # [审11] >0 → 导出被拒
    price_data_notes: list[str]      # [D11]「单价数据为 YYYY 年」
    blind_spots: list[str]           # 盲区声明
    reproducible: bool               # [审9] False → 「含已删除的个人数据, 不可完整复现」


# ═════════════════════ 项目容器

@dataclass
class Project:
    project_id: str
    owner: Principal
    origin_id: str
    topic_ids: list[str]
    chosen_topic_id: str | None
    deliverable_ids: list[str]
    change_log: list[JSON]           # E4 回写偏差落此处
    status: str
    created_at: datetime


# ═════════════════════ 任务分解 [T1][T2]

@dataclass
class TaskSpec:
    """双受众双单位 (v0.3.3, 字段顺序有调整——milestone 前移至默认值区之前):
    human_reader → estimate_days 必填 (≤0.5);
    ai_executor  → estimate_cycles 必填 (≤2, 超则拆; 目标 1 = oneshot)
                   且 verify_cmd 必填——无机检验收的任务不允许存在 [E3 升级]。
    互斥必填由 DagValidator 校验。
    cycle := 一次 装载→执行→验证→落盘 闭环 (衡量上下文寿命, 非日历时间)。"""
    task_id: str
    title: str
    inputs: list[str]                # 须为前置任务 outputs 或外部既有物
    outputs: list[str]               # artifact
    acceptance: list[str]            # 须可转测试断言 [E3]
    depends_on: list[str]
    milestone: str
    estimate_days: float | None = None      # 人类路径, ≤ 0.5
    estimate_cycles: float | None = None    # AI 路径, ≤ 2 (v0.3.3)
    oneshot: bool | None = None             # 预估单 cycle 可完成
    verify_cmd: str | None = None           # exit 0 = 验收通过
    context_refs: list[str] | None = None   # 执行时装载的 vibe_pack 单元 ID (S6)
    review_gate: bool | None = None         # ai 路径: true=须过审核 agent 才解锁下游 (v0.3.3)


@dataclass
class PackageStatus:
    package: str
    ecosystem: Literal["pypi", "npm", "crates"]
    exists: bool
    latest_stable: str | None
    replaced_with: str | None
    reason: str | None


@dataclass
class DagReport:
    acyclic: bool
    orphans: list[str]
    unreachable: list[str]
    errors: list[str]


@dataclass
class Completion:
    text: str
    tool_calls: list[JSON]
    usage: JSON
