"""M1-012 acceptance tests: Weibo hot-search adapter (TrendSource).

Acceptance (tasks.json M1-012):
  - board parse yields >=50 entries with complete fields
  - upstream page-structure drift raises ParseDrift instead of silently
    emitting wrong data
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from flint.domain.models import TrendItem
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError
from flint.sources.weibo import WeiboHotSource, parse_board
from flint.testing.replay import HttpReplay

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures" / "weibo"
NOW = datetime(2026, 7, 23, 8, 0, 0, tzinfo=UTC)


def test_fetch_daily_replay_yields_50_complete_entries() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-23.json", mode="replay") as session,
        session.client() as client,
    ):
        source = WeiboHotSource(client=client, now=lambda: NOW)
        items = source.fetch_daily(date(2026, 7, 23))
    assert len(items) >= 50
    for item in items:
        assert isinstance(item, TrendItem)
        assert item.keyword
        assert item.score > 0
        assert item.region == "CN"
        assert item.url.startswith("https://s.weibo.com/weibo?q=")
        assert item.captured_at == NOW


def test_source_id_matches_registry_key() -> None:
    assert WeiboHotSource.source_id == "weibo"


def test_parse_board_extracts_keyword_score_url() -> None:
    html = (
        '<table><tbody><tr><td class="td-01 ranktop">1</td>'
        '<td class="td-02"><a href="/weibo?q=%23固态电池%23">固态电池</a>'
        "<span>2963000</span></td></tr></tbody></table>"
    )
    items = parse_board(html, now=NOW)
    assert len(items) == 1
    assert items[0].keyword == "固态电池"
    assert items[0].score == 2_963_000.0
    assert items[0].url == "https://s.weibo.com/weibo?q=%23固态电池%23"


def test_drift_no_rows_raises() -> None:
    with pytest.raises(ParseDrift):
        parse_board("<html><body><p>improved page!</p></body></html>", now=NOW)


def test_drift_renamed_cell_class_raises() -> None:
    html = (
        '<table><tbody><tr><td class="cell-rank">1</td>'
        '<td class="cell-word"><a href="/weibo?q=x">词条</a><span>100</span></td>'
        "</tr></tbody></table>"
    )
    with pytest.raises(ParseDrift):
        parse_board(html, now=NOW)


def test_drift_missing_heat_span_raises() -> None:
    html = (
        '<table><tbody><tr><td class="td-01">1</td>'
        '<td class="td-02"><a href="/weibo?q=x">词条</a></td></tr></tbody></table>'
    )
    with pytest.raises(ParseDrift):
        parse_board(html, now=NOW)


def test_drift_non_numeric_heat_raises() -> None:
    html = (
        '<table><tbody><tr><td class="td-01">1</td>'
        '<td class="td-02"><a href="/weibo?q=x">词条</a><span>爆</span></td>'
        "</tr></tbody></table>"
    )
    with pytest.raises(ParseDrift):
        parse_board(html, now=NOW)


def test_429_and_5xx_raise() -> None:
    with (
        HttpReplay(FIXTURES / "2026-07-26.json", mode="replay") as session,
        session.client() as client,
    ):
        source = WeiboHotSource(client=client, now=lambda: NOW)
        with pytest.raises(RateLimitedError):
            source.fetch_daily(date(2026, 7, 26))
    with (
        HttpReplay(FIXTURES / "2026-07-27.json", mode="replay") as session,
        session.client() as client,
    ):
        source = WeiboHotSource(client=client, now=lambda: NOW)
        with pytest.raises(SourceFetchError):
            source.fetch_daily(date(2026, 7, 27))
