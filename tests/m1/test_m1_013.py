"""M1-013 acceptance tests: GitHub Trending adapter (TrendSource).

Acceptance (tasks.json M1-013):
  - repo -> keyword mapping covers all three origins (name / topic / description)
    with unit tests
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from flint.sources.errors import RateLimitedError, SourceFetchError
from flint.sources.ghtrend import DerivedKeyword, GitHubTrendingSource, map_repo_keywords
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "ghtrend"
NOW = datetime(2026, 7, 23, 8, 0, 0, tzinfo=UTC)

SAMPLE_REPO = {
    "full_name": "acme/solid-sim",
    "description": "Solid-state battery cell simulator",
    "topics": ["battery", "materials"],
    "stargazers_count": 1200,
    "html_url": "https://github.com/acme/solid-sim",
}


def test_mapping_covers_name_origin() -> None:
    keywords = map_repo_keywords(SAMPLE_REPO)
    assert DerivedKeyword(text="solid sim", origin="name") in keywords


def test_mapping_covers_topic_origin() -> None:
    keywords = map_repo_keywords(SAMPLE_REPO)
    assert DerivedKeyword(text="battery", origin="topic") in keywords
    assert DerivedKeyword(text="materials", origin="topic") in keywords


def test_mapping_covers_description_origin() -> None:
    keywords = map_repo_keywords(SAMPLE_REPO)
    description_terms = {k.text for k in keywords if k.origin == "description"}
    assert description_terms, "description must contribute keyword candidates"
    assert "simulator" in description_terms


def test_mapping_dedupes_across_origins() -> None:
    """'battery' appears both as topic and in the description; earlier origin
    (name > topic > description) wins and the keyword appears exactly once."""
    keywords = map_repo_keywords(SAMPLE_REPO)
    battery = [k for k in keywords if k.text == "battery"]
    assert len(battery) == 1
    assert battery[0].origin == "topic"


def test_mapping_underscore_and_case_normalized() -> None:
    repo = dict(SAMPLE_REPO, full_name="Lab/Tiny_LLM", topics=[], description="")
    keywords = map_repo_keywords(repo)
    assert DerivedKeyword(text="tiny llm", origin="name") in keywords


def test_fetch_daily_replay_yields_items_from_all_origins() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-23.json", mode="replay") as session,
        session.client() as client,
    ):
        source = GitHubTrendingSource(client=client, now=lambda: NOW)
        items = source.fetch_daily(date(2026, 7, 23))
    assert len(items) >= 15
    for item in items:
        assert item.keyword
        assert item.score > 0
        assert item.region == "global"
        assert item.url.startswith("https://github.com/")
        assert item.captured_at == NOW
    keywords = {i.keyword for i in items}
    assert "claude flow" in keywords  # name origin
    assert "agents" in keywords  # topic origin


def test_source_id_matches_registry_key() -> None:
    assert GitHubTrendingSource.source_id == "ghtrend"


def test_429_and_5xx_raise() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-26.json", mode="replay") as session,
        session.client() as client,
    ):
        source = GitHubTrendingSource(client=client, now=lambda: NOW)
        with pytest.raises(RateLimitedError):
            source.fetch_daily(date(2026, 7, 26))
    with (
        HttpReplay(FIXTURES / "2026-07-27.json", mode="replay") as session,
        session.client() as client,
    ):
        source = GitHubTrendingSource(client=client, now=lambda: NOW)
        with pytest.raises(SourceFetchError):
            source.fetch_daily(date(2026, 7, 27))
