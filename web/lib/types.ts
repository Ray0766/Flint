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

/**
 * `GET /deliverables/{id}/quality` 的答复（`WB-05` 加）。
 *
 * 字段逐字对齐 `flint/api/quality.py#_quality_payload`。
 * **这里没有「逐章是否满足」那一格**——那个端点报的是**整份交付物**的质量：
 * 引用覆盖、未解析引用、缺口引用、阻断态四项。
 * 章一级的判定今天**没有任何后端出处**（单 `docs/blocked/QUALITY-FAMILY-HAS-NO-BACKEND.md`），
 * 所以章节导航那一列显示「还没有判定」，NEVER 由前端自己算一个出来。
 */
export interface QualityReport {
  deliverable_id: string;
  citation_coverage: {
    blocks_counted: number;
    blocks_with_refs: number;
    blocks_excluded_user: number;
  };
  unresolved:
    | { status: "not_checked" }
    | { status: "checked"; count: number; ids: string[] };
  gap_hint_refs: string[];
  blocking_block_ids: string[];
  blocking_open: number;
  advisory_open: number;
  exportable: boolean;
}
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

// ───────────────────────── TYPE-02：九条端点的响应形状
//
// ## 本节只补**真缺的**，NEVER 重抄已有的
//
// 对账器只读本文件，于是把「类型在 `viewsClient.ts` / `topicClient.ts` 里」
// 报成「前端根本没建类型」。按它的说法做，会把 `PlazaCluster` / `Topic` /
// `EvidenceCard` 这些**正在被使用的**类型再抄一遍——
// 两份定义从抄完那一刻起就开始各走各的。
// 尺子那一处登记在 `docs/blocked/PARITY-ONLY-SCANS-TYPES-TS.md`（归 `TYPE-04`）。
//
// 把九条按「全 web/lib」重新量过之后，真缺口只有两类：
// **① 信封键**（响应最外层那一层，客户端拆开就丢了，从没被类型化）；
// **② `/plaza/hot` 的热度分量与弱信号**——15 个字段，一个都没有。
//
// 字段与类型逐条取自**真 payload**（`GET /plaza/hot?day=2026-07-04` 实打），
// NEVER 按蓝本或记忆写。

/** 热度分量：后端算好的六个数，前端**零计算**，原样显示。 */
export interface HotnessComponents {
  velocity: number;
  accel: number;
  /** 跨源出现次数——**整数计数**，不是比率。 */
  cross_count: number;
  multi_boost: number;
  novelty_factor: number;
  decay: number;
}

