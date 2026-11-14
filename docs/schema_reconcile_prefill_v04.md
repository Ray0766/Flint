# schema_reconcile_prefill_v04 · 对账预填表（依据 models.py 真件，第 4 轮上传）

> 指纹：1030 行 / 30783 B / md5 `380d7b5a7daee17111a8961f0e3a41c6`；含 v0.3.3 特征（TaskSpec.estimate_cycles/review_gate、Audience、ProposalContext、DeliverableType 含 vibe_pack）。
> 用途：SCHEMA-00 对账卡的预填输入。worker 仍 MUST 对仓库内 `contracts/models.py` 复跑 additive 校验——本表基于 owner 上传副本，仓库工作副本为最终权威；不符处照写 CONFLICTS-v04.md。
> 风格核实：真件为**非 frozen 的 `@dataclass`** + `Literal` + 中文 docstring + `[审N]/[D*]` 出处标；v04 增量区同风格（工单 §4 已由 frozen 改正）。

## 逐项落点（清单假设 → 真件核实）

| I 项 | 清单/工单原假设 | 真件核实落点 | 相邻真实字段（证据） | 增量内容（修正后） | 结论 |
|---|---|---|---|---|---|
| I1 四枚举 | 新增 | 新增（真件无同名） | — | Region / SystemLanguage / AuthorityTier / FetchLegalStatus | 照原案 |
| I2 溯源四字段 | 落 `Origin` | **落 `Doc`**；`Origin` 实为选题入口五类（combo/idea/domain/competitor/document，payload 含 combo{card_ids, hypothesis}），与文档溯源无关 | Doc: doc_id/source_id/kind/title/url/published_at/meta/origin/access | Doc 增 region/source_country/authority_tier/fetch_legal_status；`TrendItem.region: str` 已存在（采集态，保留不动，类型不收窄） | **落点修正** |
| I3 SourceRegistry | 新增 | 新增 | Doc.source_id 为接线点 | SourceEntry/SourceRegistry 照原案，空表种子 | 照原案 |
| I4 名称三元组 | 落 TopicSeed + 热点卡实体（名待定） | **落 `Cluster`**（热点卡实体=Cluster）；TopicSeed 无名称字段（keywords/hypothesis/context_text），不动 | Cluster: cluster_id/canonical_name/category_id/centroid/status/…/aliases | Cluster 增 name_native/name_lang/name_display；`canonical_name` 保留，与 name_native 的关系由 REGION-04 命名规则成文（native 为权威，canonical_name 兼容既有中文命名） | **落点修正** |
| I5 TranslatedText | 新增 | 新增 | — | 照原案（translated/translator/source_field） | 照原案 |
| I6 引文原文/派生 | event/date/quote 三 display 槽 | **`WhyNowEvidence` + `Citation`**；`event_date: date` 为日期类型无原文文本 → date display 槽**取消**（本地化在渲染层） | WhyNowEvidence: event/event_date/citation_id；Citation: citation_id/doc_id/locator/quote_span | WhyNowEvidence 增 event_display；Citation 增 quote_span_display（均 `dict[SystemLanguage, TranslatedText] \| None`）。Doc.title 原文呈现（同 B7 精神），title 译显不在本轮范围 | **槽位收敛** |
| I7 产物语言 | Deliverable/Block 增 lang | 同假设；两类字段齐全已核 | Deliverable: type/version/ledger_version/stale_reasons…；Block: author/locked/user_modified/needs_review… | 照原案 + 同语不变量 | 照原案 |
| I8 图谱三实体 | 新增 | 新增（真件无同名） | Principal 存在（owner_scope 类型可用） | 照原案 | 照原案 |
| I9 Favorite | 新增 | 新增 | — | 照原案（基线内嵌快照；P1 位） | 照原案 |
| I10 TemplateRecord | 新增 | 新增；真件已有 `TemplateSpec`（章节模板）为另一物，命名不冲突 | TemplateSpec: 章节/占比语义 | 照原案（G5 注册表项） | 照原案 |
| I11 ShareLink | 新增 | 新增 | Principal/Role 复用 | 照原案 + friend 缝 | 照原案 |
| I12 三不变量 | 测试即规范 | 照原案 | — | — | 照原案 |
| I13 分析上下文 | AnalysisContext 增 lang/region | AnalysisContext 现有 **project_id/budget_cny/locale** 三字段——`locale: str` 已存在但松散 | ProposalContext 亦有 locale（保留） | 增 lang: SystemLanguage + region: Region；locale 保留兼容并在 v04 docstring 注记「v0.4 起 lang/region 为权威（A3），locale 由 lang 派生填充」 | **微调** |
| （原 I13 后半）PricingRecord.currency | 增 currency | **无需增量**：真件 PricingRecord 已含 `currency: str` 与 `region: str`（plan/price/currency/region/confidence/captured_at/url） | 见左 | J9 收敛为「核实登记」：SCHEMA-14 只做存在性断言 + price_entries 表列核对；K8（汇率/分档）不变 | **已满足** |
| 事件与作业 | 落 protocols_v04 | **落 models_v04**：JobKind Literal 与 payload 判别类（StatusChanged/StepEvent/PartialBlockEvent/JobFailedEvent + JobEvent 封套）均在 models.py；protocols_v04 仅 docstring 增补 | JobKind 现七值：gate1_analysis/report/proposal/spec_export/revalidation/daily_ingest/pricebook_scan | JobKind 增 translate/design_generate/template_solidify；payload 联合增七成员（design_delta/design_tool_call/design_clarify/design_check/translate_progress/solidify_result/graph_stale_notice） | **落点修正** |

## 其余核实注记

1. **冻结头文字滞后**：models.py 头部仍写「改动只能来自 ⑧ 对抗性推演」，未同步 v0.3.3「∨ owner 变更」补充（protocols.py 已同步）。登记为文字滞后，非阻塞；v04 副本头部按 v0.3.3 口径书写。
2. **B7 执行机制修正**：真件非 frozen dataclass → 「name_native 拒改写」由写路径校验与测试保证（工单 §3-B7「违反时」已改）。
3. **H8 进一步坐实**：Origin docstring 明确 combo payload = {card_ids, hypothesis}、「关联假设仅此路径必填」——GraphEdge.hypothesis 复用该校验语义成立。
4. **豁免记录**：RedactionRecord 在列（[F2] 唯一 GC 例外），P1 pin 提案的豁免面扩展表述与真件一致。
