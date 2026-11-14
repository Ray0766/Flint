# 生产 Gate①→真实源切换 · payoff（owner @2026-07-31）

> 把 Feature B 的真实 github/arxiv 检索接进生产 Gate①，替换 `.example` 占位，让生产分析产出有据结果。
> **NEVER 粉饰**：报前后对比 + 诚实边界。

## 判定（第一步只读结论）：BOUNDED，已 build

- `Gate1Deps` 已有 `provider`/`searcher` 字段——注入真实实例 **无契约改动、run_gate1 内核不变**。
- 新增 `build_live_deps`（`flint/jobs/gate1.py`）：注入真实 provider + 真实 `GithubArxivSearcher`。
- 真实 Doc 过 `check_provenance`（§3.5，source_id/url/fetched_at 齐）；Doc 只元信息、无全文。
- 免费本地 qwen + 免费公网 github/arxiv → **零付费源**。
- **NEVER 擅切生产默认**：`main()` 仍 `build_offline_deps`；default→live = **owner 一行决策**。

## 前后对比（同一主题「检索增强生成」，locale=en）

| | BEFORE（`.example` 占位，`build_offline_deps`） | AFTER（真实源，`build_live_deps`） |
|---|---|---|
| 检索文档 | 合成 `doc-vendor-alpha`（`alpha.example/product`）/`doc-<hash>`（`papers.example`） | **真实 arxiv 论文**：如 `arxiv.org/abs/2312.10793`（14 篇） |
| 判官 | `_DeterministicJudgeProvider`（合成） | **免费本地 qwen3.6:35b-a3b**（真实 LLM 判官） |
| 检索厚度 | 固定 2~3 合成条 | **scripted 判官 2 篇 / qwen 判官 14 篇真实 arxiv**（qwen 查询扩展→更多样） |
| verdict 引用 | 引合成 `.example` doc | **引真实 arxiv 论文 doc_id**（`doc-025a7c2ead5e` = 内容寻址于真 arxiv url） |
| 可复现 | 离线合成 | **双录制回放**（LLM + 搜索，M1-008，CI 零联网 S2-7） |

两条路都跑通四步（plan→retrieve→judge→validate），产出**引真论文的有据 verdict**：
- **scripted 路**（判官确定、零 LLM 网）：隔离证"真实检索流进 Gate①"，CI 可回放。
- **live 路（owner payoff）**：真实 qwen 判官 + 真实 github/arxiv，24s 跑完，检索 **14 篇真实 arxiv**、
  support_claim 引真论文。LLM+搜索双录制回放，CI 离线复现。

## 诚实边界（NEVER 粉饰）

- **support/论文路通了、竞品/landscape 路没出货**：Gate① 的 landscape/discontinued 查询模板
  （`{term} product platform vendor` / `{term} archived discontinued`）是给 web/产品检索设计的，
  **不匹配 github 仓库搜索语义** → github 搜这些串返 0 仓库 → **0 竞品**。paper 路（→arxiv）工作良好。
  这是**检索查询策略与 github 搜索语义的错配**，非切换本身失败——改 landscape 查询模板 = 动检索策略
  （M2 生产行为），**登记待 owner**（`docs/v0.4-问题单.md`），NEVER 在切换里擅改。
- **quote_span 可溯 = 下一层**：Gate① 的 Doc 是元信息（title/url/date），本切换让 verdict 引真论文 doc_id
  （可溯到真实 arxiv url）；把**短 quote_span**钉到被引论文（复用 B-2/B-3 抓摘要首句）是接下来一步，
  与卡做厚同机制、§3.5 安全。登记为随 owner 定「生产切 live」一并接。
- **dirty=0 语义**：Phase 0 校验器判的是 topic why_now（不是 Gate① verdict）。Gate① 的「有据」=
  引用真实存在、可溯的 doc_id（真 arxiv 论文），对比 BEFORE 的合成 `.example`——这才是「产出有据结果」。
