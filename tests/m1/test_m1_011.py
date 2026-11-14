"""M1-011 acceptance tests: Google Trends adapter (TrendSource).

Acceptance (tasks.json M1-011):
  - fixture replay yields TrendItem objects with every field non-empty
  - the rate limiter takes effect under a fake-clock unit test
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from flint.domain.models import TrendItem
from flint.sources.errors import RateLimitedError, SourceFetchError
from flint.sources.gtrends import GoogleTrendsSource, RequestPacer, parse_traffic
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "gtrends"
NOW = datetime(2026, 7, 23, 8, 0, 0, tzinfo=UTC)


def test_fetch_daily_replay_all_fields_non_empty() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-23.json", mode="replay") as session,
        session.client() as client,
    ):
        source = GoogleTrendsSource(client=client, now=lambda: NOW)
        items = source.fetch_daily(date(2026, 7, 23))
    assert len(items) == 20
    for item in items:
        assert isinstance(item, TrendItem)
        assert item.keyword
        assert item.score > 0
        assert item.region
        assert item.url
        assert item.captured_at == NOW


def test_source_id_matches_registry_key() -> None:
    assert GoogleTrendsSource.source_id == "gtrends"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("200K+", 200_000.0), ("1M+", 1_000_000.0), ("500+", 500.0), ("2.5M+", 2_500_000.0)],
)
def test_parse_traffic(raw: str, expected: float) -> None:
    assert parse_traffic(raw) == expected


def test_rate_limiter_paces_under_fake_clock() -> None:
    clock = [100.0]
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    pacer = RequestPacer(min_interval=2.0, now=lambda: clock[0], sleep=fake_sleep)
    pacer.acquire()  # first call goes straight through
    assert sleeps == []
    pacer.acquire()  # immediate second call must wait the full interval
    assert sleeps == [2.0]
    clock[0] += 0.5
    pacer.acquire()  # 0.5s elapsed -> tops up the remaining 1.5s
    assert sleeps == [2.0, 1.5]
    clock[0] += 10.0
    pacer.acquire()  # long idle -> no wait
    assert sleeps == [2.0, 1.5]


def test_fetch_applies_pacer() -> None:
    clock = [0.0]
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    pacer = RequestPacer(min_interval=3.0, now=lambda: clock[0], sleep=fake_sleep)
    with (
        HttpReplay(FIXTURES / "2026-07-23.json", mode="replay") as session,
        session.client() as client,
    ):
        source = GoogleTrendsSource(client=client, now=lambda: NOW, pacer=pacer)
        source.fetch_daily(date(2026, 7, 23))
        source.fetch_daily(date(2026, 7, 23))
    assert sleeps == [3.0]


def test_429_raises_rate_limited() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-26.json", mode="replay") as session,
        session.client() as client,
    ):
        source = GoogleTrendsSource(client=client, now=lambda: NOW)
        with pytest.raises(RateLimitedError):
            source.fetch_daily(date(2026, 7, 26))


def test_5xx_raises_fetch_error() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-27.json", mode="replay") as session,
        session.client() as client,
    ):
        source = GoogleTrendsSource(client=client, now=lambda: NOW)
        with pytest.raises(SourceFetchError):
            source.fetch_daily(date(2026, 7, 27))
