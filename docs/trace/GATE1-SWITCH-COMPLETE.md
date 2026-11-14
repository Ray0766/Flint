# GATE1-SWITCH-COMPLETE trace — 生产切换单线程收尾 Steps 0-3（owner @2026-07-31）

## 装载清单（inputs）
- `docs/progress.jsonl` + `eval/ledger_pairing.py`（Step 0）；`flint/jobs/gate1.py`（build_live_deps/main/run_gate1）、
  `flint/evidence/{enrich,quote,docfetch,docstore,search,compliance}.py`（Step 1 pin）、
  `flint/retrieval/query_builder.py`（Step 2 landscape）、`harness/gate1_live.py`、`tests/m2/test_m2_040.py`（Step 3）。

## 决策日志
- **Step 0（台账欠账）**：591-602 十二条**漏闭合 `}`**（bash 手拼、闭合括号落单引号外，**非裸换行**）→ 破坏一行一 JSON、
  pairing 红。逐行补 `}`（note 已闭合、内容不改、好行字节不动）→ 9 绿。守卫 `eval/ledger_append.py::append_entry`
  （json.dumps 保证合法单行 + 断言无裸换行）+ `malformed_lines` lint（4 测）。**纪律**：追加走 append_entry，NEVER 手拼。
- **Step 1（quote_span 钉论文）**：`pin_verdict_citations`（enrich.py，复用 B-2 抓+B-3 抽首句封顶 280）读 snap-docs/judge →
  给 support_claim 被引真论文钉短 quote_span → Citation 落库。**§3.5**：全文只内存、只短段落库、无 Doc.content。生产
  `main` live 与 harness 共用（harness 注回放 client，CI 零联网）。unit 测（arxiv 夹具，span 含 sequence transduction、≤281）。
- **Step 2（landscape 调优，诚实边界）**：query_builder landscape `{term} product platform vendor`→`{term}` +
  source_kinds `[repo,product,paper]`。github 现找**真实开源替代**（LightRAG/graphrag/Verba）、arxiv 找研究面。
  **诚实红线**：找到的是开源替代非商业竞品；**商业竞品待市场源（门 2 缓），NEVER 假造**（问题单登记）。test_m2_021（landscape
  只断言 intent+product kind）仍绿。
- **Step 3（切生产默认 live）**：`main()` 默认 `_default_live_deps`（qwen+真实 github/arxiv）+ `--offline` 回退。
  **返工**：`test_m2_040` 经 `python -m flint.jobs.gate1` **子进程**调 main（kill-9 恢复冒烟），默认切 live 后子进程走真网 →
  破 offline resume + 违 S2-7。修：子进程调用加 `--offline`（CI 离线）。其余测直接用 build_offline_deps 不经 main、不受影响。
  **诊断**：污染 doc（真 arxiv 标题 + 今日 fetched_at、doc_id_for 格式）即 live 子进程写入——非 landscape/pin 之过，定位到 main flip。

## 落盘
- 改 `flint/jobs/gate1.py`（main flip + _default_live_deps + pin wire）、`flint/evidence/enrich.py`（pin_citations_for_claims +
  pin_verdict_citations）、`flint/retrieval/query_builder.py`（landscape）、`harness/gate1_live.py`（pin 委托 + pinned 输出）、
  `tests/m2/test_m2_040.py`（--offline）。新增 `eval/ledger_append.py`、`tests/m4/test_ledger_append.py`。
- 生产链端到端复验（main 默认 live 无 --offline）：21 真实文档（arxiv+github）、竞品 3 开源替代、support 引真论文 +
  quote_span 可溯（AR-RAG 摘要短段）、verdict D_insufficient（据真实证据诚实判定非粉饰）。手动 payoff job 已清理。
- verify：ruff 净 · mypy --strict 232 文件净 · S2-8 净 · m2+m3-025+m4 ledger+topic **449 绿**（含 pairing 9/ledger_append 4/
  gate1_live 3/pin unit 1/m2_040 5）。**未改冻结件**；**未改依赖锁**；key 零涉及（ollama/github/arxiv unauth）；§3.5 0 违规。
- **DAG**：owner 授权、tasks.json 外——无 DAG 对账/H-3。

## 返工记录
- Step 3：test_m2_040 子进程 main 默认切 live → 加 --offline 保 CI 离线（先误判 landscape/pin，还原后定位到 main flip）。
