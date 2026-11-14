"""M2-009 acceptance tests: PaperSource adapter (Crossref-shaped).

Acceptance: replay yields Doc with every field non-empty and origin=retrieved;
DOI/URL merge-dedup unit-tested.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from flint.domain.models import Doc, Query
from flint.evidence.paper import CrossrefPaperSource, dedupe_by_doi_url
from flint.sources.errors import RateLimitedError, SourceFetchError
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "evidence6" / "paper"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
QUERY = Query(text="solid state battery", source_kinds=["paper"], intent="support", locale="en")


def search(fixture: str, query: Query = QUERY, limit: int = 10) -> list[Doc]:
    with (
        HttpReplay(FIXTURES / f"{fixture}.json", mode="replay") as session,
        session.client() as client,
    ):
        source = CrossrefPaperSource(client=client, now=lambda: NOW)
        return source.search(query, since=None, limit=limit)


def test_replay_yields_complete_retrieved_docs() -> None:
    docs = search("solid-state-battery")
    assert len(docs) == 6
    for doc in docs:
        assert isinstance(doc, Doc)
        assert doc.doc_id and doc.source_id == "crossref"
        assert doc.kind == "paper"
        assert doc.title and doc.url
        assert doc.published_at is not None
        assert doc.origin == "retrieved" and doc.access == "public"
        assert doc.meta["fetched_at"] == NOW.isoformat()
        assert "cited_by" in doc.meta


def test_dedupe_by_doi_url() -> None:
    docs = search("solid-state-battery")
    doubled = docs + [docs[0], docs[1]]
    merged = dedupe_by_doi_url(doubled)
    assert len(merged) == 6
    assert [d.doc_id for d in merged] == [d.doc_id for d in docs], "first wins, order kept"


def test_rate_limit_and_failure_raise() -> None:
    probe = Query(text="probe", source_kinds=["paper"], intent="support", locale="en")
    with pytest.raises(RateLimitedError):
        search("ratelimit", query=probe)
    with pytest.raises(SourceFetchError):
        search("failure", query=probe)
