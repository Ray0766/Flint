"""Feature B-6：Gate① 真实 Searcher（github/arxiv 搜索 → Doc），离线回放（S2-7 零联网）。

断言：可注入的真实 searcher 从真实搜索响应回真 Doc（元信息），可替换 gate1 `_offline_searcher`
（占位 .example）。生产 Gate① 是否切真实源 = owner 决策，本测试不动 gate1 默认。
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from flint.domain.models import Query
from flint.evidence.search import (
    GithubArxivSearcher,
    arxiv_search_url,
    github_search_url,
)
from flint.testing.replay import load_fixture

pytestmark = pytest.mark.compose

FX = Path(__file__).resolve().parents[2] / "fixtures" / "evidence" / "search_transformer"
NOW = datetime(2026, 7, 31, tzinfo=UTC)
TEXT = "transformer attention"


def _client() -> httpx.Client:
    by_url = {ex.url: ex for ex in load_fixture(FX / "search.json")}

    def handler(request: httpx.Request) -> httpx.Response:
        ex = by_url[str(request.url)]
        return httpx.Response(ex.status_code, content=ex.body_text.encode("utf-8"),
                              headers={"content-type": ex.content_type})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _query() -> Query:
    return Query(text=TEXT, source_kinds=["repo", "paper"], intent="landscape",
                 locale="en")


def test_searcher_returns_real_docs_from_both_sources() -> None:
    searcher = GithubArxivSearcher(_client(), NOW, per_source=3)
    docs = searcher(_query())
    kinds = {d.kind for d in docs}
    assert "repo" in kinds and "paper" in kinds          # 两源都出真 Doc
    assert all(d.origin == "retrieved" and d.access == "public" for d in docs)
    # 真实身份（非 .example 占位）：github flask、arxiv 真 url
    assert any("github.com" in d.url for d in docs)
    assert any("arxiv.org" in d.url for d in docs)
    assert all(".example" not in d.url for d in docs)    # 非合成占位


def test_docs_are_metadata_only_no_content() -> None:
    docs = GithubArxivSearcher(_client(), NOW)(_query())
    for d in docs:
        assert set(vars(d)) == {
            "doc_id", "source_id", "kind", "title", "url",
            "published_at", "meta", "origin", "access"}     # 无 content 字段


def test_search_url_builders() -> None:
    assert "q=transformer+attention" in github_search_url(TEXT, 3)
    assert "search_query=all:transformer+attention" in arxiv_search_url(TEXT, 3)
