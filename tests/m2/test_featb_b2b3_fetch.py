"""Feature B-2/B-3：源无关抓取器 + 短 quote_span 抽取（M1-008 离线回放，S2-7 零联网）。

门 2=R1：仅 github + arxiv 官方 API；weibo/news 未注册 → UnregisteredSourceError（缓办）。
门 1=C：只抽短 quote_span，Doc 无全文——build_doc 只落元信息、span 长度封顶守 §3.5。
回放真实录制夹具（fixtures/evidence/*），断言解析忠实 + 短段合规。
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from flint.evidence.docfetch import (
    ArxivFetcher,
    DocFetcherRegistry,
    GithubRepoFetcher,
    UnregisteredSourceError,
)
from flint.evidence.quote import (
    MAX_SPAN_LEN,
    build_citation,
    build_doc,
    extract_quote_span,
)
from flint.sources.errors import RateLimitedError
from flint.sources.throttle import SourceThrottle
from flint.testing.replay import load_fixture

pytestmark = pytest.mark.compose  # 无 DB 依赖，但归 M2 集成族

FX = Path(__file__).resolve().parents[2] / "fixtures" / "evidence"
NOW = datetime(2026, 7, 31, tzinfo=UTC)


def _client(key: str) -> httpx.Client:
    """从录制夹具建离线回放 client（按 URL 返回录制响应；零联网）。"""
    exchanges = load_fixture(FX / key / "fetch.json")
    by_url = {ex.url: ex for ex in exchanges}

    def handler(request: httpx.Request) -> httpx.Response:
        ex = by_url.get(str(request.url))
        if ex is None:
            raise AssertionError(f"no recorded exchange for {request.url}")
        return httpx.Response(
            ex.status_code, content=ex.body_text.encode("utf-8"),
            headers={"content-type": ex.content_type})

    return httpx.Client(transport=httpx.MockTransport(handler))


# ── B-2 抓取器 ────────────────────────────────────────────────────────

def test_github_fetch_metadata_from_real_fixture() -> None:
    f = GithubRepoFetcher(_client("github_pallets_flask"))
    fetched = f.fetch("https://github.com/pallets/flask")
    assert fetched.source_id == "github" and fetched.kind == "repo"
    assert fetched.title == "pallets/flask"
    assert fetched.url == "https://github.com/pallets/flask"
    assert "micro framework" in fetched.summary


def test_arxiv_fetch_metadata_from_real_fixture() -> None:
    f = ArxivFetcher(_client("arxiv_1706.03762"))
    fetched = f.fetch("https://arxiv.org/abs/1706.03762")
    assert fetched.source_id == "arxiv" and fetched.kind == "paper"
    assert fetched.title == "Attention Is All You Need"
    assert fetched.published_at == date(2017, 6, 12)
    assert "sequence transduction" in fetched.summary


def test_supports_domain_matching() -> None:
    gh = GithubRepoFetcher(_client("github_pallets_flask"))
    ax = ArxivFetcher(_client("arxiv_1706.03762"))
    assert gh.supports("https://github.com/pallets/flask")
    assert not gh.supports("https://s.weibo.com/weibo?q=x")
    assert ax.supports("http://arxiv.org/abs/2607.10004v1")
    assert not ax.supports("https://github.com/pallets/flask")


def test_registry_dispatch_and_deferred_sources_unregistered() -> None:
    reg = DocFetcherRegistry()
    reg.register(GithubRepoFetcher(_client("github_pallets_flask")))
    reg.register(ArxivFetcher(_client("arxiv_1706.03762")))
    assert reg.fetch("https://github.com/pallets/flask").title == "pallets/flask"
    # 门 2=R1：weibo / news 未注册 → 明确报错（缓办，NEVER 静默抓）
    assert not reg.supports("https://s.weibo.com/weibo?q=x")
    with pytest.raises(UnregisteredSourceError):
        reg.fetch("https://s.weibo.com/weibo?q=x")
    with pytest.raises(UnregisteredSourceError):
        reg.fetch("https://news.example.com/2026-06-29/18")


def test_throttle_exhaustion_raises_ratelimited() -> None:
    throttle = SourceThrottle()
    throttle.configure("github", capacity=1, refill_per_second=0.001)  # ~不回填
    reg = DocFetcherRegistry(throttle=throttle)
    reg.register(GithubRepoFetcher(_client("github_pallets_flask")))
    reg.fetch("https://github.com/pallets/flask")            # first token ok
    with pytest.raises(RateLimitedError):
        reg.fetch("https://github.com/pallets/flask")        # bucket empty


# ── B-3 短 quote_span + Doc/Citation ─────────────────────────────────

def test_extract_first_sentence_only() -> None:
    s = "First sentence here. Second sentence should be dropped."
    assert extract_quote_span(s) == "First sentence here."


def test_extract_caps_length_no_fulltext() -> None:
    long = "x" * 5000  # 无句末标点的超长串
    span = extract_quote_span(long)
    assert len(span) <= MAX_SPAN_LEN + 1          # 封顶 + 省略号
    assert span.endswith("…")


def test_extract_empty_summary() -> None:
    assert extract_quote_span("") == ""            # 空 → 空串（诚实无引）


def test_build_doc_is_metadata_only() -> None:
    f = GithubRepoFetcher(_client("github_pallets_flask"))
    doc = build_doc(f.fetch("https://github.com/pallets/flask"), NOW)
    # Doc 冻结件无 content 字段——只有元信息 9 键
    assert set(vars(doc)) == {
        "doc_id", "source_id", "kind", "title", "url",
        "published_at", "meta", "origin", "access"}
    assert doc.origin == "retrieved" and doc.access == "public"


def test_build_citation_carries_short_span_and_fk() -> None:
    f = GithubRepoFetcher(_client("github_pallets_flask"))
    fetched = f.fetch("https://github.com/pallets/flask")
    doc = build_doc(fetched, NOW)
    span = extract_quote_span(fetched.summary)
    cit = build_citation("card-x", doc, span)
    assert cit.doc_id == doc.doc_id                # FK 指向 Doc
    assert cit.quote_span == span and len(cit.quote_span or "") <= MAX_SPAN_LEN
    assert "micro framework" in (cit.quote_span or "")
