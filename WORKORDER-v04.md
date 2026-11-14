# WORKORDER-v04 · 燧石 Flint 全球化 + 工作台 增量工单

> **版本**：v0.4 增量冻结（基线 v0.3.3 不推翻）。**受众**：ai_executor（单 agent，无监管 AI）。
> **依据**：flint-feature-list-v1.md（A~L 96 项，唯一需求来源）+ protocols.py（v0.3.3 修订真件）+ 技术方案-v1.1.md + tasks.json（2.0-vibe，232 任务实况）+ CLAUDE.md（vibe_pack v2.0 真件）+ 前端功能说明.md（中性版 667 行）。附件逐件核实结论 → `ASSUMPTIONS.md`。
> **规范力标记**：沿用 CLAUDE.md 约定——MUST / NEVER 为硬约束；SHOULD 为默认做法，偏离须在 trace 说明；MAY 为可选。标 `[示例]` 的内容 non-normative。标 `[待核实]` 的数字或路径取自清单或既往审计、本轮附件未含实物。
> **配套**：`tasks-v04.json`（D2，机读任务真相）+ `worker.md`（D3，工作 AI 唯一提示词）。
> **锚点规则**：本文各节以 `WORKORDER-v04.md#<节号>` 被 context_refs 引用；§3 七条原则以 `PRINCIPLES#<编号>` 引用（PRIN-01 将 §3 落盘为 docs/PRINCIPLES-v04.md，一处定义、两处同文校验）。

---

## §1 变更背景与解冻依据

**冻结规则**：protocols.py 头部原文规定「改动只能来自 ⑧ 对抗性推演产出的 v0.4 修订」；v0.3.3 已将其补充为「改动来源 = ⑧推演 ∨ owner 变更」（tasks.json.frozen_against 与 CLAUDE.md S4 所载 v0.3.3 决议）。**本次解冻走 owner 变更通道**，触发事由两项：

1. **全球化需求**（清单 A/B 组）：系统语言 zh/en、九地区（CN/US/AU/SG/JP/KR/GB/IT/FR，无 EU）、语言地区正交、分区源与四级权威度。
2. **立场修正 G0**（清单 0 节）：AI 设计工作台产出的 HTML 定性为「统一模板的参考样板」而非交付物；原「AI 不得撰写正文」约束作废，改为 探索期（几乎无约束）→ 固化期（强约束）两阶段模型，风险转移到 G2（样板可辨识）与 G3/G6（固化闸门）。

**解冻方式**：v0.4 **增量**冻结。NEVER 覆盖 v0.3.3 原件；一律另存副本（目录 `contracts_v04/`，原 `contracts/` 保持只读零触碰）。只加不删；确需废弃的字段或语义标 `deprecated` 并保留。

**与 ⑧ 推演的关系**：技术方案 v1.1 自述「⑧ 推演合入 v0.4 预计只动 E4/E6」——那是对推演来源的预估；本次 owner 变更实际波及 E2/E3/E4/E5/E6/E9/E10/E12 八节（§2-J2）。**⑧ 推演仍欠，不因本次关闭**；两条解冻来源相互独立，后续推演发现按同一增量机制合入。附注：批量上传中曾混入三份产品生成的 vibe_pack 样例（gold-C-04 / gold-B-01 / gold-C-01）；owner 已明确系顺带上传、不使用，不作为 ⑧ 材料——⑧ 推演的欠账状态不变。

**执行模式声明**：本轮**单 agent**。v0.3.3 的 review_gate 双 agent 流水线在本增量内改为 self_review 自审机制（字段改名 + 语义变更，见 tasks-v04.json.rules 与 D3 §4.2）；CLAUDE.md S7「同一原因连续 2 次失败 → 升级」由本工单 4.4「同一卡自修 3 轮仍不过 → blocked 绕行」**显式覆盖**（owner 于本工单核准的差异，非静默冲突；其余 S 章约定继续适用）。质量兜底 = verify_cmd 覆盖率 100% + 自审纪律 + 阶段 SELFCHECK（L1~L7 转内部自查，L8 删除）。

---

## §2 影响面（清单 J 组九项，逐附件核实）

> 核实方式：逐个打开真实附件比对；与清单描述不符处以核实结果为准，汇总于本节末「与清单预估不符之处」。

### J1 `models.py` / `protocols.py`（必做）

**protocols.py 侧（真件已核，协议级全量列出）**：

| 协议 | v0.4 触点 | 处置 |
|---|---|---|
| `TrendSource / PaperSource / PatentSource / NewsSource / CompetitorSource / FundingSource` | 检索按 `SourceRegistry(region)` 选源；文档溯源须携带 region / source_country / authority_tier / fetch_legal_status | 协议签名不动；实现层接 I2/I3（§4） |
| `PricingParser` | PricingRecord 增 currency（J9） | 签名不动，产物字段增量 |
| `QueryBuilder.build(keywords, intent, locale)` | locale 参数既有——多语检索复用之，locale 语义扩展为 SystemLanguage×Region 组合串（增量注记，不改签名） | protocols_v04 docstring 增补 |
| `EvidenceScorer`（双尺 [审7]） | B3 三尺：authority 轴接入 axis 体系（记于 `EvidenceScore.components`），权重初值中性 1.0 标 revisit（K3） | REGION-06；金标回归守护 |
| `CitationAligner`（两段式 [D1-c]） | B10：align 的 evidence 输入 MUST 为原文字段，译文禁入 | protocols_v04 docstring 增补 + MIGRATE-01 规格 |
| `JobRunner / JobEventStream`（SSE seq/replay） | 新 JobKind 三种 + 新 JobEvent payload 七种（§4 事件表）；G7 流式 delta 的 replay 语义 → §9-P3 | SCHEMA-13 |
| `Analyzer.verdict` | B2 后半：authority_tier=unknown 的证据不得满足判 A/B 必要条件（前置门，独立于评分公式） | REGION-03 |
| `ReportComposer / Renderer`（导出门禁 [审11]） | G21 复用导出管线；G22 闸门沿 blocking 语义扩两判据（空假设边、模板未固化——后者在隔离带） | DESIGN-15/16/32；§9-P2 |
| `Revalidator / LedgerStore.diff`（changed→advisory、removed→blocking） | H1 三处接入：收藏快照 stale、分析结果时效、Deliverable 图谱联动 | HOTSPOT-06 / FAV-02 / DESIGN-25 |
| `SnapshotStore`（[F2] 保留 180 天，唯一例外 RedactionRecord） | 与 D2「收藏=冻结快照」的保留期矛盾 → §9-P1（基线绕行=收藏内嵌副本，零协议改动） | SCHEMA-09 / FAV-01 |
| `SpecExporter / DagValidator / RegistryValidator` | D2 产物按 DagValidator 的 vibe_pack 质量门（verify 覆盖率 100%、双单位）自校；新前端依赖（next-intl）MUST 过 RegistryValidator | MIGRATE-04 / I18N-01 |

**models.py 侧（真件第 4 轮已到并核实：1030 行 / 30783 B / md5 380d7b5a…，含 v0.3.3 特征）**：字段级影响面与落点修正已预填至 `docs/schema_reconcile_prefill_v04.md`（SCHEMA-00 的输入；仓库工作副本仍为最终权威，additive 校验照跑）。要点：I2 溯源四字段落 **Doc**（真件 Origin 为选题入口五类，非文档溯源）；I4 名称三元组落 **Cluster**（热点卡实体=Cluster，canonical_name 保留）；I6 收敛为 WhyNowEvidence.event_display + Citation.quote_span_display（event_date 为 date 类型，无 date 文本槽）；AnalysisContext 现有 project_id/budget_cny/locale，增 lang/region、locale 保留兼容；**PricingRecord 已含 currency 与 region**（J9 收敛为核实登记）；JobKind 七值与 payload 判别类均在 models.py（事件增量落 models_v04）。风格核实：非 frozen `@dataclass` + Literal + 中文 docstring，v04 增量区同风格。

### J2 技术方案 v1.1 八节（必做，产物 = `docs/技术方案-v1.2-delta.md`，MIGRATE-02）

