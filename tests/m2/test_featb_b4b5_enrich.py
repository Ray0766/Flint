"""Feature B-4/B-5：卡→Doc 编排 + 喂生成器/校验器（离线回放 + DB 落库）。

B-4：卡 top_links [github, weibo] → github 抓成 Doc+Citation、weibo 未注册跳过（门 2=R1）。
B-5：富化后 cards_context 带真 quote_span、校验器语料含 quote_span（引真证据判 clean）。
门 1=C：只经短 quote_span。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from flint.domain.models import Doc
from flint.evidence.common import doc_id_for
from flint.evidence.common import doc_id_for as _doc_id_for
from flint.evidence.docfetch import (
    ArxivFetcher,
    DocFetcherRegistry,
    GithubRepoFetcher,
)
from flint.evidence.docstore import PgDocStore
from flint.evidence.enrich import (
    card_evidence_to_enriched,
    enrich_card,
    enriched_cards_context,
    enriched_corpus,
    load_card_evidence,
    persist_card_evidence,
    pin_citations_for_claims,
)
from flint.grounding import check_topic
from flint.testing.replay import load_fixture

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
FX = Path(__file__).resolve().parents[2] / "fixtures" / "evidence"
NOW = datetime(2026, 7, 31, tzinfo=UTC)
FLASK = "https://github.com/pallets/flask"
WEIBO = "https://s.weibo.com/weibo?q=x"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _multi_client(keys: list[str]) -> httpx.Client:
    by_url: dict[str, Any] = {}
    for k in keys:
        for ex in load_fixture(FX / k / "fetch.json"):
            by_url[ex.url] = ex

    def handler(request: httpx.Request) -> httpx.Response:
        ex = by_url.get(str(request.url))
        if ex is None:
            raise AssertionError(f"no recorded exchange for {request.url}")
        return httpx.Response(ex.status_code, content=ex.body_text.encode("utf-8"),
                              headers={"content-type": ex.content_type})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _registry() -> DocFetcherRegistry:
    client = _multi_client(["github_pallets_flask", "arxiv_1706.03762"])
    reg = DocFetcherRegistry()
    reg.register(GithubRepoFetcher(client))
    reg.register(ArxivFetcher(client))
    return reg


@pytest.fixture(autouse=True)
def _wipe() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM citations WHERE citation_id LIKE 'cit-card-b45%'")
            await conn.execute(
                "DELETE FROM docs WHERE doc_id = $1", doc_id_for(FLASK))
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


def test_enrich_card_github_ok_weibo_skipped() -> None:
    ev = enrich_card("card-b45", [FLASK, WEIBO], _registry(), NOW)
    assert [d.title for d in ev.docs] == ["pallets/flask"]     # github 抓成
    assert WEIBO in ev.skipped                                 # 门 2：weibo 缓办跳过
    assert len(ev.citations) == 1
    assert "micro framework" in (ev.citations[0].quote_span or "")


def test_persist_and_load_roundtrip() -> None:
    store = PgDocStore(DSN)
    ev = enrich_card("card-b45", [FLASK], _registry(), NOW)
    run(persist_card_evidence(ev, store))
    docs, cits = run(load_card_evidence([FLASK], store))
    assert [d.doc_id for d in docs] == [doc_id_for(FLASK)]
    assert "micro framework" in (cits[0].quote_span or "")


def test_enriched_context_and_corpus_carry_quote_span() -> None:
    ev = enrich_card("card-b45", [FLASK], _registry(), NOW)
    ec = card_evidence_to_enriched("card-b45", "web 框架", date(2026, 6, 29),
                                   ev.docs, ev.citations)
    ctx = enriched_cards_context([ec])
    assert "micro framework" in ctx and "card-b45" in ctx and "web 框架" in ctx
    corpus = enriched_corpus([ec])
    assert "micro framework" in corpus["card-b45"].corpus     # quote_span 进语料


def test_pin_citations_for_claims_short_span() -> None:
    # Step 1（Gate①）：给被引真论文钉短 quote_span（复用 B-2/B-3，§3.5 短段非全文）
    from flint.evidence.docfetch import DocFetcherRegistry
    ARXIV = "https://arxiv.org/abs/1706.03762"
    client = _multi_client(["arxiv_1706.03762"])
    reg = DocFetcherRegistry()
    reg.register(ArxivFetcher(client))
    doc = Doc(doc_id=_doc_id_for(ARXIV), source_id="arxiv", kind="paper",
              title="Attention Is All You Need", url=ARXIV, published_at=date(2017, 6, 12),
              meta={"fetched_at": NOW.isoformat()}, origin="retrieved", access="public")
    claims = [{"claim": "方向存在市场支持证据", "doc_id": doc.doc_id}]
    pairs = pin_citations_for_claims(claims, [doc], reg, NOW)
    assert len(pairs) == 1
    _pdoc, cit = pairs[0]
    assert cit.doc_id == doc.doc_id                          # FK 指向真论文
    assert "sequence transduction" in (cit.quote_span or "")  # 真摘要短段
    assert len(cit.quote_span or "") <= 281                   # §3.5 短段封顶


def test_topic_citing_enriched_evidence_is_clean() -> None:
    # 卡变厚后：主题引 quote_span 里的真内容 → 校验器判 clean（有真证据、不造假）
    ev = enrich_card("card-b45", [FLASK], _registry(), NOW)
    ec = card_evidence_to_enriched("card-b45", "web 框架", date(2026, 6, 29),
                                   ev.docs, ev.citations)
    corpus = enriched_corpus([ec])
    tg = check_topic(
        "t1",
        [("micro framework for building web applications", date(2026, 6, 29), "card-b45")],
        corpus)
    assert tg.verdict == "clean"
