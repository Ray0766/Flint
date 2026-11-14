"""M2-012 acceptance tests: CompetitorSource adapter.

Acceptance: every competitor Doc carries a reachable source url (replay);
name normalization + dedup unit-tested.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from flint.domain.models import Query
from flint.evidence.competitor import ProductSearchSource, normalize_competitor_name
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "evidence6" / "competitor"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
QUERY = Query(
    text="solid state battery", source_kinds=["product"], intent="landscape", locale="en"
)


def test_replay_docs_have_reachable_urls() -> None:
    with (
        HttpReplay(FIXTURES / "solid-state-battery.json", mode="replay") as session,
        session.client() as client,
    ):
        docs = ProductSearchSource(client=client, now=lambda: NOW).search(QUERY, limit=10)
    assert len(docs) == 4
    for doc in docs:
        assert doc.kind == "product" and doc.source_id == "products"
        assert doc.url.startswith("https://"), "reachable source url is mandatory"
        assert doc.meta["last_activity"]
        assert doc.meta["fetched_at"] == NOW.isoformat()


def test_name_normalization_and_dedup() -> None:
    assert normalize_competitor_name("  Solid  State  VENDOR ") == "solid state vendor"
    assert normalize_competitor_name("Solid-State Vendor, Inc.") == "solid-state vendor inc"

    with (
        HttpReplay(FIXTURES / "solid-state-battery.json", mode="replay") as session,
        session.client() as client,
    ):
        source = ProductSearchSource(client=client, now=lambda: NOW)
        docs = source.search(QUERY, limit=10)
    names = [normalize_competitor_name(d.title) for d in docs]
    assert len(names) == len(set(names)), "normalized names are deduped"