- **E2 存储设计**：表清单 ≈22 张 → 增 7 张：`source_registry`、`workbench_graphs`、`graph_nodes`、`graph_edges`、`favorites`、`template_registry`、`share_links`；`price_entries` 加 `currency` 列（默认 `"CNY"`）；`snapshots` 表 180 天周删任务与收藏冻结语义的冲突处置 → §9-P1。
- **E3 API 契约**：核心端点组增 `/favorites`、`/share-links` 与 `/share/{token}`（viewer 匿名）、`/workbenches`、`/design`；既有 `/plaza/hot` 增 `region` query（增量不破坏）；错误码增 `EMPTY_HYPOTHESIS`（F8/F9 服务端判据）。鉴权不新建：全部走 E3 既有 JWT 中间件的 Principal→owner_scope 解析（§6-H2）。
- **E4 作业编排**：`daily_ingest` 按 region 分批加锁（`lock:daily_ingest:{day}:{region}:{batch}`）；新 JobKind 三种（translate / design_generate / template_solidify）入 worker 消费。
- **E5 LLM 调用层**：翻译调用归入「幂等判别类」缓存（内容 hash：原文字节+目标语言+translator 版本）；design_generate 走流式（§9-P3）；本轮 NEVER 动用真实 API key 或付费调用——LLMProvider 一律 fixture/mock 注入（硬约束 6）。
- **E6 故障降级矩阵**：增 3 行——翻译服务不可用（不阻断；A7 退 `name_native` 单行）、单区源全灭（不阻断；该区当日缺数据角标，沿「单热点源不可用」行语义）、模板注册表不可用（阻断固化与生产渲染，不阻断探索期）。
- **E9 测试策略**：新不变量测试三条（I12）+ 正交性 18 组合 harness（A8）+ additive 冻结件校验入 CI。
- **E10 前端架构**：next-intl 入栈（RegistryValidator 校验后锁版）；图谱视图 = zustand 状态 + 自绘 SVG（力导向手写一次性布局，零新依赖）；移动端图谱只读；设计台 iframe.srcdoc 零构建。
- **E12 fixture**：目录扩为 `fixtures/{region}/{source_id}/{yyyy-mm-dd}.json`；翻译 fixture 表；九区源注册**空表**种子（K1 留空）+ 双区同事件聚类 fixture（B5 反例）。

### J3 接地增强(a) 规格（必做·全链最前置，MIGRATE-01）

核实：现行接地铁律只验 `citation_id` 在账本，不验 event 文本/日期忠于被引卡（既往横评已实证「引真卡+编假证据」漏洞）。(a) 规格 = event 文本/日期与被引卡一致性校验，v0.4 增补三条：校验输入 MUST 为原文字段（PRINCIPLES#B10）；译文 NEVER 参与一致性比对；报告以译文呈现引用时，出处槽 MUST 可展开到原文。规格依赖 PRINCIPLES#B9/#B10 成文后才可写 → PRIN-01 → MIGRATE-01 为整条链前两卡。

### J4 《前端功能说明》扩版（必做，MIGRATE-03）

核实：真件 667 行、12 界面（2.1~2.12）、API 总表 20 端点、状态呈现规则 8 条；3.4（i18n，⚪未建·接口预留）与 3.5（多地区，V2-001）本次前提为正项。扩版到 **16+ 屏**：新增 ①语言/地区设置 ②热点卡片广场（C 组）③收藏图书馆（D 组）④热点工作台·图谱（F 组）⑤AI 设计工作台（G 组）⑥外链只读查看页（E3）。**命名冲突处置**：现 2.2「工作台（证据卡）」与 F 组「热点工作台」并屏定名——SHOULD 方案：2.2 更名「证据卡面板」，作为图谱工作台内的抽屉面板（双击节点即达），`/workbench` 路由归 F 组；该定名偏离清单未提及处，扩版文档内标 `owner_review: true`。全量 i18n key 总表随扩版产出（A4 落点）。

### J5 `tasks.json` 重估（必做，MIGRATE-04 + 本包 D2）

核实：**基线实况 232 任务**（M1 41 / M2 52 / M3 66 / M4 44 / FE 5 + FE-CORE 8 + FV 2 / TS 14；含 ts/ts2/ts3 批次扩展；dag_report：acyclic、errors=[]、Σ270 cycles、关键路径 53 cycles、verify 覆盖率 1.0、review_gate 77 张）≠ 清单口径「M1 41 + 框架 251」。处置：D2 = v0.4 增量 DAG（本包 103 卡）；MIGRATE-04 = 基线补丁（77 张 review_gate→self_review 改名转义；FE/FE-CORE/FV 15 卡逐张标 `impacted_by_v04`；TS 组 hypothesis 通道标 H8 复用锚）+ 合并 DAG 校验。字段映射约定见 tasks-v04.json.rules。

### J6 `design_handoff_flint_web/` 登记（本轮登记，MIGRATE-05）

登记内容 [待核实：包未随附件，数字取自清单与既往审计]：20 屏两轨、中文硬编码零 i18n key、缺 4 类新屏（设置/收藏/图谱/设计台）；两处已知问题（456 处 inline mono 仅 14 处带 tabular-nums 且 `.num` 类零使用；23 处 ⚠ 与「禁 emoji 当图标」冲突）→ 修复卡 DESIGN-05（对挂载进仓库的 `_ds` 副本执行并以扫描器断言）。

### J7 `harness/prod_caliber.py` 影响声明（本轮登记，MIGRATE-06）

登记：12 金标场景只验中文；双语后免费档路线判断（0.44 vs 0.90 悬置中）的数据基础改变 → K7 待 harness 重跑。**本轮 NEVER 修改 harness**（重构属 §10-①）；声明文档逐场景引用 12 个场景 id 并写明「不因 v0.4 改动其断言」。

### J8 总量重估（落笔于 §8，无独立任务卡）

基线 232 + 本增量 103 = **335**；另 FE 批次 15 卡中预计 8~10 卡因 i18n key 化与新屏结构受返工影响（只标记不重写，实际返工量在 V2 出口后按标定复估）。依据与阶段拆分见 §8。

### J9 PriceBook 多币种（真件核实后收敛：字段已存在，本轮登记核对）

真件 `PricingRecord` **已含** `currency: str` 与 `region: str`——清单预估的加字段无需执行。收敛为：SCHEMA-14 做存在性断言；MIGRATE-07 登记「字段既存 + price_entries 表列核对（与 E2 对齐）」。汇率、多币种定价分档 NEVER 本轮实现 → K8。

### 与清单预估不符之处（核实结果为准）

1. **models.py 前三轮错传、第 4 轮真件已到**（1030 行 / md5 380d7b5a…）；零猜测书写形态保留，落点已按真件预填（docs/schema_reconcile_prefill_v04.md），SCHEMA-00 保留为仓库内最终防线。
2. **CLAUDE.md 首轮错传、二轮真件已到**（vibe_pack v2.0）；随包另收三份产品生成样例包（gold-C-04 / gold-B-01 / gold-C-01），登记为形态参考。
3. **重估基线**：清单「41 + 框架 251」→ 实况 232 全量展开（J5）。
4. **卡片字段实名** `task_id/estimate_cycles/review_gate` ≠ 工单示例 `id/cycles/self_review/blocked_by` → D2 rules 做映射约定。
5. **「工作台」命名冲突**：现 2.2 证据卡工作台 vs F 组热点工作台 → J4 并屏定名（owner_review）。
6. **F8 边假设与 combo hypothesis 同源**：origins/topic_seeds 已落库、`POST /projects/combo` 已建、卡数 2~5 与 hypothesis 非空已是现行硬校验 → 核实新增复用项 **H8**（§6），F 组 NEVER 新写假设通道。
7. **热点卡实体已核定 = `Cluster`**（TrendItem 为采集态、EvidenceCard 为证据卡）；I4 落点随之钉定。
8. **端点为增量非新建**：E3 已有五组核心端点 + 前端说明 20 端点总表 → C/D/E/F/G 全部挂既有组或新增子组，NEVER 另立顶级风格。
9. **解冻来源表述**：v1.1「⑧ 只动 E4/E6」为推演预估，本次 owner 变更实波及八节（§1）。
10. **双 agent 口径残留**：清单头与 L 组按监管 AI 行文 → 单 agent 工单口径为准（L8 删，L1~L7 转自审）。
11. **B2 权威度枚举**：清单文字「四级」+「unknown 时…」→ 实际枚举五值（四级 + unknown 缺省态），§4-I1 按五值定义。
12. **E12 已全 fixture 化**（respx 回放、CI 永不联网 S2-7）：硬约束 5 与现行体系天然一致，登记为已满足项。
13. **AnalysisContext 现有 locale 无 lang/region**：增两典型化字段、locale 保留兼容并注记派生关系（§4-I13，owner_review）。
14. **I2 落点修正**：清单写 Origin，真件 Origin 为选题入口五类（combo/idea/domain/competitor/document）——溯源四字段改落 **Doc**；TrendItem.region 既存保留。
15. **PricingRecord 已含 currency 与 region**：J9 由「加字段」收敛为「核实登记」。
16. **I6 槽位收敛**：event_date 为 date 类型无原文文本，date display 槽取消；落点 = WhyNowEvidence.event_display + Citation.quote_span_display。
17. **冻结件风格 = 非 frozen `@dataclass`**：§4 风格声明与 B7 执行机制随之修正。
18. **models.py 头部冻结规则文字滞后**（未同步 v0.3.3「∨ owner 变更」，protocols.py 已同步）：登记为文字滞后，非阻塞；v04 副本按 v0.3.3 口径书写头部。

