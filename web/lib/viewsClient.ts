// 前半程三界面读客户端（FE-VIEWS）：广场/工作台/Gate。只读消费既有读端点，
// 前端零计算、NEVER 自判分类（Gate verdict 直取后端）。

export interface PlazaCluster {
  cluster_id: string;
  canonical_name: string;
  category_id: string;
  status: string;
  /**
   * 首见日期，恒 ISO 日（`YYYY-MM-DD`）。SLOT-01 让端点回出来的——
   * 这一列库里一直有，端点先前查了不回，于是卡面那一槽永远是空的。
   *
   * **可选**：`weak_signals` 那一轨与老录制回放里没有它。声明成必填的话，
   * 少一个字段就是一处 tsc 红，而真相只是「那一条数据早于这次改动」。
   */
  first_seen?: string;
  by_source: Record<string, number>;
  /**
   * 每个源的地区（`REGION-09` 加的）。**与 `by_source` 并行一键，NEVER 塞进它**：
   * `by_source` 是 `{源: 分值}`，`HOTSPOT-07` 的分列判据按这个形状读——
   * 往里塞一个对象，那些判据会在读到分值的地方拿到一个 dict，
   * 它们不会报错，只会算出一个错的列高。
   *
   * **可选**：判不出区的簇（`region IS NULL`）在这里就没有那个源的条目。
   */
  by_source_region?: Record<string, string>;
  /**
   * 每个源对这条簇说的那句**原话**（`REGION-12` 加的，`PLAZA-02` 缺口二）。
   * 微博说「脑机接口」、GitHub 说 `bci`——**同一个热点两种说法**。
   *
   * 这是 `SourceColumns` 的 `text` 槽要的东西，契约逐字：「原文；NEVER 是译文」。
   * **NEVER 拿 `by_source` 的分值去顶它**：屏上会出现一列「来源说法」写着 `100.0`。
   *
   * **查不到词面的源不出现在这里**（不是空串）：空串在屏上与「这个源说了一句空话」
   * 长得一模一样，而真相是我们没能把它的原话找回来。
   */
  by_source_text?: Record<string, string>;
  total_heat: number;
}

export interface EvidenceCard {
  card_id: string;
  cluster_id: string;
  keyword_ids: string[];
  flags: string[];
  top_links: string[];
}

export interface VerdictGap {
  missing_what: string;
  cause: string;
  action: string;
}

/**
 * Gate① 判定依据（`flint/gate/engine.py` 摊平的三规则评估痕迹）。
 *
 * ## 这里曾经写着 `boolean`
 *
 * 后端一直回的是**对象**。前端标成 `boolean` 之所以一直没出事，
 * 是因为 `GateView` 根本不渲染这个字段——**错类型一次都没被执行到**。
 *
 * 危险在于它**看起来是对的**：下一个人要把「判定依据」做成可展开面板时，
 * 会照着类型写 `{verdict.constraints_checked ? …}`——
 * **一个非空对象恒为真**，于是屏上出现一个永远展开、内容为 `true` 的面板，
 * 而真正的判定依据一项都不显示。
 *
 * 改成对象之后，那种写法会被 TypeScript 拦下来
 * （`tests/v041/test_verdict_constraints_type.py` 构造了这种误用并判红）。
 *
 * ## 判定顺序是**后端给的**
 *
 * `order` 是 A>B>C>D 那条顺序的原样转出。前端 NEVER 自己排——
 * 顺序变了要跟着后端变，而不是跟着前端的常量变。
 */
export interface ConstraintsChecked {
  /** 判定顺序（A>B>C>D），后端给什么就是什么。 */
  order: string[];
  /** 被两段式对齐降级掉的那些判定。 */
  demoted_by_alignment: string[];
  rule_a: {
    satisfied: boolean;
    /** 只用了用户自带证据——那种情况下结论要标出来。 */
    used_user_evidence_only: boolean;
    /** 卡在「等用户同意用他的证据」这一步。 */
    blocked_pending_optin: boolean;
  };
  rule_b: {
    satisfied: boolean;
    by_count: boolean;
    by_strength: boolean;
    /** **计数**，不是比率。 */
    reachable_count: number;
    strong_names: string[];
  };
  rule_c: {
    satisfied: boolean;
    failed_conditions: string[];
    blocking_competitors: string[];
  };
  /** 缺口条数。判 D 时它必然 > 0（`engine.py` 有断言）。 */
  gap_count: number;
}

export interface Verdict {
  verdict: string; // A_infeasible / B_red_ocean / C_opportunity / D_insufficient（后端定，前端不判）
  all_satisfied: string[];
  key_citation_ids: string[];
  rationale_fact_ids: string[];
  competitors: { name: string; url: string; strength: string }[];
  /** **对象，不是布尔**。见下方 `ConstraintsChecked` 的注释。 */
  constraints_checked: ConstraintsChecked;
  gaps: VerdictGap[];
}