- **github 限流**：unauth 搜索 API 限 10/min；`GithubArxivSearcher` 已做**源无关分派**（按 source_kinds 只搜对口源）
  + **resilient 单源降级**（一源限流跳过、不整跑失败，M1-015）。生产上量若大须走 github token（付费/配额）→ owner 决策。

## 结论

**生产 Gate① 真实源切换成立**：`build_live_deps` 注入真实 qwen + 真实 github/arxiv，生产分析现在
**检索真实 arxiv 论文、产出引真论文的有据 verdict**（对比 BEFORE 的 `.example` 合成），双录制回放 CI 离线可验、
零契约改动、零付费、§3.5 安全。**剩两件 owner 决策**：① 把生产默认切 live（一行）；② landscape/github 查询模板
调优 + quote_span 钉论文（随切 live 一并做）。

复现：`python -m harness.gate1_live record-qwen`（live）/ `pytest tests/m2/test_featb_gate1_live.py`（离线回放）。

---

## 切换完成（owner @2026-07-31 单线程收尾 Steps 0-3）

**Step 0 · 台账欠账收回**：`docs/progress.jsonl` 591-602 十二条我手拼 bash JSON **漏闭合 `}`**（闭合括号落在 bash 单引号外，
非裸换行）→ 破坏「一行一 JSON」、`test_ledger_pairing` 红。修：逐行补 `}`（note 串本已闭合、内容不改、好行字节不动），
9 绿。守卫 `eval/ledger_append.py::append_entry`（json.dumps 保证合法单行）+ `malformed_lines` lint，4 测；**台账一切追加走
`append_entry`，NEVER 手拼 bash**（本轮收尾各条即用它写）。

**Step 1 · quote_span 钉论文**：`pin_verdict_citations`（复用 B-2 抓 + B-3 抽短段）给 verdict 的被引真论文钉 **短 quote_span**
（首句、封顶 280）→ Citation(doc_id FK) 落库。**守 §3.5：全文只内存、只短段落库、NEVER Doc.content**。抓取走录制回放、CI 零联网。

**Step 2 · landscape 模板调优（诚实边界内）**：`query_builder.py` landscape 查询由 `{term} product platform vendor`
（商业检索式、命中不了 github 仓库）→ **裸术语 `{term}` + source_kinds `[repo,product,paper]`**——github 现能找**真实开源替代**、
arxiv 找**研究面**。实测竞品线由 **0 → 真实开源仓库**（LightRAG / microsoft graphrag / weaviate Verba）。**诚实红线**：
github/arxiv 是研究/代码源，**找到的是开源替代、非商业竞品**；**商业竞品须市场源（微博/news/web，门 2 缓）→ 如实标「待市场源」，
NEVER 假造**（问题单登记）。

**Step 3 · 切生产默认 live**：`main()` 默认 `build_offline_deps → _default_live_deps`（免费本地 qwen + 真实 github/arxiv）。
`--offline` 回退合成占位。**CI/单测直接用 `build_offline_deps` 不经 main（S2-7 零联网，不受影响）**；唯一经 `main` 子进程的
`test_m2_040`（kill-9 恢复冒烟）加 `--offline` 保持离线。

**生产链端到端复验**（`python -m flint.jobs.gate1 ... 检索增强生成`，**默认 live、无 --offline**）：
- 检索 **21 篇真实文档**（arxiv 论文 + github 仓库，零 `.example`）；
- 竞品线 **3 个真实开源替代**（LightRAG / graphrag / Verba）；
- support_claim 引真论文 + **quote_span 可溯**（「We introduce Autoregressive Retrieval Augmentation (AR-RAG)…」，源自真 arxiv 摘要短段）；
- verdict = **D_insufficient**（据真实证据的**诚实判定**，非粉饰——规则 A/B/C 未达即如实落 D）。

**生产切换成立**：生产默认现走真实源，端到端产出「引真论文/仓库 + quote_span 可溯 + 开源替代竞品」的有据 verdict，
零付费（qwen 免费本地 + github/arxiv 免费公网）、零契约改、§3.5 安全。**剩 owner 决策**：github token（量大超 unauth 10/min）、
商业竞品的市场源接入（门 2 缓）。