---

## §3 前置原则（PRINCIPLES v04 · 七条）

> 本节即 `docs/PRINCIPLES-v04.md` 的规范正文（PRIN-01 落盘同文，`tools/check_principles_doc.py` 校验两处一致与四段完整）。每条含：规则 / 反例 / 校验点（可执行）/ 违反时的系统行为。schema 与校验器以 `PRINCIPLES#<编号>` 引用。本节是 §4~§6 与 D2 全部功能卡的前置依赖。

### PRINCIPLES#A3 语言与地区正交

- **规则**：`SystemLanguage ∈ {zh, en}` 统治全站 UI 文案与生成内容语言；`Region ∈ {CN,US,AU,SG,JP,KR,GB,IT,FR}` 只决定数据源选集与热点集合。两值独立存 user profile（A5）；切地区 NEVER 改语言，切语言 NEVER 改热点集合。
- **反例**：切 region=JP 时把界面变日文（日文不在语言集）；lang=en 时把 CN 热点集合过滤成英文源；用 Accept-Language 推导 region。
- **校验点**：`python tools/orthogonality_check.py --combos all` —— 遍历 9×2=18 组合，逐组断言四条：①UI locale == lang ②检索源集合 == SourceRegistry[region] ③热点集合内容 hash 与 lang 无关 ④生成产物 `Deliverable.lang == lang`。
- **违反时**：CI 红；运行时出现由 lang 派生 region 或反向派生 → 抛 `OrthogonalityViolation`，拒绝该请求并落 structlog error。

### PRINCIPLES#B4 本国源优先但不隔离

- **规则**：检索排序 MAY 以 region_match 加权提升本国源；过滤器 NEVER 按国别排除他国源。跨国立场分歧沿 `by_source` 分列独立呈现（§6-H6），NEVER 合成为单一结论句。
- **反例**：`[s for s in sources if s.country == region]`；提示词写「综合各国观点给出统一结论」。
- **校验点**：`pytest tests/v04/region/test_registry.py -q`（他国强证据在选集内断言）+ `pytest tests/v04/region/test_by_source_regions.py -q`（分歧 fixture 输出 ≥2 列且无合成结论句——以结论句模板黑名单匹配）。
- **违反时**：检索层单测失败；生成层该 block 标 `needs_review`，导出闸门按既有 blocking 语义拦截。

### PRINCIPLES#B5 跨区不得合并成簇

- **规则**：聚类 MUST 先按 region 分桶再执行；簇血缘增 region 维度；跨区关联的唯一合法通道 = `same_event_group` 显式建立（B6，由用户或系统操作，NEVER 靠 embedding 相似度自动合并）。
- **反例**：embedding 把 US 与 JP 对同一事件的报道合成一簇——产出哪国都不存在的假热点。
- **校验点**：`pytest tests/v04/region/test_cluster_bucketing.py -q`（双区同事件 fixture → 断言产出 2 簇 0 合并；`all(len({m.region for m in cluster})==1)`）+ `pytest tests/v04/region/test_same_event_group.py -q`（不存在自动建组路径的断言）。
- **违反时**：聚类作业 job failed（阻断当日该区更新，其余区照常——E6 部分成功语义）。

### PRINCIPLES#B7 name_native 唯一权威

- **规则**：`name_native` NEVER 翻译、NEVER 改写；聚类/检索/去重/embedding 一律以原文字段为输入。
- **反例**：用 `name_display["en"].text` 做 embedding；入库时对原名做全角半角归一改写。
- **校验点**：`pytest tests/v04/schema/test_i4_names.py -q`（写后读回字节等同）+ 静态扫描（embedding 与检索调用点仅引用 native 字段，纳入 I18N-02 扫描器规则集）。
- **违反时**：写路径校验拒绝对 name_native 的改写（真件为非 frozen dataclass，权威性由校验与测试保证）；扫描命中 → CI 红。

### PRINCIPLES#B8 name_display 派生且次要

- **规则**：`name_display[lang]` 为机翻派生，MUST 带 `translated=True` 与 `translator` 标记；UI 上只能是次要行（字号与层级低于原名），NEVER 单独出现或与原名平级。
- **反例**：卡片主标题显示英文译名、原名收进 tooltip。
- **校验点**：`pytest tests/v04/schema/test_i5_translated_text.py -q`（必填标记）+ `cd web && npm test -- --run components/native-name`（主行==native、次要行带机翻标记断言）。
- **违反时**：schema 校验失败；组件测试红。

### PRINCIPLES#B9 引文原文不翻译

- **规则**：event 文本 / 日期 / 引语的存储字段保留来源语言原文；译文只存 `*_display` 派生槽（TranslatedText）。
- **反例**：ingest 时统一翻成中文写入原文字段。
- **校验点**：`pytest tests/v04/schema/test_i6_original_display.py -q`（日文 fixture 入库后原文字段字节等同；派生槽独立存在）。
- **违反时**：ingest 拒绝该条并落 DegradationNote。

### PRINCIPLES#B10 接地校验只对原文

- **规则**：接地增强(a) 的一致性校验（event 文本/日期与被引卡一致）输入 MUST 为原文字段；译文 NEVER 参与比对；报告以译文呈现引用时，出处槽 MUST 可展开到原文。CitationAligner 两段（verdict/draft）同受此约束。
- **反例**：对 `event_text_display["en"]` 跑一致性比对；报告引文只给译文且无原文展开。
- **校验点**：`pytest tests/v04/region/test_grounding_original_only.py -q`（对派生槽调用接地入口 → 抛 `GroundingOnTranslationError`）+ `cd web && npm test -- --run components/quote-slot`（译文引用带原文展开断言）。
- **违反时**：接地调用抛 `GroundingOnTranslationError`；含未展开译文引用的 Block 标 `needs_review`，导出按 blocking 拦截。

---

## §4 Schema 增量（I 组 · contracts_v04/）

> **副本与对账策略**：新目录 `contracts_v04/` 存 `models_v04.py` 与 `protocols_v04.py`；原 `contracts/` 只读零触碰。真件已于第 4 轮核实（指纹与逐项落点 → `docs/schema_reconcile_prefill_v04.md`）；本节仍保持「**零猜测增量**」书写形态（新类型完整定义、既有类只写纯新增字段块），落点已按真件预填。SCHEMA-00 在仓库内对工作副本复核：`tools/check_frozen_additive.py` 断言 v0.3.3 全部符号与字段在 v04 副本中原样存在、只加不删；落点类名与本节假设不符 → 写 `CONFLICTS-v04.md` 并按对照表映射，NEVER 静默改名。
> **风格**：与冻结件同法——**非 frozen 的 `@dataclass`** + `Literal` 判别 + 中文 docstring 携 `[审N]/[D*]` 出处标（真件核实）；下述代码为 v04 副本中的**增量区**内容。

### I1 枚举（新增）

```python
Region = Literal["CN", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"]
"""九地区，无 EU（清单 A2）。决定数据源选集与热点集合，与语言正交 [PRINCIPLES#A3]。"""

SystemLanguage = Literal["zh", "en"]
"""系统语言，仅此两种，zh 默认（A1）。统治全站 UI 与生成内容语言 [PRINCIPLES#A3]。"""

AuthorityTier = Literal["official", "mainstream", "industry", "community", "unknown"]
"""四级权威度 + unknown 缺省态（§2 不符 #11）。unknown 证据 NEVER 满足判 A/B 必要条件（B2 后半，REGION-03 前置门）。"""

FetchLegalStatus = Literal["allowed", "unknown", "restricted"]
"""抓取合规状态（B11），默认 unknown；restricted 拒绝抓取任务（REGION-07）。各国合规结论待 K2。"""
```

### I2 溯源增量（修改 · 落点 `Doc`，真件已核；`TrendItem.region: str` 既存保留）

