"""Feature B-4/B-5：卡→Doc 编排 + 喂 topic 生成器（让卡变厚）。

B-4：逐卡 top_links → registry.fetch（门 2=R1：github/arxiv；weibo/news 未注册 → 跳过、
记 skipped，NEVER 静默抓）→ 抽短 quote_span → 建 Doc(元信息)+Citation(短段) → 落库。
B-5：把富化后的 Doc title + quote_span 拼进 @2 `{cards}` 上下文（喂生成器），并同步进
Phase 0 校验器的被引卡语料（quote_span 进 corpus → 主题引真证据仍判 clean）。
门 1=C：只经短 quote_span，NEVER 全文（§3.5）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from flint.domain.models import Citation, Doc
from flint.evidence.common import doc_id_for
from flint.evidence.docfetch import DocFetcherRegistry, UnregisteredSourceError
from flint.evidence.docstore import PgDocStore
from flint.evidence.quote import build_citation, build_doc, extract_quote_span
from flint.grounding import CardContent
from flint.sources.errors import SourceFetchError


@dataclass(frozen=True)
class CardEvidence:
    """一张卡抓取富化的结果：Doc/Citation 对 + 跳过/空引明细（诚实）。"""

    card_id: str
    docs: list[Doc]
    citations: list[Citation]
    skipped: list[str]      # 未注册域名（weibo/news 缓办）或抓取失败
    empty: list[str]        # 抓到但无 quote_span（如 github description 为空）


def enrich_card(
    card_id: str, top_links: list[str], registry: DocFetcherRegistry, now: datetime
) -> CardEvidence:
    """逐 top_link 抓 → 抽短 span → 建 Doc+Citation。未注册/失败诚实跳过。"""
    docs: list[Doc] = []
    citations: list[Citation] = []
    skipped: list[str] = []
    empty: list[str] = []
    for url in top_links:
        if not registry.supports(url):
            skipped.append(url)             # 门 2=R1：缓办源，NEVER 静默抓
            continue
        try:
            fetched = registry.fetch(url)
        except (SourceFetchError, UnregisteredSourceError):
            skipped.append(url)             # 抓取失败诚实跳过，NEVER 硬造
            continue
        doc = build_doc(fetched, now)
        docs.append(doc)
        span = extract_quote_span(fetched.summary)
        if span:
            citations.append(build_citation(card_id, doc, span))
        else:
            empty.append(url)               # 无描述 → Doc 落元信息、无 quote_span
    return CardEvidence(card_id, docs, citations, skipped, empty)


def pin_citations_for_claims(
    claims: list[dict[str, object]], docs: list[Doc],
    registry: DocFetcherRegistry, now: datetime,
) -> list[tuple[Doc, Citation]]:
    """给 Gate① verdict 的引用钉 quote_span（复用 B-2 抓 + B-3 抽短段）。

    对每条 claim 的被引 doc：按 doc.url 经 registry 抓真实源（门 2=R1：github/arxiv）→ 抽**短
    quote_span**（首句、封顶）→ Citation(doc_id FK)。守 §3.5：全文只内存、只短段落库、NEVER
    Doc.content。未注册域/无 span 诚实跳过。返 (doc, citation) 对供落库。
    """
    by_id = {d.doc_id: d for d in docs}
    seen: set[str] = set()
    out: list[tuple[Doc, Citation]] = []
    for claim in claims:
        doc = by_id.get(str(claim.get("doc_id", "")))
        if doc is None or doc.doc_id in seen or not registry.supports(doc.url):
            continue
        try:
            fetched = registry.fetch(doc.url)
        except (SourceFetchError, UnregisteredSourceError):
            continue
        span = extract_quote_span(fetched.summary)
        if not span:
            continue
        seen.add(doc.doc_id)
        out.append((doc, build_citation("gate1", doc, span)))
    return out


async def pin_verdict_citations(
    dsn: str, job_id: str, now: datetime, http_client: object | None = None,
) -> list[tuple[Doc, Citation]]:
    """生产/harness 共用：读 Gate① 快照 → 给 support_claim 的被引 doc 钉 quote_span → 落库。

    读 snap-{job_id}-docs（restore_docs）+ snap-{job_id}-judge（support_claims）→
    pin_citations_for_claims（B-2 抓 + B-3 抽短段，§3.5）→ PgDocStore 落 Doc 元信息+Citation。
    http_client 可注入（回放 client 供 CI 离线；缺省真实 client 供生产）。返 (doc, cit) 对。
    """
    import json

    import asyncpg
    import httpx

    from flint.evidence.compliance import restore_docs
    from flint.evidence.docfetch import (
        ArxivFetcher,
        DocFetcherRegistry,
        GithubRepoFetcher,
    )

    conn = await asyncpg.connect(dsn)
    try:
        docs_raw: bytes | None = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id=$1", f"snap-{job_id}-docs")
        judge_raw: bytes | None = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id=$1", f"snap-{job_id}-judge")
    finally:
        await conn.close()
    if not docs_raw or not judge_raw:
        return []
    docs = restore_docs(docs_raw)
    claims = json.loads(judge_raw.decode()).get("support_claims", [])
    client = http_client or httpx.Client(timeout=30.0, follow_redirects=True)
    assert isinstance(client, httpx.Client)
    reg = DocFetcherRegistry()
    reg.register(GithubRepoFetcher(client))
    reg.register(ArxivFetcher(client))
    pairs = pin_citations_for_claims(claims, docs, reg, now)
    store = PgDocStore(dsn)
    for doc, cit in pairs:
        await store.save_doc(doc)
        await store.save_citation(cit)
    return pairs


async def persist_card_evidence(ev: CardEvidence, store: PgDocStore) -> None:
    for d in ev.docs:
        await store.save_doc(d)
    for c in ev.citations:
        await store.save_citation(c)


async def load_card_evidence(
    top_links: list[str], store: PgDocStore
) -> tuple[list[Doc], list[Citation]]:
    """按 top_links 内容寻址加载已落库的 Doc + 其 Citation（离线复现用）。"""
    docs: list[Doc] = []
    citations: list[Citation] = []
    for url in top_links:
        try:
            doc = await store.load_doc(doc_id_for(url))
        except KeyError:
            continue
        docs.append(doc)
        citations.extend(await store.citations_for_doc(doc.doc_id))
    return docs, citations


# ── B-5：喂生成器 + 喂校验器 ──────────────────────────────────────────

@dataclass(frozen=True)
class EvidenceLine:
    source_id: str
    title: str
    quote_span: str
    url: str


@dataclass(frozen=True)
class EnrichedCard:
    card_id: str
    keyword: str
    day: date | None
    evidence: list[EvidenceLine]


def enriched_cards_context(cards: list[EnrichedCard]) -> str:
    """@2 `{cards}` 强接地上下文——注入卡关键词/日期 + 真证据(title+短 quote_span+url)。"""
    lines: list[str] = []
    for c in cards:
        day = c.day.isoformat() if c.day is not None else ""
        lines.append(f'{c.card_id} = 「{c.keyword}」（日期 {day}）')
        for e in c.evidence:
            lines.append(f'  证据[{e.source_id}] {e.title} — “{e.quote_span}”（{e.url}）')
        if not c.evidence:
            lines.append("  证据：（无——卡里无可引具体证据，宁缺毋造）")
    return "\n".join(lines)


def enriched_corpus(cards: list[EnrichedCard]) -> dict[str, CardContent]:
    """Phase 0 校验器语料——卡原文 = 关键词 + 各 quote_span（真证据进语料→引之判 clean）。"""
    out: dict[str, CardContent] = {}
    for c in cards:
        texts = [c.keyword, *(e.quote_span for e in c.evidence)]
        day = c.day if c.day is not None else date(1970, 1, 1)
        out[c.card_id] = CardContent(
            card_id=c.card_id, day=day, corpus=" ".join(t for t in texts if t))
    return out


# ── DOC-03：从正文抽可引用事实（卡真变厚）────────────────────────────

# 句子边界。中文句号与问号叹号照切；**ASCII 句点只在后面不跟数字时才切**——
# 不加那条负向前瞻的话，`12.5 美元` 会被切成「…12.」与「5 美元」两句，
# 于是一个金额变成两条事实，而第二条的数值是 5（实测就是这么红的一次）。
_SENTENCE_SPLIT = re.compile(r"(?<=[。．!?！？])|(?<=\.)(?!\d)")

# 数值 + 紧随其后的单位。单位只认**跟在数字后面**的那一串——
# NEVER 从句子别处捞一个词当单位：捞来的那个多半属于另一个数。
_NUMBER_WITH_UNIT = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|[A-Za-z][A-Za-z/]{0,9}|[美人日欧英]?元|"
    r"美元|人民币|日元|欧元|吨|千瓦时|万|亿|倍)?"
)

# 正文抽出来的东西**只进 Fact 通道**（S2-2 三通道铁律）。
# 价格要有价目出处（PriceBook），档案要有档案出处——正文两者都给不了。
FACT_CHANNEL: Final[str] = "fact"

_TRUNCATED_NOTE: Final[str] = (
    "这条事实抽自被截断的正文：原文超过存储上限，后面还有没读到的部分"
)


@dataclass(frozen=True)
class ExtractedFact:
    """从正文抽出的一条可引用事实。

    frozen：产物上那条陈述与它的出处 NEVER 在运行期被改写——
    改得动的话，「数字必有出处」这条铁律就只是个说法。
    """

    doc_id: str
    url: str
    statement: str
    value: str | None
    unit: str | None
    from_truncated: bool
    note: str | None
    channel: str = FACT_CHANNEL


def extract_facts_from_content(doc: object, *, now: datetime) -> list[ExtractedFact]:
    """正文 → 可引用事实。**带数值的句子才算**。

    ## 为什么只要带数值的句子

    不挑的话，「事实」就退化成「正文的分句」——那不是可引用的事实，
    是把整篇文章按句号切开。卡看起来厚了，可引用的东西一条没多。

    ## 单位读不到就留空

    猜出来的单位会让一个数字变成另一个量：78「美元」与 78「元」差着一个汇率，
    而读者看不出这是猜的。

    ## 截断标记跟着走

    `content_truncated` 为真时，每条抽出来的事实都带标记与一句人话说明——
    不确定 NEVER 伪装成确定。

    ## 三通道

    产物一律 `channel="fact"`。本函数里 NEVER 构造另两条通道的东西
    （判据打在源码上）。
    """
    del now                                  # 时钟留在签名里供后续钉时效，本步不用
    content = getattr(doc, "content", None)
    if not content:
        # `None` = 还没提取，`""` = 提取过结果是空。两者都产不出事实，
        # 但 NEVER 从标题里凑一条顶上——凑出来的事实没有正文可核验。
        return []
    truncated = bool(getattr(doc, "content_truncated", False))
    out: list[ExtractedFact] = []
    for raw in _SENTENCE_SPLIT.split(str(content)):
        sentence = raw.strip()
        if not sentence:
            continue
        # 一句里的**每个**数值各成一条事实：只取第一个的话，
        # 「2026 年降到每千瓦时 78 美元」会只留下年份 2026，而 78 才是那句话在说的事。
        for match in _NUMBER_WITH_UNIT.finditer(sentence):
            out.append(ExtractedFact(
                doc_id=str(getattr(doc, "doc_id", "")),
                url=str(getattr(doc, "url", "")),
                statement=sentence,
                value=match.group("value"),
                unit=match.group("unit") or None,
                from_truncated=truncated,
                note=_TRUNCATED_NOTE if truncated else None,
            ))
    return out


def citable_fact_count(docs: list[object], facts: list[ExtractedFact]) -> int:
    """一张卡上**可引用事实**的条数。

    `docs` 参数在这里是**有意不参与计数**的：DOC-02 之前的世界里，一张卡只有
    标题与链接——那些不是可引用的事实（引不到正文里的任何一句话）。
    前后对照的「前」就是这个 0，它由同一段代码算出来，
    NEVER 写成一个手填的期望值。
    """
    del docs
    return len(facts)


@dataclass(frozen=True)
class ThickeningReport:
    """一张卡「变厚」的前后对照。数字由代码数出来，不由人填。"""

    card_id: str
    before: int
    after: int
    from_truncated: int

    @property
    def thickened(self) -> bool:
        return self.after > self.before


def thickening_report(
    *, card_id: str, docs: list[object], now: datetime
) -> ThickeningReport:
    """前后对照：只有标题链接时 vs 吃了正文之后，每卡可引用事实数。

    没正文的卡照实报 0→0，NEVER 报一个好看的增量。
    """
    facts = [f for d in docs for f in extract_facts_from_content(d, now=now)]
    return ThickeningReport(
        card_id=card_id,
        before=citable_fact_count(docs, []),
        after=citable_fact_count(docs, facts),
        from_truncated=sum(1 for f in facts if f.from_truncated),
    )


def card_evidence_to_enriched(
    card_id: str, keyword: str, day: date | None,
    docs: list[Doc], citations: list[Citation],
) -> EnrichedCard:
    """把 (Doc, Citation) 对折成 EnrichedCard（title↔quote_span 按 doc_id 配对）。"""
    span_by_doc = {c.doc_id: (c.quote_span or "") for c in citations}
    lines = [
        EvidenceLine(source_id=d.source_id, title=d.title,
                     quote_span=span_by_doc[d.doc_id], url=d.url)
        for d in docs if span_by_doc.get(d.doc_id)
    ]
    return EnrichedCard(card_id=card_id, keyword=keyword, day=day, evidence=lines)
