"""M2-015 acceptance tests: evidence provenance compliance + snapshot wiring.

Acceptance (tasks.json M2-015):
  - six-source results: source_id/url/fetched_at spot-check with zero misses
  - full retrieval results land in SnapshotStore and replay by snapshot_id
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Doc, Query
from flint.evidence.competitor import ProductSearchSource
from flint.evidence.compliance import (
    check_provenance,
    load_docs_snapshot,
    restore_docs,
    serialize_docs,
    snapshot_docs,
)
from flint.evidence.funding import FundingSourceStub
from flint.evidence.news import NewsApiSource
from flint.evidence.paper import CrossrefPaperSource
from flint.evidence.patent import PatentSearchSource
from flint.store.snapshot import PgSnapshotStore
from flint.testing.replay import HttpReplay

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "evidence6"
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
QUERY = Query(text="solid state battery", source_kinds=["paper"], intent="support", locale="en")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def collect_six_source_docs() -> list[Doc]:
    docs: list[Doc] = []
    adapters = [
        ("paper", lambda c: CrossrefPaperSource(client=c, now=lambda: NOW).search(QUERY, None, 10)),
        ("patent", lambda c: PatentSearchSource(client=c, now=lambda: NOW).search(QUERY, None, 10)),
        ("news", lambda c: NewsApiSource(client=c, now=lambda: NOW).search(QUERY, None, 10)),
        ("competitor", lambda c: ProductSearchSource(client=c, now=lambda: NOW).search(QUERY, 10)),
    ]
    for source, fetch in adapters:
        with (
            HttpReplay(FIXTURES / source / "solid-state-battery.json", mode="replay") as session,
            session.client() as client,
        ):
            docs.extend(fetch(client))
    docs.extend(FundingSourceStub().search("solid state battery"))  # 空集也过合规面
    return docs


def test_spot_check_zero_provenance_misses() -> None:
    docs = collect_six_source_docs()
    assert len(docs) == 6 + 5 + 5 + 4
    assert check_provenance(docs) == [], "source_id/url/fetched_at must never miss"


def test_provenance_violations_are_reported() -> None:
    docs = collect_six_source_docs()
    broken_url = replace(docs[0], url="")
    meta_without_fetch = dict(docs[1].meta)
    del meta_without_fetch["fetched_at"]
    broken_meta = replace(docs[1], meta=meta_without_fetch)
    violations = check_provenance([broken_url, broken_meta])
    assert len(violations) == 2
    assert "url" in violations[0]
    assert "fetched_at" in violations[1]


def test_serialize_restore_roundtrip() -> None:
    docs = collect_six_source_docs()
    payload = serialize_docs(docs)
    assert isinstance(payload, bytes)
    assert restore_docs(payload) == docs, "byte roundtrip must be lossless"


def test_snapshot_store_wiring_end_to_end() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-m2015-%'")
        finally:
            await conn.close()

    run(wipe())
    docs = collect_six_source_docs()
    store = PgSnapshotStore(dsn=DSN, id_factory=lambda: "snap-m2015-1", now=lambda: NOW)
    snapshot_id = run(snapshot_docs(store, docs))
    assert snapshot_id == "snap-m2015-1", "id feeds GenerationRecord.retrieval_snapshot_id"
    restored = run(load_docs_snapshot(store, snapshot_id))
    assert restored == docs, "any analysis can replay from its snapshot (F2)"