```python
# —— v0.4 纯新增字段块（挂接 Doc；真件 Origin 为选题入口五类，与文档溯源无关 → 落点修正见预填表）——
    region: Region
    source_country: str          # ISO 3166-1 alpha-2；与 region 独立（他国源不隔离 [PRINCIPLES#B4]）
    authority_tier: AuthorityTier = "unknown"
    fetch_legal_status: FetchLegalStatus = "unknown"
```

### I3 `SourceRegistry`（新增）

```python
@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    region: Region
    source_country: str
    authority_tier: AuthorityTier
    fetch_legal_status: FetchLegalStatus
    enabled: bool = True

@dataclass(frozen=True)
class SourceRegistry:
    """region → 源清单，热插拔（B1）。种子 MUST 为空表——九国清单待 K1，准入标准随 REGION-01 文档给出；
    NEVER 自行编造网站清单（编造的名单比空表更糟）。select(region) 空表时走 E6「该区当日缺数据」降级行。"""
    entries: tuple[SourceEntry, ...]
```

### I4 名称三元组（修改 · 落点 `Cluster`，真件已核；canonical_name 保留，关系由 REGION-04 命名规则成文；TopicSeed 无名称字段不动）

```python
# —— v0.4 纯新增字段块 ——
    name_native: str                                      # 唯一权威值 [PRINCIPLES#B7]
    name_lang: str                                        # BCP-47 来源语言码
    name_display: dict[SystemLanguage, "TranslatedText"]  # 派生次要行 [PRINCIPLES#B8]
```

### I5 `TranslatedText`（新增）

```python
@dataclass(frozen=True)
class TranslatedText:
    text: str
    translated: bool          # MUST True（人工校订流后置；本轮恒机翻）
    translator: str           # 服务标识 + 版本；选型待 K4，本轮 fixture/identity 实现
    source_field: str         # 派生自哪个原文字段（接地禁入判据 [PRINCIPLES#B10]）
```

### I6 引文原文/派生分离（修改 · 落点 `WhyNowEvidence` 与 `Citation`，真件已核）

```python
# —— v0.4 纯新增字段块：原文字段保持不动（B9）——
# WhyNowEvidence（现有 event/event_date/citation_id）：
    event_display: dict[SystemLanguage, TranslatedText] | None = None
# Citation（现有 citation_id/doc_id/locator/quote_span）：
    quote_span_display: dict[SystemLanguage, TranslatedText] | None = None
# event_date 为 date 类型：无原文文本，本地化在渲染层，NEVER 设 display 槽（预填表收敛）。
```

### I7 产物语言（修改 · 落点 `Deliverable` 与 `Block`）

```python
# —— v0.4 纯新增字段块 ——
    lang: SystemLanguage
# 不变量：同一 Deliverable 内所有 Block.lang 与 Deliverable.lang 一致（I12 附随断言，随 test_i7 落）。
```

### I8 图谱三实体（新增）

```python
NodeRole = Literal["primary", "secondary", "auxiliary"]

@dataclass(frozen=True)
class GraphNode:
    node_id: str
    graph_id: str
    source_kind: Literal["cluster", "topic", "favorite"]   # 卡片入台来源（F1/E1）
    source_id: str
    role: NodeRole = "auxiliary"
    x: float = 0.0
    y: float = 0.0

@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    graph_id: str
    from_node_id: str
    to_node_id: str
    hypothesis: str      # MUST 非空（F8；服务端 422 EMPTY_HYPOTHESIS）；通道复用 combo hypothesis（§6-H8）

@dataclass(frozen=True)
class WorkbenchGraph:
    """底层统一有向图（F13）；树视图只是以 primary 为根的 BFS 布局投影，NEVER 另一种存储。"""
    graph_id: str
    owner_scope: "Principal"
    title: str
    archived: bool = False       # 归档交互待 K6；数据层先行
```

### I9 `Favorite`（新增）

```python
@dataclass(frozen=True)
class Favorite:
    favorite_id: str
    owner_scope: "Principal"
    source_kind: Literal["cluster", "topic"]
    source_id: str
    region: Region
    verdict_at_save: str | None       # 收藏当时判定（D4 排序维度）
    evidence_snapshot: "JSON"         # 冻结当时证据卡（D2 基线=内嵌副本；§9-P1 采纳则改 snapshot_id+pin）
    snapshot_stale: bool = False      # 源头变化打标（D3，接 §6-H1）
    created_at: str = ""
```

### I10 `TemplateRecord`（新增 · G5 注册表项）

```python
@dataclass(frozen=True)
class TemplateRecord:
    template_id: str
    version: int
    source_mock_id: str                 # 固化自哪份样板（G3）
    slots: tuple[str, ...]              # {{block:id}} / {{t:key}} 插槽清单
    checksum: str                       # 固化校验通过时的内容哈希（G4）
    registered_at: str
```

### I11 分享（新增）

```python
ShareTarget = Literal["workbench", "friend", "link"]

@dataclass(frozen=True)
class ShareLink:
    token: str
    target_kind: Literal["favorite", "cluster", "deliverable", "workbench_readonly"]
    target_id: str
    expires_at: str | None = None       # E4
    password_hash: str | None = None    # E4；明文 NEVER 落库
# friend 通道：接口占位，实现 MUST 抛 NotImplementedError("friends: post-v1")（E2 缝）。
```

### I12 三条不变量（新增 · 测试即规范）

`tests/v04/schema/test_i12_invariants.py`，三个测试函数 MUST 存在且通过：

1. `test_primary_unique` —— 同一 graph 设第二个 primary 时，前一个自动降 secondary，图内 primary 计数恒 ≤1（F6 存储层保证；UI toast 在 GRAPH-06）。
2. `test_hypothesis_nonempty` —— 空串/全空白 hypothesis 的 GraphEdge 构造与持久化均被拒绝（F8）。
3. `test_graph_change_derives_stale` —— 图谱节点/边变更事件 → 关联 Deliverable 派生 stale 标记（纯函数层验证派生逻辑；运行时接线走 §6-H1，DESIGN-25 验）。

### I13 分析上下文（修改 · 核实新增，owner_review: true）+ 币种核实

```python
# —— AnalysisContext v0.4 纯新增字段块（现有 project_id/budget_cny/locale；A3 端到端 + C11）——
    lang: SystemLanguage
    region: Region
# locale: str 保留兼容；v04 docstring 注记「v0.4 起 lang/region 为权威（A3），locale 由 lang 派生填充」。
```

**PricingRecord：无需增量**——真件已含 `currency: str` 与 `region: str`（J9 收敛为核实登记；SCHEMA-14 只做存在性断言 + price_entries 表列核对；汇率与分档 NEVER 本轮 → K8）。

### 事件与作业增量（models_v04 为落点 · SCHEMA-13；真件核实 JobKind 与 payload 判别类均在 models.py，protocols_v04 仅 docstring 增补）

`JobKind`（现七值：gate1_analysis/report/proposal/spec_export/revalidation/daily_ingest/pricebook_scan）增：`translate`、`design_generate`、`template_solidify`。payload 判别联合（现四成员 StatusChanged/StepEvent/PartialBlockEvent/JobFailedEvent）增七成员（事件名 = SSE 事件契约，H4 约束：NEVER 只在前端约定）：

| 事件 | 载荷要点 | 用途 |
|---|---|---|
| `design_delta` | `{chunk, offset}`；ephemeral 位见 §9-P3 | G7 流式渲染 |
| `design_tool_call` | `{call_id, name, state}` | G8 时间线 |
| `design_clarify` | `{question_id, options, allow_delegate}` | G9 澄清卡 |
| `design_check` | `{check_id, state: "passed"|"failed"|"unreported"}` | G19 三态；unreported NEVER 渲染成 passed |
| `translate_progress` | `{done, total}` | 批量派生 |
| `solidify_result` | `{template_id?, violations[]}` | G3/G4 |
| `graph_stale_notice` | `{deliverable_id, changed_kind}` | G32/G33：只提示，NEVER 自动重跑 |

---

## §5 功能实现设计（A~G 逐项：数据流 / 端点·SSE / 前端状态 / 边界降级 / 可执行验收）

> 写法约定：每项一行五要素；「验收」列 = 负责卡 id + 该卡 verify_cmd（一处定义：命令全文以 tasks-v04.json 为准，本节同文引用）。端点全部挂 E3 既有组的增量位（§2 不符 #8）。前端状态一律 zustand store + 服务端真相（乐观更新仅限位置类）。

### A 组 · 语言系统（8 项）

