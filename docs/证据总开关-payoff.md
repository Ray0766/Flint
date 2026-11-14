# 证据总开关 · payoff 铁证（Feature B，owner @2026-07-31 建 B-1~B-6）

> 收尾验证：对一个 combo 的卡跑真实 github/arxiv 抓取（R1 授权公网免费）→ 卡变厚 → 用
> qwen3.6:35b-a3b（免费本地）重跑 topic 生成 → 过 Phase 0 校验器。报前后对比。**NEVER 粉饰。**

## 设置

- **demo combo**（两卡指向**真实**源）：`card-featb-flask`→`github.com/pallets/flask`；
  `card-featb-arxiv`→`arxiv.org/abs/1706.03762`（Attention Is All You Need）。
  （生产 evidence_cards 的 top_links 为合成种子数据——见空壳诊断；故 payoff 用真实 URL 的
  demo combo 证机制，真实采集跑起来后真卡走同一管线。）
- **真实抓取**：R1 两家官方 API，抓回录制为 fixture（`fixtures/evidence/*`，CI 离线回放）。
  抽短 quote_span：flask=“The Python micro framework for building web applications.”；
  arxiv=摘要首句。**门 1=C：只落短 quote_span，NEVER 全文；§3.5 巡检 0 违规。**
- **模型**：qwen3.6:35b-a3b @2/@3，前后同模型同参；免费本地，零花费。

## 前后对比（同模型、同卡、变的是"卡厚度 + 证据感知 prompt"）

| | BEFORE（瘦卡 @2/@3 无证据段） | AFTER（厚卡 @3 带真 quote_span） |
|---|---|---|
| **校验器 dirty** | **0** | **0** |
| arxiv 卡证据**命名真论文** | **0/4**（泛写「注意力机制作为核心建模能力被广泛引用」） | **3/3**（「Attention Is All You Need 提出…序列转导模型…编码器-解码器…」） |
| 证据实况 | 空泛、不可溯真源 | 命名真实论文 + 复述其真实论点（源自抓回摘要） |

**关键两步**（缺一不成）：
1. **卡变厚**（B-1~B-4）：抓真实源 → 短 quote_span → Doc+Citation → 进 @2 `{cards}` 上下文 + 校验器语料。
2. **证据感知 prompt**（`topic_gen@3`）：光把 quote_span 喂进去不够——@2 的 few-shot 自身是泛写「热度上升」，
   模型照抄泛写（实测：厚卡 @2 主题仍不引证据）。@3 明令「有证据段则 why_now.event 复述其要点、NEVER 泛写」，
   主题才真去引真论文。**总开关 = 卡变厚 + 证据感知 prompt。**

## 诚实边界（NEVER 粉饰）

- **dirty=0 不是 payoff 的功劳**：瘦卡下 @2/@3 本就 dirty=0（校验器只查数字/日期编造，两者都不编）。
  payoff 的真增益是**主题从"泛写不可溯"变"命名真源 + 引真论点"**，不是 dirty 下降。
- **语义忠实度校验器管不了**：arxiv quote_span 是英文原文，qwen 的 event 是中文翻译——字符重叠近 0，
  确定性校验器（查数字/日期）无法核"这段中文是不是忠实翻译了英文摘要"。**忠实度验证 = RAGAS/语义判官层
  （已评估、待卡做厚后接——正是此刻卡做厚了，RAGAS 的前置条件才成立）。**
- **few-shot 污染**：@3 的 few-shot 示例用了 flask，故 thin 的 flask 卡也"命名 flask"（示例泄漏，4/8 里的 4）。
  **arxiv 卡是干净信号**（@3 示例不含 arxiv）：thin 0/4 → rich 3/3，无污染。
- **demo 非生产真卡**：生产 evidence_cards 的 top_links 是合成占位（空壳诊断），故 payoff 用真实 URL 的 demo combo；
  真实采集接入后（含 weibo/news 缓办源）真卡走同一管线。

## 结论

**总开关成立**：真实 github/arxiv 抓取 → 短 quote_span → Doc/Citation 落库（守 §3.5）→ 喂生成器，
端到端跑通、dirty=0 安全、且让主题从"泛写"变"引真实可命名源 + 真论点"。**完整语义忠实度打分 = RAGAS**
（依赖闭包 + 本地判官，卡做厚后其价值才成立——待 owner，见 `docs/ragas-接入评估.md`）。

复现：`python -m harness.featb_payoff`（录制，需 ollama qwen3.6:35b-a3b）/ `pytest tests/m2/test_featb_payoff.py`（离线）。
