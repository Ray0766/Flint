# 接地增强(a) 规格 v04 — event 文本/日期一致性校验

> 依据：`WORKORDER-v04.md#2-J3`、`PRINCIPLES#B9`（引文原文不翻译）、`PRINCIPLES#B10`（接地校验只对原文）。
> 校验器：`tools/check_grounding_spec.py`。本规格只规定**判据**，落地实现属后续里程碑。

## 0 要补的洞

现行接地铁律只验 `citation_id` 在账本里、指向的 `Citation` 存在——**不验 event 文本与日期是否
忠于被引卡**。既往横评已实证这条漏洞的形态：**引真卡 + 编假证据**——引用编号完全合法，
`WhyNowEvidence.event` 的叙述却是模型自己写的，日期也对不上被引来源。

冻结件里的相关真件（`contracts/models.py`，只读）：

```
WhyNowEvidence: event: str | event_date: date | citation_id: str
Citation:       citation_id: str | doc_id: str | locator: str | None | quote_span: str | None
Alignment  = Literal["pending", "supports", "partial", "unsupported"]
CitationAligner.align(claim, evidence: Doc, stage: Literal["verdict","draft"]) -> Alignment
```

(a) 规格 = 在上述结构上，增加 **event 文本/日期与被引卡的一致性校验**。

## A 三条 v04 增补

### A1 校验输入 MUST 为原文字段

一致性比对的两侧输入 MUST 都是**原文字段**：待验侧取 `WhyNowEvidence.event` 与
`event_date`，被引侧取 `Citation.quote_span` 与其 `Doc` 的原文正文。
译文派生槽（`TranslatedText` 系列 `*_display`）NEVER 作为输入。依据 `PRINCIPLES#B10`。

`event_date` 是 `date` 类型，没有语言属性，本地化只发生在渲染层——它天然满足本条，
NEVER 为它设 display 槽。

### A2 译文禁入比对

比对函数 MUST 拒绝译文入参：传入任一 `*_display` 派生槽 → 抛 `GroundingOnTranslationError`，
**NEVER 降级为「用译文比一比」**。理由：机翻会同时改写措辞与数字表述，
用译文比对会把「翻得不一样」判成「证据不忠实」，也会把「翻得像」判成一致——两个方向都错。

`CitationAligner` 的两段（`stage="verdict"` 与 `stage="draft"`）同受本条约束，
NEVER 只在其中一段设防。依据 `PRINCIPLES#B10`。

### A3 译文引用可展开原文

报告以译文呈现引用时，出处槽 MUST 可展开到原文：渲染层同时持有原文与译文，
默认显示按 `Deliverable.lang`，展开后显示 `quote_span` 原文与来源语言标记。
只给译文、不能展开到原文的 Block MUST 标 `needs_review`，导出按既有 blocking 语义拦截。
依据 `PRINCIPLES#B9`（原文是权威，译文是派生）。

## B 一致性判据（伪码）

两条判据独立成立，任一不过即整条 evidence 不过：

```python
def check_grounding_a(evidence: WhyNowEvidence, cited: Citation, doc_text: str) -> GroundingResult:
    """(a) event 文本/日期一致性。输入 MUST 全为原文字段（A1）。"""
    # A2：译文派生槽 NEVER 进入比对——先拒绝，再谈判据
    for field in (evidence.event, doc_text):
        if is_translated_slot(field):
            raise GroundingOnTranslationError(
                f"接地比对收到译文派生槽：{field!r}；原文字段才是唯一合法输入（PRINCIPLES#B10）"
            )

    # 判据一：文本忠实——event 的事实性内容 MUST 可在被引原文里定位
    #   证据源 = quote_span（有则以它为准）否则 doc_text 全文
    source_text = cited.quote_span or doc_text
    text_ok = spans_support_event(event=evidence.event, source=source_text)

    # 判据二：日期一致——event_date MUST 与被引来源给出的日期一致
    #   来源无日期 = 不成立（NEVER 以「没写就算过」放行）
    source_date = extract_source_date(source_text, cited)
    date_ok = source_date is not None and source_date == evidence.event_date

    return GroundingResult(
        passed=text_ok and date_ok,
        text_ok=text_ok,
        date_ok=date_ok,
        reason=None if (text_ok and date_ok) else describe_gap(text_ok, date_ok),
    )
```

判据说明：

- **文本忠实**：`event` 的事实性内容 MUST 能在被引原文里定位；改写措辞可以，
  引入原文没有的事实 NEVER 可以。判定实现属后续里程碑（沿用既有 `CitationAligner` 通道，
  NEVER 新开第二条对齐管线）。
- **日期一致**：来源没有可提取日期时判**不过**——「来源没写日期」与「日期对得上」是两回事，
  把前者当后者放行，正是这个洞的成因。
- 结果只有过与不过两态；`Alignment` 的四态是 `CitationAligner` 的产物，两者不混用。

## C 错误类型 GroundingOnTranslationError

```python
class GroundingOnTranslationError(Exception):
    """接地比对收到译文派生槽。原文字段是唯一合法输入（PRINCIPLES#B10）。"""
```

- **何时抛**：`check_grounding_a` 的任一输入被判定为译文派生槽（`*_display` / `TranslatedText`）时，
  在进入判据之前抛出。两段（verdict / draft）同规则。
- **NEVER 怎么处理**：NEVER 捕获后回退成「用译文比对」、NEVER 静默跳过该条 evidence。
- **系统行为**：接地调用抛错 → 该条 evidence 不计入通过集；含未展开译文引用的 Block 标
  `needs_review`，导出按既有 blocking 语义拦截（与 `PRINCIPLES#B10`「违反时」一致）。

## D 与既有件的关系

| 既有件 | 本规格的接法 |
|---|---|
| `CitationAligner`（两段式 verdict/draft） | (a) 判据挂在同一通道上，NEVER 新开第二条对齐管线 |
| `Citation.quote_span` | 有 `quote_span` 时以它为证据源，无则回落被引 `Doc` 原文 |
| 导出门禁 blocking 语义 | 不过的 evidence 走既有 `needs_review` → blocking 路径，NEVER 新造拦截机制 |