| 项 | 数据流 / 端点 | 前端状态 | 边界与降级 | 验收 |
|---|---|---|---|---|
| A1 zh/en 全站 | next-intl locale 路由，zh 默认 | locale 由 profile 驱动 | 未登录用默认 zh | I18N-01 `cd web && npm test -- --run lib/i18n` |
| A2 九地区 | `Region` 枚举（I1）贯穿 | region 存 prefs store | 枚举外值 422 | SCHEMA-01 `pytest tests/v04/schema/test_i1_enums.py -q` |
| A3 正交 | PRINCIPLES#A3 | lang/region 两个独立槽 | 派生行为抛 OrthogonalityViolation | I18N-07 `python tools/orthogonality_check.py --combos all` |
| A4 key 化 | 文案全走 message catalog | — | 组件目录 CJK 字面量=0（白名单推进制） | I18N-02 `node tools/i18n_scan.mjs web/components --fail-on-cjk` |
| A5 持久化 | `GET/PUT /profile/prefs {lang, region}` | prefs store 以服务端为真相 | NEVER localStorage（跨设备一致断言） | I18N-06 `pytest tests/v04/i18n/test_profile_prefs.py -q && cd web && npm test -- --run stores/prefs` |
| A6 生成语言 | AnalysisContext.lang（I13）→ Deliverable.lang（I7） | 分析页语言=系统语言 | lang 不一致的 Block 拒绝落库 | SCHEMA-07 `pytest tests/v04/schema/test_i7_lang.py -q` |
| A7 翻译降级 | Translator 协议 + fixture 实现 | 卡片退 name_native 单行 | E6 新行：不阻断 | I18N-03 `pytest tests/v04/i18n/test_translator.py -q` |
| A8 组合矩阵 | 18 组合 harness（A3 校验点） | — | 任一组合破 4 断言 → CI 红 | I18N-07（同上） |

### B 组 · 多地区数据（B1~B11；B12/B13 → §7-K1/K2）

| 项 | 数据流 / 端点 | 前端状态 | 边界与降级 | 验收 |
|---|---|---|---|---|
| B1 源注册表 | SourceRegistry.select(region)（I3）；ingest 读表 | — | 空表 → 当日该区缺数据角标（E6 新行） | REGION-01 `pytest tests/v04/region/test_registry.py -q` |
| B2 权威度 | I1 五值枚举；入库必填默认 unknown | 卡片辅助信息位 | unknown NEVER 满足判 A/B 必要条件 | REGION-02 + REGION-03 `pytest tests/v04/region/test_unknown_tier_gate.py -q` |
| B3 强度三尺 | authority 轴接入 axis 体系（记于 EvidenceScore.components） | — | 权重中性 1.0 标 revisit（K3）；金标回归守护 | REGION-06 `pytest tests/v04/region/test_scorer_axis.py -q` |
| B4 不隔离 | PRINCIPLES#B4 | — | 见原则「违反时」 | REGION-01 + REGION-08 |
| B5 分桶聚类 | 聚类前按 region 分桶；簇血缘加 region | — | 违反 → 该区当日作业 failed | REGION-04 `pytest tests/v04/region/test_cluster_bucketing.py -q` |
| B6 同事件组 | `POST/DELETE /clusters/same-event-group` 显式建解 | 关联标签展示 | NEVER embedding 自动建组 | REGION-05 `pytest tests/v04/region/test_same_event_group.py -q` |
| B7 原名权威 | PRINCIPLES#B7 | 主行恒 native | — | SCHEMA-05 `pytest tests/v04/schema/test_i4_names.py -q` |
| B8 译名派生 | translate JobKind 批量派生 name_display | 次要行 + 机翻标记 | 翻译不可用走 A7 | I18N-04 `pytest tests/v04/i18n/test_name_display.py -q && cd web && npm test -- --run components/native-name` |
| B9 引文原文 | PRINCIPLES#B9；I6 派生槽 | 引用槽默认按系统语言 | — | SCHEMA-06 `pytest tests/v04/schema/test_i6_original_display.py -q` |
| B10 接地原文 | PRINCIPLES#B10；MIGRATE-01 规格 | 译文引用可展开原文 | GroundingOnTranslationError | REGION-02 附随 `pytest tests/v04/region/test_grounding_original_only.py -q` + I18N-05 |
| B11 抓取合规 | I2 fetch_legal_status 门 | — | restricted 拒任务；结论待 K2；fixture-only 网络护栏 | REGION-07 `pytest tests/v04/region/test_fetch_legal_gate.py -q` |

### C 组 · 热点广场卡片化（11 项）

- **C1~C5 卡片本体**：数据流 = `GET /plaza/hot?region=&day=` 返回簇卡（name_native 主行 + name_display 次要行 + 左上日期 + 地区标 + stale 徽章 + Gate① 判定标）；右下动作区三独立按钮（收藏/入台/分享），卡片主体点击 → 分析界面，动作区在点击排除区。降级：字段缺失逐槽隐藏 NEVER 占位假数据。验收：HOTSPOT-01 `cd web && npm test -- --run components/hotspot-card`；HOTSPOT-02 `…/hotspot-card-actions`（三 handler 独立触发 + 冒泡阻断断言）。
- **C6/C7 分析界面骨架 + 默认态**：进入即展示 Gate① 已有判定与证据概览（零新计算）；界面语言=系统语言（C11）。验收：HOTSPOT-03 `cd web && npm test -- --run views/analysis && pytest tests/v04/hotspot/test_analysis_view_api.py -q`。
- **C8 AI 分析按钮**：`POST /analysis/deep {cluster_id}` → JobRunner 深度档；预算与付费落点参数化（免费/付费路线待 K7，按钮态可配置）。LLM 恒 mock 注入。验收：HOTSPOT-04 `pytest tests/v04/hotspot/test_deep_job.py -q`。
- **C9 结果缓存**：同参（cluster_id+lang+档位+账本版本）二次点击 → 0 新 job、0 计费，直接回缓存。验收：HOTSPOT-05 `pytest tests/v04/hotspot/test_analysis_cache.py -q`。
- **C10 时效性**：缓存结果过 Revalidator 通道判 stale（§6-H1 适配器，NEVER 新写比对逻辑——测试断言 import 来源）。验收：HOTSPOT-06 `pytest tests/v04/hotspot/test_analysis_stale_adapter.py -q`。
- **C11 语言绑定**：AnalysisContext.lang = profile.lang（I13）。验收：SCHEMA-14 `pytest tests/v04/schema/test_i14_ctx_currency.py -q`。
- **信息源列表**（C 组尾）：by_source ≥2 列独立渲染，无合成句（PRINCIPLES#B4）。验收：HOTSPOT-07 `cd web && npm test -- --run components/source-columns`。

### D 组 · 收藏图书馆（7 项）

- **D1/D2 收藏写路径与冻结**：`POST /favorites` 落 Favorite（I9），evidence_snapshot 当场内嵌冻结（基线路径；§9-P1 采纳则改 pin）。改源 fixture 后快照字节不变断言。验收：FAV-01 `pytest tests/v04/fav/test_snapshot_freeze.py -q`。
- **D3 stale 与双动作**：源头变化（H1 diff）→ snapshot_stale=True；UI「查看当时版本 / 更新到最新」两动作，后者 `POST /favorites/{id}/refresh-snapshot` 生成新快照（旧值保留在历史）。验收：FAV-02 `pytest tests/v04/fav/test_snapshot_stale.py -q`。
- **D4 卡片墙 + 排序**：`GET /favorites?sort=` 四维（created_at / region / verdict_at_save / in_workbench）。验收：FAV-03 `cd web && npm test -- --run views/library`。
- **D5 筛选搜索**：region / verdict / 日期区间三过滤器组合。验收：FAV-04 `cd web && npm test -- --run views/library-filters`。
- **D6 批量操作**：`POST /favorites/batch {op: add_to_workbench|remove, ids}`——入台批量为单事务（部分失败整体回滚 + 报错清单）。验收：FAV-05 `cd web && npm test -- --run views/library-batch && pytest tests/v04/fav/test_batch_ops.py -q`。
- **D7 空态**：引导去热点广场（i18n key 化文案）。验收：FAV-06 `cd web && npm test -- --run views/library-empty`。

### E 组 · 分享（4 项）

