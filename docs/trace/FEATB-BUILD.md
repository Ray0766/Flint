# FEATB-BUILD trace — Feature B「retrieval/Doc 总开关」B-1~B-6 + payoff

owner @2026-07-31 建 Feature B（门 1=C quote_span、门 2=R1 github+arxiv）。test-first + review_gate。

## 装载清单（inputs 来源）
- 冻结件：`contracts/models.py#Doc/Citation/DocKind`、`migrations/0006_evidence_layer`（docs/citations 表）。
- 复用地基：`flint/sources/{registry,arxiv,throttle,errors}.py`、`flint/evidence/common.py#doc_id_for`、
  `flint/topic/store.py`（PgStore 范式）、`flint/jobs/gate1.py#Searcher/_offline_searcher`、
  `flint/grounding.py`（Phase 0 校验器）、`harness/topic_caliber.py`（run_combo_batch + 录制/回放 transport）。
- 设计依据：`docs/证据总开关-设计.md`（本轮据其门 1=C/门 2=R1 裁决落地）。

## 决策日志
- **门 1=C（合规红线）**：Doc 只落元信息（`PgDocStore`，0006 表，无 content 列）；证据正文只进
  `Citation.quote_span` 短段（`quote.py:extract_quote_span` 首句 + 长度封顶 280）。**NEVER 全文、NEVER 加
  Doc.content、NEVER 动契约**。守 §3.5：`check_metadata_only` 落库后仍 0 违规（B-1 verify 断言）。
- **门 2=R1（源无关可插拔）**：`DocFetcherRegistry` 复刻 `sources/registry` 插槽，仅注册 github+arxiv
  官方 API fetcher（`docfetch.py`）；weibo/news/付费源**未注册 → UnregisteredSourceError**，`enrich_card`
  诚实跳过记 skipped（NEVER 静默抓）。缓办源接入通道登记 `docs/v0.4-问题单.md`（Feature B 缓办源通道）。
- **零新依赖**：github(JSON/httpx)、arxiv(Atom/stdlib ElementTree)、selectolax(已锁)——RegistryValidator 无需调用。
- **抓取走 M1-008 录制回放**：真实响应录 `fixtures/evidence/*`（github pallets/flask、psf/requests、
  arxiv 1706.03762、search_transformer），测试离线回放，CI 零联网（S2-7）。真实抓取仅发生于录制期
  （owner R1 授权公网免费 API）+ payoff。限流复用 `SourceThrottle`（B-2 verify）。
- **payoff 发现（NEVER 粉饰）**：卡变厚（真 quote_span 进上下文/语料）后，光靠 @2 主题仍泛写——@2 few-shot
  自身泛写。加 `topic_gen@3`（证据感知：有证据段则 event 复述其要点）后，主题才引真论文。**总开关 = 卡变厚
  + 证据感知 prompt**。arxiv 卡干净信号：thin 命名真论文 0/3 → rich 3/3，前后 dirty=0。dirty=0 非 payoff 功劳
  （瘦卡本就 0）；真增益 = 引真实可命名源。语义忠实度（EN quote_span→ZH event 翻译）= RAGAS 层（待）。
- **B-6（Gate① 真实 Searcher）**：建可注入的 `GithubArxivSearcher`（搜索→真 Doc）替换 `_offline_searcher`
  占位，离线回放测试；**NEVER 改 gate1 生产默认**（切真实源 = owner 决策，涉真实抓取 + 缓办源覆盖面）。

## 落盘
- 新增 `flint/evidence/{docstore,docfetch,quote,enrich,search}.py`、`prompts/topic_gen@3.md`（+lock）、
  `harness/featb_payoff.py`、`assets/featb_payoff/{thin,rich}.json`、`fixtures/evidence/*`。
- 测试 `tests/m2/test_featb_{b1_docstore,b2b3_fetch,b4b5_enrich,payoff,b6_searcher}.py` = **25 绿**。
- 文档 `docs/证据总开关-payoff.md`（前后对比铁证）、`docs/v0.4-问题单.md`（缓办源通道）。
- verify：ruff 净 · mypy --strict 231 文件净 · prompt lock 无 drift · S2-8 净（幂等→重词）· m2+topic 421 绿。
- **未改冻结件**（contracts/domain 未动，generate.py 仅 @1 向后兼容既有）；**未改依赖锁**；key 零涉及；§3.5 0 违规。
- **DAG**：Feature B 属 owner 授权、在 tasks.json（M1 DAG）之外——无 DAG 卡增删，无需 dag 对账/H-3 备份。

## 返工记录
- B-1：`@pytest.mark.asyncio` 未注册 → 改用既有 `run=asyncio.run` 同步测试范式（照 test_ts_001）。
- B-2/3：throttle refill=0.0 被拒 → 用 0.001（~不回填）。
- B-6：arxiv url `all:` 冒号字面（非 %3A）→ 修测试断言。
- payoff：@2 厚卡主题仍泛写 → 加 @3 证据感知 prompt（诚实发现，非粉饰）。
