# GATE1-LIVE trace — 生产 Gate①→真实源切换（owner @2026-07-31）

## 装载清单（inputs）
- `flint/jobs/gate1.py`（run_gate1 / Gate1Deps / build_offline_deps / _offline_searcher / _plan_queries）、
  `flint/retrieval/{query_builder,expand,terms,refute_templates}.py`（查询计划）、
  `flint/evidence/{search,compliance}.py`（B-6 searcher / check_provenance §3.5）、
  `flint/llm/local.py`（qwen LocalProvider）、`harness/topic_caliber.py`（录制/回放 transport 复用）。

## 第一步只读判定：BOUNDED
- Gate1Deps 已有 provider/searcher 字段 → 注入真实实例**无契约改动、run_gate1 内核不变**。
- 真实 Doc 过 check_provenance（source_id/url/fetched_at 齐）；Doc 只元信息、无全文（§3.5 安全）。
- qwen 免费 + github/arxiv 免费公网 → 无付费源。
- **唯一 owner 决策**：切生产默认 offline→live（改 production 行为 + CI S2-7）——NEVER 擅切，opt-in + 证明。

## 决策日志
- **build_live_deps**（gate1.py）：注入真实 provider+searcher，term_map 照 offline 装载。default 不切。
- **GithubArxivSearcher 精化**（生产必需，非契约）：① 源无关分派——按 query.source_kinds 只搜对口源
  （github=repo/product，arxiv=paper），省调用守 github unauth 搜索限流（10/min）；② resilient 单源降级
  （SourceFetchError→跳过该源，M1-015 单源不整跑失败）。B-6 测试仍绿（query 带 repo+paper 双源）。
- **两条验证路**（都 build_live_deps）：scripted 判官（确定、零 LLM 网，隔离证"真实检索进 Gate①"，CI 回放）
  + live qwen 判官（owner payoff，真实 qwen+真实 github/arxiv，双录制回放）。
- **payoff 实况（NEVER 粉饰）**：qwen 24s 跑完四步，检索 **14 篇真实 arxiv**，support_claim 引真 doc
  （doc-025a7c2ead5e，内容寻址于真 arxiv url），对比 BEFORE 的 `.example` 合成。**诚实边界**：landscape/github
  查询模板（"product platform vendor"/"archived discontinued"）不匹配 github 仓库搜索 → 0 竞品（paper→arxiv 路良好）；
  改模板 = 动检索策略（owner 决策，登记问题单）。quote_span 钉论文 = 随切 live 一并接（登记）。
- **工程坑**：① PG/Docker 本会话中途停（机器长时休眠）→ 起 Docker Desktop + compose up 恢复（数据卷存）。
  ② github 搜索 403 限流 → 源无关分派（github 降到 2 调用）+ resilient + 等窗口重录。

## 落盘
- 改 `flint/jobs/gate1.py`（+build_live_deps）、`flint/evidence/search.py`（源无关分派 + resilient）。
- 新增 `harness/gate1_live.py`（scripted/qwen record/replay）、`fixtures/gate1_live/{scripted,qwen}/*`、
  `assets/gate1_live/*`、`tests/m2/test_featb_gate1_live.py`（3 绿：scripted 检索真 doc + verdict 引真 doc + qwen payoff）。
- 文档 `docs/生产Gate1-真实源切换-payoff.md`、问题单登记两件 owner 决策。
- verify：ruff 净 · mypy --strict 232 文件净 · m2 307 绿 · S2-8 净（报告 1 处 etc-义歧义词已修）。
- **未改冻结件**（Gate1Deps 是 gate1.py 的 @dataclass 非契约；Doc/Query/Citation 用如故）；**未改依赖锁**；
  key 零涉及（ollama/github/arxiv 均 unauth，fixture 键仅 method/url/status/content_type/body_text 无 headers）；§3.5 0 违规。
- **DAG**：owner 授权、tasks.json 外——无 DAG 卡增删、无需对账/H-3。

## 返工记录
- github 403 → 源无关分派 + resilient + 等限流窗口重录。
- 判定 provider 不匹配 LLMProvider（generate 返 object）→ 返 Completion。