- **E1 一键入台**：分享菜单第一项调 `POST /workbenches/{id}/nodes {source_kind:"cluster"|"favorite", source_id}`（与 F1 同端点，零新链路）。验收：HOTSPOT-09（含 GRAPH-02 API 调用断言）。
- **E2 分享给朋友（缝）**：菜单项存在但触发 `NotImplementedError("friends: post-v1")` → 前端渲染「即将上线」态；schema 缝在 I11。验收：SCHEMA-11 `pytest tests/v04/schema/test_i11_share.py -q` + HOTSPOT-09 `cd web && npm test -- --run components/share-menu && pytest tests/v04/share/test_friend_stub.py -q`。
- **E3 只读外链**：`POST /share-links` 出 token；`GET /share/{token}` 以匿名 viewer Principal 走**既有**鉴权中间件（§6-H2；NEVER 新建鉴权分支）。越权 fixture：token 只能读 target，改写请求 403。验收：HOTSPOT-08 `pytest tests/v04/share/test_link.py -q`。
- **E4 过期与密码**：expires_at 过期 → 410；password_hash 校验失败 → 401；明文 NEVER 落库。验收：HOTSPOT-08（同卡覆盖）。

### F 组 · 热点工作台图谱（19 项）

| 项 | 设计要点 | 验收 |
|---|---|---|
| F1 拖卡入台 | 广场/图书馆卡 → `POST /workbenches/{id}/nodes`；去重（同 source 二次入台幂等返回既有节点） | GRAPH-02 `pytest tests/v04/graph/test_store.py -q` |
| F2 节点渲染 | native 主行 + region/日期/stale/判定辅助槽（复用 HOTSPOT-01 卡片子组件） | GRAPH-03 `cd web && npm test -- --run components/graph-node` |
| F3 拖动 | rAF 节流本地移动，松手 `PATCH …/nodes/{nid} {x,y}` 落盘；失败回弹 | GRAPH-04 `…/graph-drag` |
| F4 双击开分析 | 节点双击 → 抽屉式分析面板（HOTSPOT-03 复用），不离台 | GRAPH-05 `…/graph-open-analysis` |
| F5/F6 角色与主唯一 | 右键菜单设 primary/secondary/auxiliary；服务端保证 primary ≤1，旧主自动降级 + toast（NEVER 弹确认对话框） | GRAPH-06 `cd web && npm test -- --run components/graph-roles && pytest tests/v04/graph/test_primary_unique_runtime.py -q` |
| F7/F8 连线强制假设 | 松手弹假设输入框；空值不落盘（前端）+ 422 EMPTY_HYPOTHESIS（服务端，双保险）；通道复用 combo hypothesis（§6-H8） | GRAPH-07 `cd web && npm test -- --run components/graph-edge && pytest tests/v04/graph/test_edge_hypothesis.py -q` |
| F9/F10 空假设阻断 + 摘要条 | 存在空假设边 → 生成按钮置灰 + 计数徽章 + 点击高亮定位；AI 栏顶部摘要条列 primary/边数/假设完整度 | GRAPH-08 `…/graph-generate-gate` |
| F11 框选批量 | 拖框 + ⌘A + 批量设角色（主唯一约束在批量路径同样生效） | GRAPH-09 `…/graph-multiselect` |
| F12 力导向 | 手写一次性布局（迭代收敛即停，NEVER 持续 rAF 模拟；节点 ≤50 规模） | GRAPH-11 `cd web && npm test -- --run lib/graph-layout` |
| F13/F14 树视图投影 | 同一存储双投影：树 = primary 为根 BFS；未连接节点入「未连接」区；两视图数据一致性断言 | GRAPH-12 `…/views/graph-tree` |
| F15 无模式切换 | **隔离带卡**：页签（图谱/树）+ 常驻可折叠 AI 栏；状态树无 mode 键（断言 store 键集）；「默认/AI」保留为预设组合文案层 | GRAPH-16 `…/views/workbench-tabs`（owner_review，零下游） |
| F16 撤销共链 | 图谱操作与其它视图共用一条 undo 链（单栈跨视图断言） | GRAPH-10 `cd web && npm test -- --run lib/undo` |
| F17 移动端只读 | 触摸端禁拖禁连，可看可点开分析 | GRAPH-13 `…/views/graph-mobile` |
| F18 多工作台 | 数据层多台 + archived 字段先行；UI 单台自动创建，多台入口 flag off（交互稿待 K6） | GRAPH-14 `pytest tests/v04/graph/test_multi_workbench_store.py -q` |
| F19 空态 | 从广场拖入引导 | GRAPH-15 `…/views/workbench-empty` |

（F 组容器/路由：GRAPH-01 `cd web && npm test -- --run views/workbench-shell`，对 F15 两方案中立。）

### G 组 · AI 设计工作台（35 项，两阶段模型）

**探索期（G1 几乎无约束）**：
- G7 对话生成 + 流式：`POST /design/sessions {workbench_id, model, effort}` → design_generate job；SSE design_delta 边到边渲染（NEVER 等整回合）；replay 语义 → §9-P3。验收：DESIGN-01 `cd web && npm test -- --run design/chat-panel && pytest tests/v04/design/test_stream_events.py -q`。
- G10 渲染管线：iframe.srcdoc 直挂 HTML，禁 Babel/构建器（import 黑名单断言）。DESIGN-02 `…/design/renderer`。
- G11 三接口抽象：HtmlRenderer/HtmlPatcher/HtmlExporter 唯一实现；Jsx* 同名接口存在但抛 NotImplementedError。DESIGN-03。
- G12 设计系统挂载：`_ds` 资产挂 `web/public/_ds`，样板引用而 NEVER 新建 token。DESIGN-04；G15 两处修复 → DESIGN-05 `node tools/scan_ds_assets.mjs web/public/_ds --tabular-nums --no-warn-emoji`。
- G8 工具时间线：30+ 调用折叠（折叠态高度 ≤40px 断言）。DESIGN-06。
- G9 澄清卡：每题「由你决定」+ 全局「全部由你决定」；未答复禁续输。DESIGN-07。
- G13 Tweaks：声明式参数面板走快路径（拖动只 patch CSS 变量，NEVER 重建 srcdoc——spy 断言）；改动按字节区间回写源码（缩进保持，diff 最小）。DESIGN-08；禁用词表（evidence/confidence/threshold/filter/hide/count 六词参数名拒绝提取）DESIGN-09。
- G14 直接编辑：data-loc 定位；落点顺序 工具类 → inline style → NEVER 全局 CSS；导出剥 data-loc。DESIGN-10。
- G16 版本历史：检查点 = 模板 VFS + 图谱状态同快照；恢复=新检查点（NEVER 破坏历史）。DESIGN-11 `pytest tests/v04/design/test_checkpoints.py -q`。
- G17 评论批注：data-loc 锚定，元素消失降级坐标锚；「让 AI 处理」→ 该评论入下一 job 上下文。DESIGN-12。
- G19 后台检查三态：passed/failed/unreported 三态可视区分（aria + class 断言）；unreported NEVER 渲染成 passed。DESIGN-13。
- G18 演示模式：全屏、隐 chrome、方向键翻页。DESIGN-14。
- G23 模型选择：模型列表读环境配置，代码零硬编码模型名（扫描器）；推理强度档位透传。DESIGN-17 `cd web && npm test -- --run design/model-picker && node tools/no_hardcoded_models.mjs web`。
- G24 用量记录：token 用量与耗时入 job 元数据。DESIGN-18。
- G25 多页面：L0 概览/章节页结构；375px 无横滚（容器断言）。DESIGN-19。
- G26 依赖白名单：样板内第三方引用仅限白名单，越界剥除 + 报错。DESIGN-20。
- G27 字体自托管：外部字体 URL 扫描为零。DESIGN-21 `node tools/no_external_fonts.mjs web`。
- G28 快捷键：⌘⏎ 发送 / ⌘Z 撤销 / ⌘\ 收 AI 栏 / ⌘1⌘2 切页签 + ⌘K 命令面板。DESIGN-22。
- G29/G30 禁置信度可视化 + 图标纪律：进度条只准绑 JobView.progress 或骨架屏（lint 规则）；图标统一 lucide 线性，emoji NEVER 当图标。DESIGN-23 `node tools/lint_no_confidence_viz.mjs web`。
- G31 无障碍：全键盘可达、focus-visible、prefers-reduced-motion 动效归零。DESIGN-24。
- G32/G33 图谱联动：图谱变更 → graph_stale_notice → 样板标黄「基于旧图谱」；G33 NEVER 自动重跑，只给「查看差异 / 重新生成」。DESIGN-25（复用 §6-H1）+ DESIGN-26 反向高亮（节点 ↔ 首个引用 Block 滚动定位）。
- G20 导出：HTML 单文件 / PDF / vibe_pack+计划书 zip 全部走既有导出管线（§6-H3；import 来源断言）。DESIGN-15。