export interface ViewOpts {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export class VerdictNotReady extends Error {}

export async function fetchPlazaHot(
  day: string, opts: ViewOpts & { region?: string } = {},
): Promise<PlazaCluster[]> {
  const f = opts.fetchImpl ?? fetch;
  // REGION-09 之后 `region` 是真参数。**不传时一个字都不加**——
  // 规格 #2.14 的增量口径：不传 region 时行为与基线逐字相同。
  const query = new URLSearchParams({ day });
  if (opts.region) query.set("region", opts.region);
  const res = await f(`${opts.baseUrl ?? ""}/plaza/hot?${query.toString()}`);
  if (!res.ok) throw new Error(`plaza: HTTP ${res.status}`);
  return ((await res.json()) as { clusters: PlazaCluster[] }).clusters;
}

/** CN-02：连**版本范围**一起取回（`DEC-045`）。
 *
 * 与 `fetchPlazaHot` 并排放着而**不改它的返回类型**：那一个有一批既有调用点与
 * 录制回放夹具，改返回形状会把它们全部带红——**而它们判的是别的事**。
 *
 * `region_in_scope` 缺席时回 `undefined`（老夹具里没有这一格），
 * 由上层按「在范围内」处理：**NEVER 默认成「不在范围」**——
 * 那会让一个正常的空结果被说成「本版不做这个区」。
 */
export async function fetchPlazaHotScoped(
  day: string, opts: ViewOpts & { region?: string } = {},
): Promise<{
  clusters: PlazaCluster[];
  regionInScope?: boolean;
  scopeLiftsWhen?: string;
}> {
  const f = opts.fetchImpl ?? fetch;
  const query = new URLSearchParams({ day });
  if (opts.region) query.set("region", opts.region);
  const res = await f(`${opts.baseUrl ?? ""}/plaza/hot?${query.toString()}`);
  if (!res.ok) throw new Error(`plaza: HTTP ${res.status}`);
  const body = (await res.json()) as {
    clusters: PlazaCluster[];
    region_in_scope?: boolean;
    scope_lifts_when?: string;
  };
  return {
    clusters: body.clusters,
    regionInScope: body.region_in_scope,
    scopeLiftsWhen: body.scope_lifts_when,
  };
}


export async function fetchEvidenceCards(
  clusterId: string, opts: ViewOpts = {},
): Promise<EvidenceCard[]> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(
    `${opts.baseUrl ?? ""}/clusters/${encodeURIComponent(clusterId)}/evidence-cards`,
  );
  if (!res.ok) throw new Error(`evidence-cards: HTTP ${res.status}`);
  return ((await res.json()) as { evidence_cards: EvidenceCard[] }).evidence_cards;
}

/**
 * 按**热点**问「它最近一次判定是哪个作业出的」（`PERSIST-04` / `DEC-044`）。
 *
 * ## 这条与 `fetchVerdict` 是两种问法，NEVER 互相替代
 *
 * | 问法 | 端点 | 什么时候用 |
 * |---|---|---|
 * | 这**一次作业**判了什么 | `GET /jobs/{jobId}/verdict` | 调用方手上已经有 job id（URL 带 `?verdictJob=`、跑完一次分析之后） |
 * | 这**个热点**判过什么 | `GET /clusters/{id}/verdict` | 只知道热点，不知道是哪次作业判的 |
 *
 * `HOTSPOT-03` / `DEC-012` 当初判死「拿 cluster_id 拼一个 job id 去试」，
 * **理由是那时没有真相可查**。`DEC-044` 的 `cluster_verdicts` 就是那个真相——
 * 所以这里是**去问**，不是去猜。
 *
 * 回 `null` = 这个热点**没判过**（端点回 404）。
 * NEVER 把它读成「读失败」：前者该去发起一次分析，后者该去查后端。
 */
export async function fetchClusterVerdictJob(
  clusterId: string, opts: ViewOpts = {},
): Promise<string | null> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(
    `${opts.baseUrl ?? ""}/clusters/${encodeURIComponent(clusterId)}/verdict`,
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`cluster verdict: HTTP ${res.status}`);
  // 缺 `job_id` 读成**没判过**（`null`），NEVER 让 `undefined` 漏出去：
  // 调用方（分析屏）用 `undefined` 表示「还没读」，
  // 漏一个出去屏就永远停在加载态——**而那一屏什么都不会说**。
  return ((await res.json()) as { job_id?: string }).job_id ?? null;
}

export async function fetchVerdict(jobId: string, opts: ViewOpts = {}): Promise<Verdict> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(`${opts.baseUrl ?? ""}/jobs/${encodeURIComponent(jobId)}/verdict`);
  if (res.status === 404) throw new VerdictNotReady(jobId);
  if (!res.ok) throw new Error(`verdict: HTTP ${res.status}`);
  return ((await res.json()) as { verdict: Verdict }).verdict;
}
