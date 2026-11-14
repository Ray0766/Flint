"""分析动作层（v0.4）：深度分析按钮的提交面。

本包只做**提交**：构造 payload、按配置决定计费落点、交给既有 JobRunner。
真正的分析编排在 `flint/jobs/gate1.py`，模型调用在 worker 内——
提交面 NEVER 碰 LLM、NEVER 自己写 runner（§6-H7）。
"""