**样板可辨识（G2 · 隔离带）**：占位语法强制（数字 `XX.X%`、来源 `[来源待补]`/`SRC-XXXX`）+ 页面水印 + 文件名 `-mock` 后缀；「水印不可移除」的可执行化 = 渲染器与导出器检测水印节点缺失即拒绝。DESIGN-27 `cd web && npm test -- --run design/mock-identity`（owner_review）。

**固化期（G3~G6）**：
- G5 注册表（非隔离）：模板 CRUD + 版本 + 复用列表。DESIGN-30 `pytest tests/v04/design/test_template_registry.py -q`。
- G3 固化管道（隔离）：`POST /design/solidify {mock_id}` → 示例内容替换为 `{{block:id}}` / `{{t:key}}` 插槽 → 注册 G5。DESIGN-28（owner_review）。
- G4 固化校验器（隔离）：插槽完整 / 无残留示例占位（语法表与 G2 共享 fixture）/ 无水印残留 / 插槽类型与 Block 类型对齐；违规拒绝并指出行号（反例 fixture 断言实际输出）。DESIGN-29（owner_review）。
- G6 生产渲染门（隔离）：生产路径只接受已注册模板；任意 HTML 尝试 → 拒绝。两路径（探索渲染/生产渲染）共用 Renderer 接口不同实现。DESIGN-31（owner_review）。
- G22 扩展（隔离）：导出闸门增「模板未固化」判据（在 DESIGN-16 基线判据之上）。DESIGN-32（owner_review）。
- 闸门基线（非隔离）：fact_removed=blocking 沿审11 + 空假设边 → 拒绝导出并列阻塞项。DESIGN-16 `pytest tests/v04/design/test_export_gate_base.py -q`。

---

## §6 复用清单（H 组 8 项 · 新写即违规）

> 每项：已有实现定位 → 本次接法 → 「不新写」的机器断言方式。工作 AI 若判断确需新写，MUST 停下（blocked）写论证待 owner 批（D2 rules 同款约束）；NEVER 先写了再论证。

| # | 复用什么 | 已有定位（真件核实） | 本次接法 | 「不新写」断言 |
|---|---|---|---|---|
| H1 | 快照/差异比对 | protocols.py `Revalidator` + `LedgerStore.diff`（changed→advisory、removed→blocking） | 收藏 stale（FAV-02）、分析时效（HOTSPOT-06）、Deliverable 图谱联动（DESIGN-25）三处各写**薄适配器** | 适配器测试断言比对逻辑 import 自 contracts 通道；`grep -R "def .*diff" flint/` 无新比对实现 |
| H2 | 鉴权 | E3 既有 JWT 中间件 + `Principal`→owner_scope | 外链 viewer=匿名 Principal 子类型走同一中间件（HOTSPOT-08） | 路由表断言 share 端点挂同一 auth dependency；无新中间件文件 |
| H3 | 导出管线 | `ReportComposer`/`Renderer` + 导出门禁 [审11] | 设计台三种导出（DESIGN-15）与闸门扩展（16/32）挂既有管线 | `pytest tests/v04/design/test_export_reuse.py -q`（导出调用栈 import 断言） |
| H4 | SSE 事件流 | `JobEventStream`（seq 单调 + replay + 心跳 15s） | 新事件只增 payload 判别成员（SCHEMA-13）；NEVER 新开 SSE 通道 | 事件注册表单一来源测试；前端 EventSource 构造点唯一 |
| H5 | 撤销栈 | 前端说明 2.x 既有 undo 链 | 图谱操作入同一链（GRAPH-10） | store 断言全局 undo 栈实例唯一 |
| H6 | by_source 分列 | 四列独立机制（by_source 不合成） | region 维度并入分列（REGION-08、HOTSPOT-07） | 合成句黑名单测试沿用 + 列数 ≥2 断言 |
| H7 | 任务/作业系统 | `JobRunner`（幂等键/重试/超时/审计） | translate、design_generate、template_solidify 三种 JobKind 注册进既有 runner | runner 注册表测试：新 kind 在表、无新 runner 类 |
| H8 | **假设通道（核实新增）** | TS-002：Origin combo 校验（card_ids 2~5、hypothesis 必填）+ `POST /projects/combo` + origins/topic_seeds 表 | F8 边假设复用同一 hypothesis 校验函数与存储惯例（GRAPH-07）；E1 入台节点 source 引用同一实体 id 体系 | 边校验测试断言校验函数 import 自 combo 通道模块 |

## §7 未决项（K 组 · 缺什么就留位绕行，NEVER 编造）

| # | 未决项 | 需要谁的什么输入 | 留空绕行方式（本轮可交付态） | 解决后影响的卡 |
|---|---|---|---|---|
| K1 | 九国源清单 | owner 提供各国具体源站清单（或授权按 REGION-01 准入标准调研后人审） | SourceRegistry 空表种子 + fixture 源跑通全链；空表走 E6 缺数据行 | REGION-01/02/04、I18N-08、HOTSPOT-01 |
| K2 | 抓取合规结论 | owner/法务出各国 robots 与 ToS 合规结论 | 全部源 fetch_legal_status=unknown；restricted 门已生效待填值 | REGION-07 |
| K3 | authority 权重 | 金标数据重跑后 owner 定权重 | 三尺 axis 接入但 authority 权重=1.0（中性）+ `revisit(K3)` 代码标记 | REGION-06 |
| K4 | 翻译服务选型 | owner 定供应商与预算 | Translator 协议 + fixture/identity 实现；调用点单一集中 | I18N-03/04/05 |
| K5 | 英文 UI 文案审校 | 人工审校资源 | en catalog 全量机翻占位 + `"needs_review": true` 标记字段 | I18N-01（catalog 数据，不阻代码） |
| K6 | 多工作台交互稿 | owner 出交互设计 | 数据层与 archived 字段先行；UI 单台自动创建、多台入口 flag off | GRAPH-14 |
| K7 | 免费/付费路线 | prod_caliber 双语重跑数据（0.44 vs 0.90 悬置） | C8 深度分析按钮的计费落点参数化（配置开关），两态皆可运行 | HOTSPOT-04、MIGRATE-06 |
| K8 | 汇率与多币种分档 | owner 定价策略 | currency 字段落库（默认 CNY）；换算与分档不实现 | SCHEMA-14、MIGRATE-07 |

> 附注（不占 K 编号）：三份 vibe_pack 样例已按 owner 指示搁置不使用（§1），无待决项。

---

## §8 分阶段实施路线（V0~V5 · 每阶段出口 = 命令清单绿）

> 卡集合与依赖以 tasks-v04.json 为唯一机读真相；本节给阶段口径。cycles 合计与关键路径由 `tools/validate_dag_v04.py` 计算并写入 dag_report（生成时实测值见 tasks-v04.json 首键）。**硬顺序**：V0（PRIN+MIGRATE）全绿前，任何 SCHEMA/功能卡 NEVER 开工（DAG 以 SCHEMA-00 依赖 V0 全集编码，validator 有专项断言）。

| 阶段 | 卡集合 | 张数 | 出口判据（全部 exit 0） |
|---|---|---|---|
| V0 原则与返工 | PRIN-01/02 + MIGRATE-01~07 | 9 | `python tools/check_principles_doc.py docs/PRINCIPLES-v04.md` · `python tools/check_grounding_spec.py docs/grounding_spec_v04.md` · `python tools/check_techplan_delta.py docs/技术方案-v1.2-delta.md` · `python tools/check_fe_doc.py docs/前端功能说明-v2.md --min-screens 16` · `python tools/validate_dag_v04.py --base tasks.json --patch tasks-m1m4-v04-patch.json --merged` · 两份 impact 文档结构校验 |
| V1 Schema | SCHEMA-00~14 | 15 | `python tools/check_frozen_additive.py contracts/models.py contracts_v04/models_v04.py` · 同 protocols · `pytest tests/v04/schema -q` |
| V2 地区+语言 | REGION-01~08 + I18N-01~08 | 16 | `pytest tests/v04/region tests/v04/i18n -q` · `python tools/orthogonality_check.py --combos all` · `node tools/i18n_scan.mjs web/components --fail-on-cjk` |
| V3 广场+收藏+分享 | HOTSPOT-01~09 + FAV-01~06 | 15 | `pytest tests/v04/hotspot tests/v04/fav tests/v04/share -q` · `cd web && npm test -- --run components views` |
| V4 图谱工作台 | GRAPH-01~16 | 16 | `pytest tests/v04/graph -q` · `cd web && npm test -- --run components/graph-node components/graph-edge lib/undo lib/graph-layout views` |
| V5 设计工作台 | DESIGN-01~32 | 32 | `pytest tests/v04/design -q` · `cd web && npm test -- --run design` · 全局门 `ruff check . && mypy --strict src && pytest -q` |

