"""M2-019 acceptance tests: multi-query result merge + dedup.

Acceptance (tasks.json M2-019):
  - concurrent multi-query results merge with DOI/URL dedup
  - embedding near-neighbor assisted dedup with a configurable threshold
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.domain.models import Doc
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.retrieval.multiquery import merge_results

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(doc_id: str, title: str, url: str, doi: str | None = None) -> Doc:
    meta: dict[str, object] = {"fetched_at": FETCHED}
    if doi:
        meta["doi"] = doi
    return Doc(
        doc_id=doc_id, source_id="crossref", kind="paper", title=title, url=url,
        published_at=date(2026, 1, 1), meta=meta, origin="retrieved", access="public",
    )


def embedder() -> EmbeddingService:
    return EmbeddingService(backend=DeterministicHashBackend(dim=64))


def test_doi_url_dedup_across_result_sets() -> None:
    set_a = [
        make_doc("d1", "Paper One", "https://a/1", doi="10.1/x"),
        make_doc("d2", "Paper Two", "https://a/2"),
    ]
    set_b = [
        make_doc("d3", "Paper One again", "https://b/1", doi="10.1/x"),  # same DOI
        make_doc("d4", "Paper Two", "https://a/2"),                      # same URL
        make_doc("d5", "Paper Three", "https://b/3"),
    ]
    merged = merge_results([set_a, set_b], embedder=None)
    assert [d.doc_id for d in merged] == ["d1", "d2", "d5"], "first-seen wins, order kept"


def test_embedding_near_dup_removed() -> None:
    set_a = [make_doc("d1", "Solid-state battery survey", "https://a/1")]
    set_b = [make_doc("d2", "Solid-state battery survey", "https://b/9")]  # 异 URL 同题
    merged = merge_results([set_a, set_b], embedder=embedder(), near_dup_threshold=0.95)
    assert [d.doc_id for d in merged] == ["d1"], "identical titles collapse via embedding"


def test_near_dup_threshold_configurable() -> None:
    set_a = [make_doc("d1", "Solid-state battery survey", "https://a/1")]
    set_b = [make_doc("d2", "Solid-state battery survey", "https://b/9")]
    kept = merge_results([set_a, set_b], embedder=embedder(), near_dup_threshold=1.01)
    assert len(kept) == 2, "threshold beyond max similarity disables near-dup removal"


def test_distinct_titles_survive() -> None:
    set_a = [make_doc("d1", "Solid-state battery survey", "https://a/1")]
    set_b = [make_doc("d2", "Drone delivery economics", "https://b/2")]
    merged = merge_results([set_a, set_b], embedder=embedder(), near_dup_threshold=0.95)
    assert len(merged) == 2


def test_empty_sets() -> None:
    assert merge_results([], embedder=None) == []
    assert merge_results([[], []], embedder=embedder()) == []
