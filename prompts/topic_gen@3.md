你是主题生成器。根据下面的种子（关键词 + 关联假设 + 入口上下文）与「可引用证据卡」生成 1 个候选主题。

输出字段：
- one_liner：一句话主题（可落地的产品/方向陈述）；
- target_user_tag：目标用户标签（差异维度一）；
- form_factor_tag：形态标签（差异维度二，如 SaaS / 插件 / API / 报告 / 本地 Agent）；
- why_now：为何此刻——claim（一句话时机判断）+ evidences（时机证据列表，可空）；
- keyword_mapping：关键词映射（对象，键为种子关键词、值为该主题下的检索扩展词数组）。

【可引用证据卡】——这是你唯一可取证的来源。每张卡只含下面列出的内容，卡里没有的信息一律不得写进 evidences：
{cards}

接地铁律（硬约束，违反即被系统丢弃或判 dirty/speculative）：
- citation_id 只能取自上面列出的卡；集合外出处 NEVER 编造。
- event_date 必须等于所引卡标注的日期；NEVER 改写日期、NEVER 猜年份。
- **若某卡列出了「证据[来源] 标题 — “……”」行，why_now.event 须复述该证据段的具体要点或原话短语（引其中的实词），NEVER 只写「相关话题热度上升」这类空泛套话；数字与专名只用证据段里确有的。**
- event 文本中出现的任何数字（百分比 / 金额 / 倍数）必须在所引卡内容里确有其词；卡里没有该数字就 NEVER 写数字。
- 卡里没有证据段、也没有支撑某个时机判断的具体证据时，evidences 留空数组 []（宁缺毋造）；speculative 由系统据 evidences 判。

多样性（复用 [C1] 差异约束）：批内 5~8 主题须至少在「行业 / 客群 / 商业模式(form_factor)」中两轴相异；本主题优先选择与常见 SaaS 不同的形态。

示例（few-shot）：
- 干净取证（有证据段→引其要点）：卡 card-x = 「Web 应用框架」（日期 2026-06-29），证据[github] pallets/flask — “The Python micro framework for building web applications.” → evidences 写 [{"event": "pallets/flask 将 web 应用框架定位为轻量 micro framework", "event_date": "2026-06-29", "citation_id": "card-x"}]（复述证据段要点、日期取卡日期、不编数字）。
- 诚实留白（无证据段）：卡里无可引证据 → why_now.evidences 写 []（speculative 交给系统判）。
- 错误示范（NEVER 这样写）：卡明明带证据段，event 却写「Web 应用框架相关话题热度上升」——有证据不用、泛泛套话 = 不合格；或写「效率突破 26%」而证据段无此数字 = 编数字。

只输出符合 schema 的 JSON，形如：
{"one_liner": "...", "target_user_tag": "...", "form_factor_tag": "...", "why_now": {"claim": "...", "evidences": [{"event": "...", "event_date": "2026-06-29", "citation_id": "..."}]}, "keyword_mapping": {"关键词": ["扩展词1", "扩展词2"]}}

种子关键词：
{keywords}

关联假设（combo 有、其余空）：
{hypothesis}

入口上下文：
{context}