**总量口径（J8）**：本包 103 卡，**实测 Σ122 cycles、关键路径 18 cycles**（PRIN-01→MIGRATE-02→MIGRATE-03→SCHEMA-00→…→FAV-02，全文见 dag_report），144 条依赖边、self_review 50 张、owner_review 7 张；预算带 ±20%。全项目 = 基线 232 + 103 = 335 卡；FE 批次受影响 8~10 卡的返工在 V2 出口后按 `impacted_by_v04` 标定复估，NEVER 现在拍数。cycle 定义沿 CLAUDE.md：1 cycle = 一次「实现→verify→（自审）」闭环。

**隔离带（owner 可整体划掉、零下游破坏）**：`GRAPH-16`（F15）、`DESIGN-27`（G2）、`DESIGN-28/29`（G3/G4）、`DESIGN-31`（G6）、`DESIGN-32`（G22 扩展）。validator 断言：带外任何卡不依赖带内卡。划掉后 §11 各项给出替代方案。

---

## §9 三个方案级提案（每项 ①动机 ②方案 ③替代 ④影响面 ⑤成本 ⑥不采纳的后果；不进 D2 卡文，双路径差异见 tasks-v04.json.proposals）

### P1 收藏快照与 SnapshotStore 保留期冲突

① **动机**：protocols.py [F2] 规定快照保留 180 天、唯一豁免 RedactionRecord；D2「收藏=冻结快照」要求永存——直接复用 SnapshotStore 的收藏会在 180 天后被周删任务清掉。
② **方案（建议采纳）**：protocols_v04 给 SnapshotStore 增 `pin(snapshot_id, reason)` / `unpin`；GC 遍历跳过 pinned；Favorite 存 snapshot_id 引用。豁免面从「唯一 RedactionRecord」扩为「RedactionRecord + pinned」，属增量不破坏。
③ **替代（当前 D2 基线）**：Favorite 内嵌 evidence_snapshot 副本（I9 现状），零协议改动，代价是同一证据双份存储 + 与快照体系脱钩（后续 diff 要走内容比对而非 id 比对）。
④ **影响面**：SCHEMA-09、FAV-01、FAV-02 三卡；E2 snapshots 表 GC 语句一处。
⑤ **成本**：采纳 ≈ +1 cycle（pin 接口 + GC 条件 + 迁移注记）；不采纳 0。
⑥ **不采纳后果**：存储冗余可承受；真正的坑在「更新到最新」链路要维护两套快照语义，长期一致性维护成本更高。

### P2 导出闸门判据注册表

① **动机**：闸门判据正在增长：审11 fact_removed → v0.4 空假设边 → 隔离带「模板未固化」→ 可预见 ⑧ 推演还会加。散写在 Renderer 调用点会重演「一处语义多处实现」。
② **方案（建议采纳）**：protocols_v04 增 `ExportGate.register(criterion: GateCriterion)`；判据对象化（id、severity: blocking|advisory、check(deliverable, graph) → violations）；导出前统一遍历。
③ **替代（当前 D2 基线）**：判据写在导出调用点（DESIGN-16 基线 + DESIGN-32 追加），两处 if 链。
④ **影响面**：DESIGN-15/16/32 三卡内容微调；零新增卡。
⑤ **成本**：采纳 ≈ +0.5 cycle；不采纳 0。
⑥ **不采纳后果**：第三个判据出现时（大概率在 ⑧ 合入时）要做一次抽取重构，届时改动面比现在大。

### P3 design_delta 与 SSE replay 语义

① **动机**：H4 契约 = 事件可 replay 断线续传；G7 流式 delta 高频细粒，全量入 replay 会让断线重连回放海量 chunk，且 delta 对最终态无独立价值（终态在检查点 VFS）。
② **方案（建议采纳）**：JobEvent 增 `ephemeral: bool = False`；design_delta 标 ephemeral=True——不入 replay 日志；断线重连 = 拉最新检查点快照 + 从当前位置续流（复用既有「快照+续传」流程）。
③ **替代（当前 D2 基线）**：delta 全量入 replay，DESIGN-01 给 replay 读取加截断参数（最近 N 条）并在 trace 登记风险。
④ **影响面**：SCHEMA-13（ephemeral 位）、DESIGN-01（重连路径）两卡。
⑤ **成本**：采纳 ≈ +0.5 cycle；不采纳 0（但埋回放性能债）。
⑥ **不采纳后果**：长对话断线重连时秒级卡顿与内存峰值；事件日志膨胀（design 会话 delta 占比预计 >90%）。

---

## §10 登记不做项（三项 · 本轮 NEVER 动手）

1. **prod_caliber 重构**：12 金标场景增英文口径、免费档路线复评（0.44 vs 0.90）——待 V2 出口后以真实双语数据重跑再定（K7）。本轮只交 MIGRATE-06 影响声明。
2. **热点仓库历史数据迁移**：既有簇/热点无 region 与名称三元组——回填策略（默认 CN？重跑聚类？）影响面大，单独立项。本轮新数据双写新字段，旧数据只读兼容（查询层 region 缺省按 CN 兜底并标 `legacy: true`）。
3. **L 组监管 AI 语义**：L8（双 agent 分工）删除；L1~L7 以自审形式并入 D3 工作提示词与 SELFCHECK 清单，NEVER 实现监管 AI 组件。

## §11 三项 owner 建议判断（工单立场 + 理由 + 被划掉时的替代）

**① F15「无模式切换」——认同清单立场。** 视图=纯投影的架构让「模式」无处安放状态，避免 mode 字段与页签/AI 栏状态的双真相漂移；「默认模式/AI 模式」的用户心智完整保留在预设组合与文案层（默认=AI 栏折叠+图谱页签），不落状态机。GRAPH-16 按此实现并断言 store 无 mode 键。若 owner 坚持要 mode：替代 = **派生只读 mode**（由 页签×AI 栏折叠态 计算得出，不落盘、不进 schema、不可直写），UI 可展示「当前模式」徽章而系统仍单真相——该替代改动只落 GRAPH-16 一卡。

**② G2 样板可辨识——认同，且建议列为不可谈判项。** 燧石的立身之本是「每个数字有出处」；探索期样板里的示例数字一旦被截图外传当真报告，是品牌级事故而非 UI 瑕疵。三件套成本极低：`-mock` 后缀与水印近零成本，占位语法只是生成提示词里的一行约束；而「水印不可移除」已可执行化（缺水印 → 渲染/导出拒绝，DESIGN-27）。若 owner 划掉：保底替代 = 至少保留导出文件名 `-mock` 后缀 + 文件元数据标记（成本最低档），页面内水印可谈——但工单立场是三件套整取。

**③ G3 固化 + G6 生产只认模板——认同，这是两阶段模型的承重墙。** G0 立场修正给了探索期自由，其安全性完全押在固化闸门上：没有 G6，探索期的任意 HTML 会直接漏进生产渲染，两阶段退化为一阶段，G0 的「几乎无约束」就从特性变成事故通道。G3 插槽化让模板可版本、可复用，与 G5 注册表、G22 门禁、审11 blocking 语义构成闭环——全部复用既有机制，不新造。若 owner 划掉（G3/G6 同划）：替代 = 生产渲染接受任意 HTML 但强制过 G4 校验器扫描（无占位残留、无水印残留、引用 Block 均真实存在）——弱一档：挡得住裸示例正文，挡不住结构漂移与插槽错位；且 G22「模板未固化」判据须同步降级为 advisory。**明确不推荐**，仅作断腕预案。

---

## 附录 · 锚点索引（context_refs 可引用清单）

`WORKORDER-v04.md#1` 解冻依据 · `#2` 影响面（#2-J1…#2-J9）· `#3` 原则（PRINCIPLES#A3/#B4/#B5/#B7/#B8/#B9/#B10）· `#4` schema（#4-I1…#4-I13、#4-events）· `#5` 功能（#5-A…#5-G）· `#6` 复用（H1…H8）· `#7` 未决（K1…K8）· `#8` 路线 · `#9` 提案（P1/P2/P3）· `#10` 登记 · `#11` 判断。配套：`ASSUMPTIONS.md`（附件核实与绕行）· `tasks-v04.json`（含 dag_report/rules/proposals/isolation）· `worker.md`。

*工单完。数字均给出处；[待核实] 项以实物到位为准；空位以 K 组编号占位，NEVER 以编造填充。*
