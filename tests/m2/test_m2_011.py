"""M2-011 acceptance tests: NewsSource adapter.

Acceptance: news Doc carries media_tier and independent_sources meta;
published-date parsing golden cases pass.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from flint.domain.models import Query
from flint.evidence.news import NewsApiSource, parse_published_date
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "evidence6" / "news"
NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC)
QUERY = Query(text="solid state battery", source_kinds=["news"], intent="support", locale="en")


def test_replay_docs_carry_media_meta() -> None:
    with (
        HttpReplay(FIXTURES / "solid-state-battery.json", mode="replay") as session,
        session.client() as client,
    ):
        docs = NewsApiSource(client=client, now=lambda: NOW).search(
            QUERY, since=None, limit=10
        )
    assert len(docs) == 5
    for doc in docs:
        assert doc.kind == "news" and doc.source_id == "news"
        assert doc.meta["media_tier"] in (1, 2, 3)
        assert doc.meta["independent_sources"] >= 1
        assert doc.published_at is not None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-07-10T08:00:00Z", date(2026, 7, 10)),
        ("2026-07-10T23:59:59+08:00", date(2026, 7, 10)),
        ("2026-07-10", date(2026, 7, 10)),
    ],
)
def test_published_date_golden(raw: str, expected: date) -> None:
    assert parse_published_date(raw) == expected


def test_unparseable_date_returns_none() -> None:
    assert parse_published_date("last Tuesday") is None
