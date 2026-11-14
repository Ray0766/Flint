"""M2-010 acceptance tests: PatentSource adapter.

Acceptance: patent Doc carries family_size and legal_status meta;
structure drift raises ParseDrift instead of silent bad data.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from flint.domain.models import Query
from flint.evidence.patent import PatentSearchSource, parse_patents
from flint.sources.errors import ParseDrift
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "evidence6" / "patent"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
QUERY = Query(text="solid state battery", source_kinds=["patent"], intent="landscape", locale="en")


def test_replay_docs_carry_family_and_legal_meta() -> None:
    with (
        HttpReplay(FIXTURES / "solid-state-battery.json", mode="replay") as session,
        session.client() as client,
    ):
        docs = PatentSearchSource(client=client, now=lambda: NOW).search(
            QUERY, since=None, limit=10
        )
    assert len(docs) == 5
    for doc in docs:
        assert doc.kind == "patent" and doc.source_id == "patents"
        assert isinstance(doc.meta["family_size"], int)
        assert doc.meta["legal_status"] in ("active", "pending")
        assert doc.meta["fetched_at"] == NOW.isoformat()
        assert doc.origin == "retrieved"


def test_structure_drift_raises() -> None:
    with pytest.raises(ParseDrift):
        parse_patents("<html>maintenance</html>", now=NOW)
    with pytest.raises(ParseDrift):
        parse_patents('{"unexpected": []}', now=NOW)
