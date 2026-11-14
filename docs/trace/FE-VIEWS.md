# trace · 前半程三界面（广场 / 工作台 / Gate 视图）

## owner 裁决（@2026-07-30）
选 (a)。目标 = 产品第一次端到端可演示（热点 → 生成报告）。第一步 NEVER 凭猜、先探后端；
数据不可查 → STOP 报 owner，NEVER 造持久化语义/假装有数据。

## 后端探明（逐界面：读契约 + 数据可查性 + 缺口）

现有读端点仅 /categories、/jobs/*、/deliverables/*（三界面结构化读端点全缺，监管已确认，
本次实测复核）。DB 权威表 29 张（查 pg_tables）。

### 广场（浏览四源日更热点/簇/主题）
- **数据可查 ✓（真实数据在库）**：
  - `clusters`（193 行）：cluster_id / canonical_name / category_id / centroid / status /
    first_seen / last_active / parent_cluster_ids / merged_into / aliases。
  - `heat_points`（1033 行）：cluster_id / **source_id** / **day** / raw_value / **norm_score**。
    四源 source_id = **arxiv / ghtrend / gtrends / weibo**（arXiv/GitHub Trending/Google
    Trends/微博）；实测有 2026-07-01~07-05 五天数据。
  - `categories`（12）/`keywords`（193）/`trend_items_raw`（1044，四源原始 item）。
- **读契约**：按 day 取当日热点簇——join clusters × heat_points（按 day、可分 source），
  按 norm_score（热度）排；带 category、四源分值。
- **缺口（诚实标注，非阻断主链）**：**无 `topics` 表——Topic（「主题」）未持久化**。日更采集
  层产的是「簇」（cluster），「主题」是后续分析产物（combo/idea/domain 型 Origin → Topic），不在
  日更面。→ **广场展示「四源日更热点/簇」（据实的持久化层），「主题」不在本界面**（登记 Q-009）。

### 工作台（证据卡 + 关联假设）
- **证据卡：数据可查 ✓**：`evidence_cards`（1027 行）：card_id / cluster_id / keyword_ids /
  flags（如 ["novelty"]）/ top_links（源 URL 列表）。按 cluster_id 查。引用 = top_links 源链接。
- **关联假设：数据不可查 = 缺口（STOP 报 owner）**：「关联假设」= combo 型 Origin/TopicSeed
  的 `hypothesis`（contracts/models.py:184「combo: {card_ids, hypothesis}」；TopicSeed.hypothesis
  combo 必填）。**无 `origins` / `topic_seeds` 表——Origin/TopicSeed/hypothesis 全未持久化**
  （grep 无 INSERT INTO origins/topic_seeds/topics）。这是**更深的缺口**（似当初 regenerate
  执行链）——combo/关联假设的创建与落库语义未建。→ **STOP：关联假设本界面不建**，登记 Q-010；
  工作台先建「证据卡只读」（真实可查），关联假设待 owner 决持久化语义。

### Gate 视图（Gate① 四分类，全引用）
- **数据可查 ✓（间接，经 job 快照）**：gate1_analysis 的 validate 步产 verdict_payload，
  存 `snapshots['snap-{job_id}-verdict']`（flint/jobs/gate1.py:544-546），内含
  **verdict（A/B/C/D）+ all_satisfied + key_citation_ids + rationale_fact_ids + competitors
  + constraints_checked + gaps**（VerdictResult 全字段 + 判定理由 + 引用链）。经 job_id 可取。
- **读契约**：GET /jobs/{id}/verdict → 反序列化 snap-{job_id}-verdict → verdict 全字段
  （四分类 + 引用 key_citation_ids + 理由 rationale_fact_ids + 竞品 + gaps）。**全引用据实呈现，
  前端 NEVER 自判分类**。
- **无缺口**（verdict 已持久化在快照，非独立 verdicts 表但可经 job_id 取）。

## 结论（可建 vs STOP）
- **可建读端点（本次）**：① 广场（clusters+heat）；② 工作台-证据卡（evidence_cards）；
  ③ Gate-verdict（snap-{job}-verdict）。三者数据均真实可查，端到端演示主链（热点→证据→四分类
  →生成报告）**通**。
- **STOP 报 owner 两缺口（NEVER 造持久化/假装有数据）**：
  - **Q-009**：Topic（主题）未持久化——广场只展示簇（据实），主题层待 owner 决是否/如何落库。
  - **Q-010**：关联假设（combo Origin/TopicSeed hypothesis）未持久化——工作台先只上证据卡，
    关联假设待 owner 决持久化语义（更深缺口）。

## 建成（走可建范围，DONE；Q-009/Q-010 缺口推后·留白·NEVER 造数据）
### FV-001 · 三读端点（flint/api/views.py，4 测试绿，本地 PG）
create_views_app：GET /plaza/hot?day=（clusters × heat_points join，聚合 by_source
+ total_heat，按 total 排；坏 day→400）；GET /clusters/{id}/evidence-cards（keyword_ids/
flags/top_links，未知簇→空）；GET /jobs/{id}/verdict（取 snap-{job}-verdict 反序列化 →
verdict 全字段；无→404）。**既有模型只读、NEVER 改冻结件、NEVER 造数据**。tests/fe_views/
test_read_endpoints.py 4 绿（种子用不撞真数据的 day 2026-07-20 + autouse 清理 fv-*）。
### FV-002 · 三界面前端（web，6 测试绿）
web/lib/viewsClient.ts（fetchPlazaHot/fetchEvidenceCards/fetchVerdict，VerdictNotReady）+
i18n keys（plaza/workbench/gate.*，④留缝）+ 三视图（纯呈现，测像 L0）：
- PlazaView：列簇（后端已排、前端零计算）+ 四源分值 + category；点簇→onSelectCluster；
  **主题层留白**（data-topic-deferred，Q-009）。
- WorkbenchView：证据卡只读（引用=top_links 源链接据实，无编辑控件）；**关联假设留白**
  （data-hypothesis-deferred，Q-010）。
- GateView：四分类全引用据实（verdict/引用/理由/竞品/gaps）；**前端 NEVER 自判——verdict
  直取后端值**（data-verdict=后端 verdict）。
### tasks.json
FV-001/FV-002 并入（milestone FE-VIEWS），tasks 216→**218**、total_cycles 227→**243**、
critical_path 53、review_gates +2、dag 对账绿；archive_write bak-5（H-3）。test_m4_023
len 218 + exit_ids +FV-002（前半程视图出口终端）。
### 端到端演示主链
广场(热点/簇) → 点簇 → 工作台(证据卡) → 发起分析 → Gate①四分类 → 生成报告(L0/L1/L2 +
指令式重生成)。**主链通**。缺口两处（主题 Q-009 / 关联假设 Q-010）不挡主链，留白登记待 owner。