/** 弱信号行：与热点簇**不是同一张表**，它有自己的分数轴。 */
export interface WeakSignalRow {
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

/** `GET /plaza/hot` 的信封。
 *
 * `day` 是**后端给的那一天**（`"2026-07-04"` 形状的字符串），
 * NEVER 用浏览器本地日期替代——两者在跨时区时会差一天，
 * 而屏上说的是「这一天的热点」。
 */
export interface PlazaHotResponse {
  day: string;
  clusters: PlazaClusterRow[];
  weak_signals: WeakSignalRow[];
  /** CN-02 / `DEC-045`：这一区在**本版**有没有内容。
   *  **与 `clusters` 为空是两件事**：空列表是「查过了没有」（换一天），
   *  `false` 是「这一版不做这个区」（等下一版）。
   *  可选：老录制回放里没有这一格，声明成必填会让那些夹具全部失效。 */
  region_in_scope?: boolean;
  /** 收窄什么时候解除。人话，因为读它的是用户。 */
  scope_lifts_when?: string;
}

/** 热点簇行。`hotness_components` 是本节新补的那一块。 */
export interface PlazaClusterRow {
  cluster_id: string;
  canonical_name: string;
  category_id: string;
  status: string;
  /** 首见日期，恒 ISO 日（`SLOT-01` 让端点回出来的）。 */
  first_seen?: string;
  by_source: Record<string, number>;
  /** 每个源的地区（`REGION-09`）。**并行一键，NEVER 塞进 `by_source`**。 */
  by_source_region?: Record<string, string>;
  /**
   * 每个源对这条簇说的那句**原话**（`REGION-12`）。
   * 微博说「脑机接口」、GitHub 说 `bci`——同一个热点两种说法。
   *
   * 与上面两键**三键并行**：分值、地区、词面各走各的。
   * **NEVER 拿分值去顶词面**（屏上会出现一列「来源说法」写着 `100.0`），
   * 查不到词面的源**不出现在这里**（不是空串）。
   */
  by_source_text?: Record<string, string>;
  total_heat: number;
  hotness: number;
  hotness_components: HotnessComponents;
}

// ── 信封键：这几条端点的元素形状早已有类型，缺的只是最外面那一层
/** `GET /topics/{id}` 的信封（元素形状见 `topicClient.Topic`）。 */
export interface TopicResponse<T> {
  topic: T;
}
/** `GET /jobs/{id}/verdict` 的信封（元素形状见 `viewsClient.Verdict`）。 */
export interface VerdictResponse<T> {
  job_id: string;
  verdict: T;
}
/** `GET /clusters/{id}/verdict` 的信封（`PERSIST-04` / `DEC-044`）。
 *
 * 比 `VerdictResponse` 多一个 `cluster_id`——对账器实测到了这个差
 * （`WIRE-VERDICT` 接完之后它报 `field_mismatch`，**而它是对的**：
 * 那条端点回三个字段，而前端的类型只说了两个）。 */
export interface ClusterVerdictResponse<T> {
  cluster_id: string;
  job_id: string;
  verdict: T;
}

/** `GET /clusters/{id}/evidence-cards` 的信封（元素见 `viewsClient.EvidenceCard`）。 */
export interface EvidenceCardsResponse<T> {
  cluster_id: string;
  evidence_cards: T[];
}

// ── 干预层两条：元素形状在 `interventionClient.ts`，缺的是乐观锁那个字段
/** 争议/证据提交回来的**当前版本号**——乐观锁用它，NEVER 前端自己加一。 */
export interface CurrentVersioned {
  current_version: number;
}

// ── 提交类端点的**响应**形状
//
// ## COMBO-ECHO：这两个类型此前描述的是一份**不存在的形状**
//
// 改前它们叫 `AnalysisSubmitEcho` / `ComboSubmitEcho`，字段是
// `{project_id, keywords, locale}` 与 `{card_ids, n, hypothesis}`——
// **一个都不在响应里**：
//
// - `card_ids` / `hypothesis` / `keywords` / `locale` 是调用方**发出去的**东西，
//   它们出现在 `runner.submit(payload={…})` 里，不是回来的；
// - `n` 来自 `flint/api/combo.py` 里一个局部计数器 `counter = {"n": 0}`。
//
// 对账器当时把函数体里**每一个** dict 都当成响应，于是抽到了这些键；
// 而前端恰好照着它们建了类型——**两边对着一份虚构的形状达成一致，尺子报绿**。
// **这比报错更坏：它把「没人核对过」伪装成「核对过、没问题」。**
//
// ## 为什么改前端而不是给后端补三个字段
//
// 后端补上就是**让虚构变成事实**（本卡 acceptance 逐字禁掉）。而且那三格本来也不该有：
// `card_ids` 与 `hypothesis` 是调用方自己刚发出去的，回声一份只会让人去信回声
// 而不信自己的入参；`n` 从来就不是一个响应字段。
//
// 真响应见 `flint/api/schemas.py`：`AnalysisSubmitResponse` 只有 `job_id`，
// `ComboCreateResponse` 是 `{project_id, topic_ids, degraded}`——
// 而 `chainClient.submitCombo` 的注释一直写的就是后者，
// **只有 `types.ts` 这两个接口是错的，且全仓没有一处 import 它们**。

/** `POST /projects/{id}/analysis` 的响应。排进队列就回作业号，**别的都不回**。 */
export interface AnalysisSubmitResponse {
  job_id: string;
}

/** `POST /projects/combo` 的响应（`flint/api/schemas.py#ComboCreateResponse`）。
 *
 * `degraded` 是**这一次组合有没有降级**，NEVER 读成「项目坏了」。 */
export interface ComboCreateResponse {
  project_id: string;
  topic_ids: string[];
  degraded: boolean;
}

// ── TYPE-04：尺子改成「按接口分组 + 展开末段枚举」之后**新看得见**的三条。
// 提交类的 proposal 与 report 此前藏在那条末段为参数的派发路径里——
// 展开 JobKind 才露出来。
//
// **本段有意不写带反引号的路径字面量**：`tests/v041/test_fe_api_contract.py`
// 的扫描器不剥注释，会把注释里的路径当成一次真调用（本卡实测被它绊过一次）。
// 已登记在 docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md。

/** `POST /projects/{id}/report` 的回声。 */
export interface ReportSubmitEcho {
  job_id: string;
  analysis_id: string;
  template_id: string;
}

/** `POST /projects/{id}/proposal` 的回声。
 *
 * `audience` 是**受众分叉**那一维（五套人类模板 / vibe_pack），
 * 后端给什么就是什么——前端 NEVER 自己推断该给谁看。
 */
export interface ProposalSubmitEcho {
  job_id: string;
  report_id: string;
  template_id: string;
  profile_id: string;
  audience: string;
}

/** `POST /projects/{id}/disputes` 的回声。
 *
 * 两个版本号**各是各的**：`current_version` 是争议记录自己的乐观锁，
 * `ledger_version` 是它所依据的证据台账版本。
 * 合成一个会让「有人同时改了争议」与「台账更新了」分不开。
 */
export interface DisputeSubmitEcho {
  target_id: string;
  status: string;
  current_version: number;
  ledger_version: number;
}

// `GET /deliverables/{id}` 的元信息（TYPE-01）。
//
// ## 为什么以前「看起来」有类型
//
// 对账器把 `types.ts` 的字段名当成**一个平集**来比。`Block` 里恰好有
// `deliverable_id` 与 `type`，于是这条端点被判成「建了类型但漂移了」——
// 而真相是**前端从没为它建过类型**，两个同名字段是撞上的。
// 两者要人做的事不同：前者去对齐，后者去新建。见 `docs/trace/TYPE-01.md`。
//
// ## 三个字段各自是什么
//
// - `version`：交付物自身的版本号；
// - `ledger_version`：它所依据的**证据台账**版本——两者会各走各的，
//   NEVER 假设相等（台账更新了而交付物没重生成，正是 Revalidator 要处理的情形）；
// - `reproducible`：这份交付物能否被原样复现（S2-2 那条铁律的可读形态）。
export interface DeliverableMeta {
  deliverable_id: string;
  type: string;
  version: number;
  ledger_version: number;
  reproducible: boolean;
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

// ═══════════════════════ TYPE-05：收藏 / 外链 / 设计提交
//
// 这三条被对账器报成 `field_mismatch`，而实况是**它认错了接口**：
// `/favorites` 与 `/shares` 都被匹到 `interventionClient.ts#DisputeInput`，
// 只因三者碰巧都有 `target_id` / `target_kind`。
// 所以本卡给它们**各建自己的类型**，而不是去「对齐」那个争议入参。

/** 一条收藏。逐字对齐冻结件 `Favorite`，**`owner` 除外**——调用方就是 owner。 */
export interface FavoriteRow {
  favorite_id: string;
  target_kind: string;
  target_id: string;
  /** 收藏那一刻的证据快照。**真的是任意 JSON**（各 target_kind 形状不同）。 */
  evidence_snapshot: unknown;
  /** ISO 时刻（后端 `.isoformat()`）。 */
  created_at: string;
  /** 只能由 Revalidator 置 `true`（§6-H1）。前端 NEVER 按时间戳推断（`DEC-039`）。 */
  snapshot_stale: boolean;
}

export interface FavoritesResponse {
  items: FavoriteRow[];
}

/**
 * 422 的机读体：**哪一个字段不合法、合法值是哪些**。
 *
 * `/favorites` 与 `/shares` 共用这一个形状（两处后端逐字相同）。
 * 只回一句 message 的话，前端只能把整句话摆给用户看——
 * 而它需要知道该把光标送回哪一个输入框。
 */
export interface FieldNotAllowed {
  field: string;
  allowed: string[];
}

/** 一条只读外链。**过期与撤销分开报**：过期可续期，撤销不可逆（冻结件原话）。 */
export interface ShareLinkRow {
  token: string;
  target_kind: string;
  target_id: string;
  expires_at: string | null;
  revoked: boolean;
  created_at: string;
}

export interface SharesResponse {
  items: ShareLinkRow[];
}

/**
 * `POST /projects/{id}/design_generate` **提交进作业队列的那份 payload**。
 *
 * 它不是响应体（响应是 `{ job_id }`，见 `ReportSubmitEcho` 一族）——
 * 对账器把处理函数里所有字面量 dict 的键都算作「这条路由的键」，
 * 于是这份 payload 的三个键也在其中。**如实建成 payload 类型，
 * NEVER 编一个带 `brief` 的「响应」**：那种类型描述的东西根本不存在。
 */
export interface DesignGeneratePayload {
  project_id: string;
  brief: string;
  template_id: string | null;
}

/**
 * `POST /projects/{id}/design_generate` 的**响应**：只有一个作业号。
 *
 * 与上面那份 payload 是两回事，所以是**两个类型**——
 * 合成一个会让「我提交了什么」与「后端给了我什么」共用一个形状，
 * 而它们的字段没有一个是重合的。
 */
export interface DesignGenerateAccepted {
  job_id: string;
}

/**
 * `GET /settings/locale`：当前语言 / 地区 + 可选值清单。
 *
 * `options.region` 是**九区词表的唯一真相**（`LOC-01`）——
 * 前端 NEVER 再抄一份。未归区不在其中：它是**筛选面**上的第十个选项
 * （`REGION-11` / `DEC-040`），由广场自己追加。
 *
 * 这条端点此前被报成 `frontend_untyped_response`：屏里确实有一个
 * 同名的局部类型，但它在 `web/app/` 下——**尺子只扫 `web/lib/`**，
 * 而尺子扫不到的类型，别的屏也 import 不到。
 */
export interface LocaleOptions {
  lang: string[];
  region: string[];
  /** `SHELL-02` 的第三根轴。**可选**：老录制回放夹具里没有这一格。 */
  theme?: string[];
}

export interface LocaleResponse {
  lang: string;
  region: string;
  /** `SHELL-02` 的第三根轴（`system` / `light` / `dark`）。
   *  漏了这一格的时候 `check_fe_be_parity` 把这条端点报成 `field_mismatch`
   *  ——**它是对的**：后端回了四样，前端的类型只说了三样，
   *  于是读它的人拿不到主题、而 `tsc` 不会说一个字。 */
  theme?: string;
  options: LocaleOptions;
}

// ── PERSIST-02：工作台三条端点的响应形状
//
// 这三个必须是 `export interface` 而不是 `export type`：
// `tools/check_fe_be_parity.py#_frontend_interfaces` **只认 `export interface`**
// （它的正则逐字写着）。写成 `type` 的话尺子报「前端根本没建这条端点的类型」，
// 而类型明明就在那儿——本卡实测撞上这一条。

/** `POST /workbenches` 的响应（`flint/api/workbenches.py#create_workbench`）。 */
export interface WorkbenchCreated {
  graph_id: string;
  seed_cluster_id: string;
  /** `true` = 这次新建；`false` = 落回既有的那张图（重复入台）。 */
  created: boolean;
}

/** `POST /workbenches/{id}/nodes` 的响应。`node_id` **由后端给**。 */
export interface WorkbenchNodeAdded {
  node_id: string;
  graph_id: string;
  created: boolean;
}

/** `GET /workbenches/{id}` 的响应（`PERSIST-02-b` 建）。 */
export interface WorkbenchDetail {
  graph_id: string;
  seed_cluster_id: string;
  created_at: string;
  /** `null` =「这张图还没有归属任何项目」（`DEC-051`）。NEVER 读成空串。 */
  project_id: string | null;
  nodes: WorkbenchNodeRow[];
  edges: WorkbenchEdgeRow[];
}

export interface WorkbenchNodeRow {
  node_id: string;
  source_kind: string;
  source_id: string;
  label: string;
  position: [number, number];
  primary: boolean;
}

export interface WorkbenchEdgeRow {
  edge_id: string;
  from_node_id: string;
  to_node_id: string;
  hypothesis: string;
}
