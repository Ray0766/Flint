"""M1-014 acceptance tests: arXiv adapter (TrendSource side).

Acceptance (tasks.json M1-014):
  - Atom parsing yields the day's keyword candidates
  - category filtering is configuration-driven
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from flint.sources.arxiv import ArxivSource, parse_atom
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "arxiv"
NOW = datetime(2026, 7, 23, 8, 0, 0, tzinfo=UTC)
DAY = date(2026, 7, 23)


def test_fetch_daily_yields_keyword_candidates() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-23.json", mode="replay") as session,
        session.client() as client,
    ):
        source = ArxivSource(client=client, now=lambda: NOW)
        items = source.fetch_daily(DAY)
    assert len(items) == 12
    for item in items:
        assert item.keyword
        assert item.keyword == item.keyword.lower()
        assert item.score > 0
        assert item.region == "global"
        assert item.url.startswith("http://arxiv.org/abs/")
        assert item.captured_at == NOW


def test_category_filter_is_configurable() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-23.json", mode="replay") as session,
        session.client() as client,
    ):
        only_ai = ArxivSource(
            client=client, now=lambda: NOW, categories=frozenset({"cs.AI"})
        )
        ai_items = only_ai.fetch_daily(DAY)
    with (
        HttpReplay(FIXTURES / "2026-07-23.json", mode="replay") as session,
        session.client() as client,
    ):
        only_lg = ArxivSource(
            client=client, now=lambda: NOW, categories=frozenset({"cs.LG"})
        )
        lg_items = only_lg.fetch_daily(DAY)
    assert len(ai_items) == 8
    assert len(lg_items) == 4
    assert len(ai_items) + len(lg_items) == 12


def test_source_id_matches_registry_key() -> None:
    assert ArxivSource.source_id == "arxiv"


def test_invalid_atom_raises_parse_drift() -> None:
    with pytest.raises(ParseDrift):
        parse_atom("this is not xml at all", categories=None)
    with pytest.raises(ParseDrift):
        parse_atom("<html><body>maintenance page</body></html>", categories=None)


def test_429_and_5xx_raise() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-26.json", mode="replay") as session,
        session.client() as client,
    ):
        source = ArxivSource(client=client, now=lambda: NOW)
        with pytest.raises(RateLimitedError):
            source.fetch_daily(date(2026, 7, 26))
    with (
        HttpReplay(FIXTURES / "2026-07-27.json", mode="replay") as session,
        session.client() as client,
    ):
        source = ArxivSource(client=client, now=lambda: NOW)
        with pytest.raises(SourceFetchError):
            source.fetch_daily(date(2026, 7, 27))
