"""燧石 Flint · 领域模型冻结件 (M0, 执行顺序 ③)

纯类型定义, 无实现。Python >= 3.11。
覆盖: PDD v0.1~v0.3.2 + M0 决策记录 (D1~D13) + 审核 1~11 (v0.3.1 附录 C) + 终轮补丁 (v0.3.2)。
本文件是 v0.3.3 冻结件 contracts/models.py 的 **v0.4 工作副本**(SCHEMA-00 产出)。
冻结规则 (v0.3.3 口径): 改动只能来自 ⑧ 对抗性推演产出的 v0.4 修订 ∨ owner 变更; 纸面评审轮次已停止。
相对冻结件**只加不删**, 由 tools/check_frozen_additive.py 逐符号断言; 原 contracts/ 只读零触碰。
v0.4 增量块以「v0.4 纯新增」注释标出, 落点依据 docs/schema_reconcile_prefill_v04.md。
[D*] 对应 M0 决策记录; [B*][C*][A*] 对应 PDD v0.2; [审N] 对应 v0.3.1 审核意见。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

Vector = list[float]
JSON = dict[str, Any]

# ═════════════════════ v0.4 增量 · I1 四枚举 [PRINCIPLES#A3]

Region = Literal["CN", "HK", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"]
"""十地区, 无 EU (清单 A2 九区 + `DEC-056` 增 HK)。决定数据源选集与热点集合, 与语言正交 [PRINCIPLES#A3]。

`DEC-056`(owner 2026-08-10) 判 CN 与 HK 两区分家、各自一源 (CN=微博, HK=Google 趋势),
两区都可切。而 HK **原本不在清单 A2 的九区里**——本别名因此从九个成员加到十个。

这一改是**加成员, 不是改口径**: `tools/check_frozen_additive.py` 对 Literal 别名
按「成员集合 base ⊆ v04」比, 加成员明确允许; 且 `Region` 本身是 v0.4 纯新增,
原冻结件 `contracts/models.py` 里没有它——原件一个字都没被碰。
「无 EU」那一条照旧: EU 是区域联盟不是地区, 混进来源选集口径会塌。
"""

SystemLanguage = Literal["zh", "en"]
"""系统语言, 仅此两种, zh 默认 (A1)。统治全站 UI 与生成内容语言 [PRINCIPLES#A3]。"""

AuthorityTier = Literal["official", "mainstream", "industry", "community", "unknown"]
"""四级权威度 + unknown 缺省态。unknown 证据 NEVER 满足判 A/B 必要条件 (REGION-03 前置门)。"""

FetchLegalStatus = Literal["allowed", "unknown", "restricted"]
"""抓取合规状态 (B11), 默认 unknown; restricted 拒绝抓取任务 (REGION-07)。各国合规结论待 K2。"""

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
    # —— v0.4 纯新增 · I4 名称三元组 [PRINCIPLES#B7/#B8] ——
    name_native: str                 # 原文名, 唯一权威; NEVER 翻译/改写 [PRINCIPLES#B7]
    name_lang: str                   # name_native 的语言标记 (来源语言, 非 SystemLanguage)
    name_display: dict[SystemLanguage, TranslatedText] | None
    # canonical_name 保留: 与 name_native 的关系由 REGION-04 命名规则成文

    def __setattr__(self, name: str, value: object) -> None:
        """name_native **写一次即定**: 构造可写, 二次赋值拒绝 [PRINCIPLES#B7]。

        真件 Cluster 是非 frozen dataclass (预填表注记 2), 把整个类改 frozen 会改变
        既有字段的可变性语义——越界。这里只钉 name_native 这一个字段, 其余字段照常可变。

        要防的不是「有人手动改名」, 而是**入库时顺手归一化**: 全角转半角、去空白、
        大小写折叠、Unicode NFC/NFKC。这些都「看起来没改内容」, 但 embedding 与去重
        吃的是字节——一次归一化就让同一个热点在两天里变成两个簇。
        """
        if name == "name_native" and name in self.__dict__:
            raise AttributeError(
                "Cluster.name_native 写一次即定, NEVER 改写 [PRINCIPLES#B7]: "
                f"已有 {self.__dict__[name]!r}, 拒绝改成 {value!r}")
        object.__setattr__(self, name, value)


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
    # —— v0.4 纯新增 · I6 [PRINCIPLES#B9] ——
    # event 原文字段保持不动; 译文只进派生槽。event_date 是 date, 无原文文本,
    # 本地化在渲染层 → NEVER 设 display 槽 (预填表收敛)。
    event_display: dict[SystemLanguage, TranslatedText] | None

    def __setattr__(self, name: str, value: object) -> None:
        """原文槽 NEVER 被翻译写入 [PRINCIPLES#B9/#B10]。

        要防的不是「有人故意写错」, 而是 ingest 管线里一句
        `evidence.event = translated_text`: 标注是 str, TranslatedText 不是 str,
        但 Python 运行期不拦; 一旦写进去, B10 的接地比对就会拿译文去比原文,
        「引真卡 + 编假证据」那个洞就从另一头被打开了。
        译文只进 *_display 派生槽。
        """
        if name == "event" and isinstance(value, TranslatedText):
            raise TypeError(
                "WhyNowEvidence.event 是原文槽, NEVER 写入译文 [PRINCIPLES#B9]: "
                "译文只进 event_display 派生槽")
        object.__setattr__(self, name, value)


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

# DOC-01: 正文进库的字节上限 (owner 2026-08-04 由 256 KB 加码到 2 MB, 约 70 万汉字)。
# 写成常量而不是散在各处的字面量: 上限只有一处真相, 改一次全仓跟着改。
# 判据 tests/v041/test_doc_content_contract.py 钉着它的值与用法。
DOC_CONTENT_MAX_BYTES = 2 * 1024 * 1024


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
    # —— v0.4 纯新增 · I2 溯源增量 (落点由预填表核实修正: Origin → Doc) ——
    region: Region | None            # 该文档所属地区; None = 未归区。NEVER 给默认值:
                                     # 归区是采集期的事实, 不该由缺省顶替
    source_country: str | None       # 源所在国 (ISO 3166-1 alpha-2), 与 region 可不同
    # 下面两项的缺省态是产品语义, MUST 写成 dataclass 默认值:
    #   unknown 权威度 NEVER 满足判 A/B 的必要条件 (REGION-03 前置门);
    #   unknown 合规状态 NEVER 被当作「可抓」(REGION-07)。
    # 写在文档里而不写进默认值, 等于把这条语义交给每个构造点各自记得。
    authority_tier: AuthorityTier = "unknown"
    fetch_legal_status: FetchLegalStatus = "unknown"
    # —— v0.4.1 纯新增 · DOC-01 证据补厚 (owner 2026-08-04 裁决: 方案 A) ——
    #
    # 此前 Doc 只有 title + url: 证据卡因此只能引到标题与链接, 引不到正文里的
    # 任何一句话。三个字段把正文本身收进来:
    #
    #   content          正文**进库**。None = 还没提取 (不是「这篇没有正文」);
    #                    两者要分得开, 否则重跑提取时无从判断该跳过谁。
    #   content_sha256   **原文**的 sha256 (截断前那一份)。两个用途:
    #                    ① 验证——库里这份还是不是当初抓到的那份;
    #                    ② 去重——同一篇文章多源抓到只存一份 (DOC-02)。
    #                    截断后再算哈希的话, 上面两件事都会失灵:
    #                    同一篇文章因截断位置不同而算出两个哈希。
    #   content_truncated 正文被截断过。上限 DOC_CONTENT_MAX_BYTES = 2 MB
    #                    (约 70 万汉字, 一部《红楼梦》的量级; owner 2026-08-04
    #                    由 256 KB 加码)。**截断 MUST 如实标记**: 下游据此
    #                    知道自己拿到的不是全文, NEVER 让它以为是。
    #   source_file_ref  PDF 一类**原件**的存放位置 (对象存储 key / 相对路径)。
    #                    **正文进库、原件进文件**, 两条路各归各的: 正文要能被
    #                    检索与引用, 原件要能被逐页翻。把 PDF 二进制塞进 content
    #                    既检索不了也引用不了。
    #
    # 四个都带默认值: 既有构造点一处不用改, 增量不破坏 (SCHEMA-00 additive 通道)。
    content: str | None = None
    content_sha256: str | None = None
    content_truncated: bool = False
    source_file_ref: str | None = None


@dataclass
class Citation:
    citation_id: str
    doc_id: str
    locator: str | None              # 页码 / 段落
    quote_span: str | None
    # —— v0.4 纯新增 · I6 [PRINCIPLES#B9/#B10] ——
    # quote_span 原文保持不动; 接地比对只对原文, 译文 NEVER 参与 (grounding_spec_v04)。
    quote_span_display: dict[SystemLanguage, TranslatedText] | None

    def __setattr__(self, name: str, value: object) -> None:
        """原文槽 NEVER 被翻译写入 [PRINCIPLES#B9/#B10]。

        要防的不是「有人故意写错」, 而是 ingest 管线里一句
        `evidence.quote_span = translated_text`: 标注是 str, TranslatedText 不是 str,
        但 Python 运行期不拦; 一旦写进去, B10 的接地比对就会拿译文去比原文,
        「引真卡 + 编假证据」那个洞就从另一头被打开了。
        译文只进 *_display 派生槽。
        """
        if name == "quote_span" and isinstance(value, TranslatedText):
            raise TypeError(
                "Citation.quote_span 是原文槽, NEVER 写入译文 [PRINCIPLES#B9]: "
                "译文只进 quote_span_display 派生槽")
        object.__setattr__(self, name, value)


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
    # —— v0.4 纯新增 · I7 产物语言 ——
    lang: SystemLanguage = "zh"      # 不变量: 同一 Deliverable 内所有 Block.lang 与之一致 (I12)


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
    # —— v0.4 纯新增 · I7 产物语言 ——
    lang: SystemLanguage = "zh"      # 与所属 Deliverable.lang 一致 (I12 不变量)
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
    locale: str                      # v0.4 起由 lang 派生填充, 保留兼容
    # —— v0.4 纯新增 · I13 [PRINCIPLES#A3] ——
    # lang/region 为权威, 两值正交: 切 region NEVER 改语言, 切 lang NEVER 改热点集合。
    lang: SystemLanguage
    region: Region


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
                  "revalidation", "daily_ingest", "pricebook_scan",
                  # —— v0.4 纯新增: 三种新作业, 注册进既有 runner (§6-H7), NEVER 新写 runner ——
                  "translate", "design_generate", "template_solidify"]
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




# —— v0.4 纯新增 · JobEventPayload 七个判别成员 (§6-H4: 复用同一 SSE 通道) ——


@dataclass
class DesignDelta:
    """设计台流式增量块。

    基线: delta **入 replay**——不入的话断线重连只能拿到残缺的一半,
    SSE 的 Last-Event-ID 补发机制拿不到没存的东西。seq 是补发的定位依据。
    """
    kind: Literal["design_delta"]
    seq: int
    fragment: str
    # —— §9-P3 采纳位 (owner 已采纳, DEF-02) ——
    # P3 的 ephemeral 选项: delta 不落库、只走内存, 换取写入量下降,
    # 代价是断线重连拿不到已推送的片段。**位没有落在这里**, 落在 `JobEvent` 上:
    # 决定落不落库的是事件记录而不是载荷内容, 加在这里则 replay 过滤要认识
    # 11 个联合成员, 每新增一个成员都要回来改一次过滤逻辑。
    # 代价怎么还 → 见 `JobEvent.ephemeral` 与 `flint/design/session.py`。


@dataclass
class DesignToolCall:
    """设计台工具调用记录 (可复现)。"""
    kind: Literal["design_tool_call"]
    tool: str
    arguments: JSON


@dataclass
class DesignClarify:
    """设计台反问: 需求不足以生成时 NEVER 猜, 出澄清问题。"""
    kind: Literal["design_clarify"]
    question: str
    options: list[str]


DesignCheckState = Literal["passed", "failed", "unreported"]
"""设计台自检三态。

第三态不是凑数: `passed: bool` 只有过与不过, 「没跑过自检」被迫伪装成其中一个——
报 False 是冤枉 (没跑不等于不合格), 报 True 是撒谎。unreported 让「这次没自检」
能如实说出来, 前端才可能显示「未自检」而不是绿勾或红叉。
"""


@dataclass
class DesignCheck:
    """设计台自检结果 (可渲染性/可访问性)。"""
    kind: Literal["design_check"]
    state: DesignCheckState
    findings: list[str]


@dataclass
class TranslateProgress:
    """翻译作业进度。translator 版本变更即缓存失效 (E5)。"""
    kind: Literal["translate_progress"]
    done: int
    total: int
    translator: str


@dataclass
class SolidifyResult:
    """模板固化结果; 注册表不可用时阻断固化 (E6 新降级行)。"""
    kind: Literal["solidify_result"]
    template_id: str
    accepted: bool
    reason: str | None


@dataclass
class GraphStaleNotice:
    """图谱节点陈旧通知; stale 判定来自 Revalidator 统一口径 (§6-H1)。"""
    kind: Literal["graph_stale_notice"]
    node_ids: list[str]
    detected_at: datetime


JobEventPayload = (StatusChanged | StepEvent | PartialBlockEvent | JobFailedEvent
                   # —— v0.4 纯新增七成员 ——
                   | DesignDelta | DesignToolCall | DesignClarify | DesignCheck
                   | TranslateProgress | SolidifyResult | GraphStaleNotice)


@dataclass
class JobEvent:
    job_id: str
    seq: int                         # 单调递增, SSE Last-Event-ID 补发依据 [D8]
    ts: datetime
    payload: JobEventPayload
    # —— §9-P3 ephemeral 位 (owner 已采纳, DEF-02) ——
    # True = 只走内存, NEVER 落 replay 日志。位加在**事件**上而不是载荷上:
    # 决定落不落库的是事件记录, 加在载荷上则 replay 过滤要认识 11 个联合成员。
    # 代价在检查点上还: 检查点 MUST 盖住每一个 ephemeral 事件, 否则重连后
    # 的文字比不断线时短一截, 而短的那截没有任何错误信号。
    # 默认 False —— 既有构造点一个字不用改, 行为也一个字不变。
    ephemeral: bool = False


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


# ═════════════════════ v0.4 增量 · I12 不变量校验入口 (测试即规范)


GraphChangeKind = Literal[
    "node_added", "node_removed", "edge_added", "edge_removed", "node_moved"]


@dataclass
class GraphChange:
    """图谱变更事件 (I12-3 的入参)。"""
    kind: GraphChangeKind
    graph_id: str
    occurred_at: datetime


# 结构性变更才派生 stale。node_moved 不在其中: 画布上挪个位置没有改变任何论断,
# 把布局变动也算成 stale 会让「陈旧」这个信号迅速失去意义。
_STRUCTURAL_CHANGES: frozenset[str] = frozenset(
    {"node_added", "node_removed", "edge_added", "edge_removed"})


def set_primary(nodes: list[GraphNode], node_id: str) -> None:
    """把 node_id 设为该图的 primary, 前一个**自动降** secondary (I12-1)。

    自动降级而不是报错: 用户点第二个节点设主, 意思很明确;
    让他先去取消上一个, 是把系统的洁癖变成用户的负担。
    """
    if not any(n.node_id == node_id for n in nodes):
        raise ValueError(f"node {node_id} 不在这批节点里, 无从设为 primary")
    for node in nodes:
        node.primary = node.node_id == node_id


def derive_stale(change: GraphChange, deliverables_by_graph: dict[str, list[str]]) -> set[str]:
    """图变 → 该图关联的 Deliverable 集合 (I12-3)。**纯函数**: 只算不改。

    运行时接线走 §6-H1 (Revalidator 统一口径), 由 DESIGN-25 验;
    本函数只定派生规则, NEVER 自己去改任何对象的 stale 标记。
    """
    if change.kind not in _STRUCTURAL_CHANGES:
        return set()
    return set(deliverables_by_graph.get(change.graph_id, []))


def check_deliverable_language(
    deliverable: Deliverable, blocks: list[Block]
) -> None:
    """同一 Deliverable 内所有 Block.lang MUST 与 Deliverable.lang 一致 (I7/I12)。

    这条是**跨对象**不变量: Block.deliverable_id 只是个字符串, Block 拿不到它所属的
    Deliverable, 所以 dataclass 自己拦不住。散在各处「记得比一下」就等于没有——
    一份中英混排的产物, 读者看到半篇中文半篇英文, 而系统全程认为一切正常。

    落库前调用; SCHEMA-12 的三不变量套复用本入口, NEVER 另写一份。
    """
    for block in blocks:
        if block.deliverable_id != deliverable.deliverable_id:
            raise ValueError(
                f"block {block.block_id} 属于 {block.deliverable_id}, "
                f"不属于 {deliverable.deliverable_id}: 传错了对象, NEVER 当成语言不一致含糊过去")
        if block.lang != deliverable.lang:
            raise ValueError(
                f"block {block.block_id} 的 lang={block.lang!r} 与所属 Deliverable "
                f"{deliverable.deliverable_id} 的 lang={deliverable.lang!r} 不一致 (I12)")


# ═════════════════════ v0.4 增量 · 新增实体 (I3/I5/I8/I9/I10/I11)


@dataclass
class TranslatedText:
    """I5 译文派生槽。译文永远是派生物, 原文是权威 [PRINCIPLES#B8/#B9]。

    三条不变量各堵一个洞:
      · translated 恒 True —— 这个槽里放的东西没有一种情况是原文。允许 False
        就会有人把原文塞进 display 槽, B7「name_native 唯一权威」当场失效。
      · translator 非空 —— 译者/模型版本是缓存键的一部分 (E5: 内容 hash =
        原文字节 + 目标语言 + translator 版本)。空 translator 意味着旧译文
        能冒充新译者的产物。
      · source_field 非空 —— 不知道派生自谁, B10 的「可展开到原文」就无从实现。

    冻结件是「纯类型定义, 无实现」。这里破例写 __post_init__: 上面三条是构造期
    不变量, 只写在文档里就等于交给每个构造点各自记得——那正是它失效的方式。
    """
    text: str
    translated: Literal[True]        # 恒 True, 类型层钉死 [PRINCIPLES#B8]
    translator: str                  # 译者/模型标识 + 版本, 缓存键的一部分 (E5)
    source_field: str                # 派生自哪个原文字段, NEVER 留空

    def __post_init__(self) -> None:
        if self.translated is not True:
            raise ValueError("TranslatedText.translated 恒为 True: 该槽只放译文, 原文属 native 字段")
        if not self.translator.strip():
            raise ValueError("TranslatedText.translator NEVER 为空: 它是 E5 缓存键的一部分")
        if not self.source_field.strip():
            raise ValueError("TranslatedText.source_field NEVER 为空: 否则无从展开到原文 (B10)")


@dataclass
class SourceEntry:
    """I3 源注册表项。九区源清单待 K1 → 本轮空表种子, NEVER 编造。"""
    source_id: str
    region: Region
    country: str                     # ISO 3166-1 alpha-2
    name_native: str                 # 源名原文 [PRINCIPLES#B7]
    homepage: str
    authority_tier: AuthorityTier
    fetch_legal_status: FetchLegalStatus
    enabled: bool


@dataclass
class SourceRegistry:
    """I3 按地区分桶的源选集。检索排序 MAY 以 region_match 加权,
    过滤器 NEVER 按国别排除他国源 [PRINCIPLES#B4]。

    K1 未决期间本表为**空表种子**: 九区源清单与各国合规结论待 owner。
    空不等于坏——select() 对空表返回空集而 NEVER 抛错, 也 NEVER 回落到别的区:
    「该区没有源」与「取源失败」是两件事, 混起来会让上层把「今天没数据」误报成故障。
    """
    entries: list[SourceEntry]
    updated_at: datetime

    def select(self, region: Region) -> list[SourceEntry]:
        """该区**启用中**的源。空表 → 空集, NEVER 抛错、NEVER 跨区回落。"""
        return [e for e in self.entries if e.region == region and e.enabled]


GraphSourceKind = Literal["cluster", "evidence_card", "topic"]
"""节点只投影这三类既有实体 (§6-H8: source 引用既有实体 id 体系)。

「假设」不在此列——它是**边**上的 hypothesis: 假设描述的是两个东西之间的关系,
做成节点就会出现「一个没有两端的假设」, 那正是 combo 通道要求 hypothesis 必填的原因。
"""


@dataclass
class GraphNode:
    """I8 图谱节点 = 既有实体的投影, NEVER 是新造的东西 (§6-H8)。"""
    node_id: str
    graph_id: str
    source_kind: GraphSourceKind
    source_id: str                   # 指向 cluster_id / card_id / topic_id
    label: str
    position: tuple[float, float]
    created_at: datetime
    primary: bool = False            # 「这张图在讲哪件事」。图内计数恒 ≤1 (I12-1)


@dataclass
class GraphEdge:
    """I8 图谱边 = 关联假设。hypothesis 复用 combo 的校验语义 (§6-H8):
    非空必填, 空则服务端判 EMPTY_HYPOTHESIS。"""
    edge_id: str
    graph_id: str
    from_node_id: str                # 有向: from → to, 两端不可互换
    to_node_id: str
    hypothesis: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.hypothesis.strip():
            raise ValueError(
                "GraphEdge.hypothesis NEVER 为空 (§6-H8 复用 combo 的校验语义): "
                "一条没有假设的边说不出两端为什么被连起来")


@dataclass
class WorkbenchGraph:
    """I8 工作台图。owner_scope 隔离沿用既有 Principal 语义。"""
    graph_id: str
    project_id: str
    owner: Principal
    title: str
    created_at: datetime
    updated_at: datetime
    archived: bool = False           # 图是用户的思考过程: 归档可翻回, 删除不在 v0.4 内
                                     # (数据删除属 owner 人审节点)


@dataclass
class Favorite:
    """I9 收藏。基线 = **内嵌**证据快照, 不引用外部 snapshot。

    为什么内嵌: 收藏要能长期翻回。若只存 snapshot_id, 被引 snapshot 被 180 天周删
    任务清掉之后, 收藏就变成一个指向空处的壳——「已收藏但内容已被清理」。
    内嵌之后收藏自带内容, 不依赖别人活着。

    stale 判定来自 Revalidator 统一口径 (§6-H1), 前端 NEVER 自行按时间戳推断新鲜度;
    新收藏还没被算过, 故 snapshot_stale 默认 False。
    """
    favorite_id: str
    owner: Principal
    target_kind: Literal["cluster", "topic", "deliverable", "card"]
    target_id: str
    # —— §9-P1 采纳位 (提案, owner 未采纳 → 本轮 NEVER 实现) ——
    # P1 的做法: 把下面这行内嵌快照换成引用, 并给被引 snapshot 加冻结保护
    # (E2 周删任务跳过被收藏的)。采纳时此处改为   snapshot_id: str
    # 并同步 E2 周删条件。在那之前它只是注释, NEVER 成为真字段。
    evidence_snapshot: JSON          # 内嵌快照: 收藏时点的证据内容本体
    created_at: datetime
    snapshot_stale: bool = False     # 只能由 Revalidator 置 True (§6-H1)


def template_checksum(html: str) -> str:
    """模板内容的指纹。checksum 由内容算出, NEVER 由人手填。"""
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


@dataclass
class TemplateRecord:
    """I10 模板固化注册表项 (G5)。与既有 TemplateSpec (章节模板) 是两回事, 命名不冲突。

    checksum **与内容绑定**: 模板固化后会被生产渲染反复使用。若 checksum 与 html 无关,
    改了模板却不改 checksum, 下游拿到的就是「版本号没变、内容已变」的东西——
    产物不可复现 (CLAUDE.md S2-2 第三条铁律)。绑定之后内容一改 checksum 必须跟着改,
    否则构造期就被拒。

    slots 非空且为**元组**: 没有插槽的模板不是模板, 是一张静态页, 固化它没有意义,
    却会占着 template_id 让人以为可以拿来生成; 用元组是因为插槽集合固化后不该被
    就地追加——那会绕过 checksum 绑定。
    """
    template_id: str
    owner: Principal
    name: str
    version: int
    slots: tuple[str, ...]
    source_deliverable_id: str | None
    html: str
    checksum: str
    solidified_at: datetime
    enabled: bool

    def __post_init__(self) -> None:
        if not isinstance(self.slots, tuple):
            raise TypeError(
                f"TemplateRecord.slots MUST 是元组, 收到 {type(self.slots).__name__}: "
                "可变序列能被就地追加, 那会绕过 checksum 绑定")
        if not self.slots or any(not s.strip() for s in self.slots):
            raise ValueError(
                "TemplateRecord.slots NEVER 为空、NEVER 含空白项: "
                "没有插槽的模板是一张静态页, 固化它没有意义")
        expected = template_checksum(self.html)
        if self.checksum != expected:
            raise ValueError(
                f"TemplateRecord.checksum 与内容不符 (期望 {expected[:12]}…, "
                f"收到 {self.checksum[:12]}…): checksum MUST 与 html 绑定, 否则产物不可复现")


ShareTarget = Literal["deliverable", "graph", "topic"]


@dataclass
class ShareLink:
    """I11 外链只读分享。viewer 是匿名 Principal 子类型, 走同一 JWT 中间件 (§6-H2),
    NEVER 新写鉴权分支。"""
    token: str
    target_kind: ShareTarget
    target_id: str
    created_by: Principal
    expires_at: datetime | None      # None = 不过期。「已过期」与「已撤销」是两件事,
    revoked: bool                    # NEVER 合并成一个 bool: 过期可续期, 撤销不可逆
    created_at: datetime
    # 口令保护只以 hash 形态存在。**连放明文的地方都不留**: 只要有 password: str 字段,
    # 就一定有人在某个构造点把明文塞进去, 然后它随对象一起进日志、进快照、进导出。
    password_hash: str | None = None


def share_with_friend(link: ShareLink, friend_user_id: str) -> None:
    """好友定向分享 —— **post-v1**, 本轮明确不实现。

    NEVER 用 `enabled=False` 式的 flag 占位: 那意味着有人打开它就「能用」,
    而背后没有好友关系模型、没有鉴权路径。抛 NotImplementedError 是唯一诚实的占位——
    调用点存在、语义已定、实现明确没有。
    """
    raise NotImplementedError("friends: post-v1")
