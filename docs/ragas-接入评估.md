# RAGAS 接入评估（owner @2026-07-31 授权只读评估 · NEVER 部署/改锁文件/跑付费判官）

> 评估把 RAGAS 采纳为 (a)-② 深层忠实度方法 + 未来卡做厚后打分的可行性。只出本文；
> 命中付费/决策 → STOP。四问：① 依赖过 RegistryValidator 报可引+确切版本；② 判官能否本地（免费）；
> ③ 中文可用性 + 与 Phase 0 确定性校验器分工；④ 现在接还是等卡做厚再接。

## ① 依赖 · RegistryValidator 口径（S2-6）

用本仓 `flint/registry/pypi.py` 的 `check_pypi` 口径实测（PyPI JSON，releases 过滤纯数字段取最大）：

- **`ragas`：存在 ✓，latest_stable = `0.4.3`，requires_python `>=3.9`**（本项目 Python 3.11 ✓）→ **ragas 本体可引、锁 `0.4.3`**。
- **但 S2-6 要求每个新依赖（含传递闭包）逐一过 registry + 锁死**。ragas 的**核心依赖（非 extra）**很重：
  `numpy / datasets>=4.0.0 / tiktoken / pydantic>=2.0.0 / nest-asyncio / appdirs / diskcache / typer / rich /
  openai>=1.0.0 / tqdm / instructor / pillow / networkx / scikit-network / langchain / langchain-core /
  langchain-community / langchain_openai`。
- 与现有 `requirements.lock`（81 行）比对：
  - **可复用（已锁、版本兼容）**：`pydantic 2.13.4`（满足 >=2.0）、`numpy 2.5.1`（满足 <3.0）、
    `sentence-transformers 5.6.1`（bge-m3，可直接当 RAGAS 嵌入）、`scikit-learn 1.9.0`、`networkx 3.6.1`、
    `typer 0.27.0`、`rich 15.0.0`。
  - **净新增直接核心依赖（13）**：`langchain / langchain-core / langchain-community / langchain-openai /
    openai / datasets / tiktoken / instructor / diskcache / scikit-network / nest-asyncio / appdirs / pillow`
    ——各自还带传递闭包（langchain 系拉 langsmith/jsonpatch 一串；datasets 拉 pyarrow/huggingface-hub/dill/
    multiprocess/xxhash/fsspec；instructor/openai 拉各自链）。
- **判定**：ragas 本体**可引可锁**；但接入 = 锁文件**规模翻倍级扩张**（~13 直接 + 大量传递），
  与本项目「最小依赖、逐项锁版」纪律张力大。**机械上可行**（`flint/registry/batch.py` 支持批量校验+锁），
  **NEVER 现在改锁**——是否吞下这批依赖 = **owner 决策**。

## ② 判官模型 · 能否本地（免费）

- **能，且不需付费模型 → 不触发 STOP**。RAGAS 的判官与嵌入均可注入自定义实例（`evaluate(..., llm=, embeddings=)`
  / `LangchainLLMWrapper`）。本地免费两条路：
  - **复用 openai 客户端打本地端点**：`ChatOpenAI(base_url="http://localhost:11434/v1", api_key="ollama", model=...)`
    指向 ollama（OpenAI 兼容）。ragas 核心本就装 openai，**无需再加依赖**、零花费。
  - 或加 `langchain-ollama`（再多一个锁项）走原生 ollama。
- 嵌入直接复用**已锁 bge-m3（sentence-transformers 5.6.1）**，与本项目检索侧同一嵌入，口径一致、免费。
- **注意**：ragas 核心仍会装 `openai + langchain_openai`（本地判官下二者不发付费调用，但依然进锁）。
  **本评估 NEVER 跑判官**（未装 ragas、未发任何调用）；上述为 0.4.x 公开 API 口径。

## ③ 中文可用性 + 与 Phase 0 确定性校验器分工

**中文**：RAGAS 忠实度（faithfulness）机制 = 判官把答案拆成陈述句、逐句判是否可由 context 蕴含（NLI），
机制语言无关；但**默认 prompt 是英文**，中文需走 RAGAS 的 prompt 适配/本地化，且**判官须中文能力强**
（本地 qwen 可承，弱模型会误判）。→ 中文可用，前置成本 = prompt 本地化 + 选中文强判官。

**分工（与 `flint/grounding.py` 互补，NEVER 互替）**：

| 维度 | Phase 0 确定性校验器 | RAGAS 忠实度 |
|---|---|---|
| 判什么 | 引用段**数字/日期/实体**是否字面可溯于被引卡 | 答案陈述是否**语义蕴含**于 context（改写级不忠） |
| 方法 | 正则+归一化，纯函数 | 判官 LLM（NLI 拆句）+ 嵌入 |
| 确定性 | 100% 可复现、零花费、CI 离线可当硬门 | 非确定、耗判官算力、难 CI 离线复现 |
| 角色 | **硬门**（dirty→拒/重试/降级） | **语义顾问分**（抓确定性挡不住的软性不忠） |
| 现在能用 | 是（已建、15 绿） | 需 context 有实质内容才有意义（见 ④） |

一句话：**确定性校验器挡字面数字/日期幻觉（即刻、免费、硬门）；RAGAS 判语义忠实（判官级、抓改写不忠）。
二者叠加才全，NEVER 用 RAGAS 替掉确定性硬门。**

## ④ 结论 · 现在接还是等卡做厚再接

**建议：等卡做厚再接（与监管倾向一致）。理由硬：**

- RAGAS 忠实度打的是「答案 vs 检索 **context**」。而 `docs/证据管线-空壳诊断.md` 已证：库内**真实 Doc=0、
  facts=0、卡=空壳**——**当前没有可当 context 的实质证据**。空 context 上跑 faithfulness = 退化/无意义
  （无物可忠）。此刻接入 = 吞 ~13 直接依赖 + 判官算力，换一个打不出有效分的指标，**性价比低**。
- 确定性校验器已覆盖当前最痛的字面数字/日期幻觉（免费硬门），当前止血足够。

**落地建议（分两步，均待 owner）：**
1. **现在**：只留**接口缝**——把 RAGAS 定为 (a)-② 语义忠实方法登记在案，**不装、不改锁**；
   继续以 `flint/grounding.py` 作即刻硬门。（本评估即此步产物。）
2. **卡做厚后**（证据管线补厚 = 付费/契约、待 owner；见空壳诊断）：批量过 registry 锁死 ragas 闭包 →
   本地判官（ChatOpenAI→ollama）+ bge-m3 嵌入 → 中文 prompt 本地化 → 金标集标定忠实度阈值 → 接 Gate/复核。

**STOP / 决策归属**：
- 是否吞 ragas 依赖闭包（锁文件翻倍）= **owner 决策**（NEVER 现在改锁）。
- 卡做厚（真实源接入/`Doc.content` 契约）= **付费/冻结件触点**，已在空壳诊断 STOP 报 owner。
- 本评估内**无任何付费判官调用、无依赖变更**——纯只读评估，符合授权。
