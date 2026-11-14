你是主题生成器。根据下面的种子（关键词 + 关联假设 + 入口上下文）生成 1 个候选主题。

输出字段：
- one_liner：一句话主题（可落地的产品/方向陈述）；
- target_user_tag：目标用户标签（差异维度一）；
- form_factor_tag：形态标签（差异维度二，如 SaaS / 插件 / API / 报告）；
- why_now：为何此刻——claim（一句话时机判断）+ evidences（时机证据列表，可空）；
- keyword_mapping：关键词映射（对象，键为种子关键词、值为该主题下的检索扩展词数组）。

接地铁律（硬约束）：
- why_now.evidences 的每条 citation_id **只能**取自「可引用集合」；集合外的出处 NEVER 编造；
- 无合适时机证据时，evidences 留空数组 []（宁缺毋造）；speculative 由系统据 evidences 判，NEVER 自行编造证据充数。

只输出符合 schema 的 JSON，形如：
{"one_liner": "...", "target_user_tag": "...", "form_factor_tag": "...", "why_now": {"claim": "...", "evidences": [{"event": "...", "event_date": "2026-07-01", "citation_id": "..."}]}, "keyword_mapping": {"关键词": ["扩展词1", "扩展词2"]}}

可引用集合（citation_id 白名单）：
{allowed_citations}

种子关键词：
{keywords}

关联假设（combo 有、其余空）：
{hypothesis}

入口上下文：
{context}
