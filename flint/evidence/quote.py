"""Feature B-3：抽短 quote_span + 建 Doc(元信息)/Citation(短段)。

门 1=C 硬约束（§3.5，问题单 209）：从抓取 summary **只抽一小段**（首句、长度封顶）作
Citation.quote_span——**NEVER 落全文正文**。Doc 只落元信息（无 content）。这是「卡变厚」
唯一合规落点：被引的那一小段短证据。
"""
from __future__ import annotations

import re
from datetime import datetime

from flint.domain.models import Citation, Doc
from flint.evidence.common import base_meta, doc_id_for
from flint.evidence.docfetch import FetchedSource

MAX_SPAN_LEN = 280  # quote_span 长度上限（守 §3.5「短段非全文」；超长即截断加省略号）

_SENT_END = re.compile(r"[。．.!?！？\n]")


def extract_quote_span(summary: str, max_len: int = MAX_SPAN_LEN) -> str:
    """从 summary 抽**首句**、长度封顶——短支撑段，NEVER 全文。空 summary → 空串。"""
    text = " ".join(summary.split())
    if not text:
        return ""
    m = _SENT_END.search(text)
    first = text[: m.end()].strip() if m else text
    if len(first) > max_len:
        return first[:max_len].rstrip() + "…"
    return first


def build_doc(fetched: FetchedSource, now: datetime) -> Doc:
    """建 Doc——**仅元信息**（doc_id 内容寻址于 url；summary NEVER 进 Doc）。"""
    return Doc(
        doc_id=doc_id_for(fetched.url), source_id=fetched.source_id,
        kind=fetched.kind, title=fetched.title, url=fetched.url,
        published_at=fetched.published_at, meta=base_meta(now),
        origin="retrieved", access="public")


def citation_id_for(card_id: str, doc_id: str) -> str:
    return f"cit-{card_id}-{doc_id[-12:]}"


def build_citation(card_id: str, doc: Doc, quote_span: str) -> Citation:
    """建 Citation——短 quote_span + doc_id FK。locator 留 None（R1 无页码/段号）。"""
    return Citation(
        citation_id=citation_id_for(card_id, doc.doc_id), doc_id=doc.doc_id,
        locator=None, quote_span=quote_span)
