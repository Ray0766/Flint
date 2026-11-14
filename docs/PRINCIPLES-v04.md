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
