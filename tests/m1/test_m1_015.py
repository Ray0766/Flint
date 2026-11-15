"""M1-015 acceptance tests: single-source degradation (E6 row 1).

Acceptance (tasks.json M1-015):
  - killing any single source's fixture leaves the other three running normally
  - a DegradationNote is persisted and the card layer gets its gap-annotation slot
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from flint.config import FeatureFlags, InMemoryFlagStore
from flint.sources.arxiv import ArxivSource
from flint.sources.degradation import (
    DegradationNote,
    InMemoryDegradationStore,
    card_gap_annotations,
    fetch_all_sources,
)
from flint.sources.ghtrend import GitHubTrendingSource
from flint.sources.gtrends import GoogleTrendsSource
from flint.sources.registry import SourceRegistry, source_flag_name
from flint.sources.weibo import WeiboHotSource
from flint.testing.replay import HttpReplay, RecordedExchange, save_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "fixtures"
DAY = date(2026, 7, 23)
NOW = datetime(2026, 7, 23, 8, 0, 0, tzinfo=UTC)
ALL_SOURCES = ["arxiv", "ghtrend", "gtrends", "weibo"]

ADAPTERS = {
    "gtrends": GoogleTrendsSource,
    "weibo": WeiboHotSource,
    "ghtrend": GitHubTrendingSource,
    "arxiv": ArxivSource,
}

# Each adapter's request URL for DAY — used to author "this source is down
# today" fixtures for the kill scenarios.
def _url_only_client() -> httpx.Client:
    """只用来调 `_url()`，**一个请求都不发**。

    裸 `httpx.Client()` 会被 `test_network_discipline` 判成
    「真实出网且无录制回放护栏」——**那把尺子是对的**：
    判据里出现一个没有 transport 的 client，形状上就是一次可能的真实出网，
    而「它只用来算 URL」这件事只有写的人知道。
    所以给它一个**一被用到就炸**的 transport：意图写在代码里，不在注释里。
    """
    def never(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("这个 client 只用来算 URL，NEVER 发请求")

    return httpx.Client(transport=httpx.MockTransport(never))


DAY_URLS = {
    # CN-04 / DEC-054：旧 dailytrends 已被 Google 下线（实测 404），
    # 换成还活着的 trending/rss。它**不吃日期**，所以这里也没有 ed= 了。
    "gtrends": "https://trends.google.com/trending/rss?geo=HK",
    "weibo": "https://s.weibo.com/top/summary?cate=realtimehot",
    # 这两条**从适配器算出来**，NEVER 写死（`CN-07`）：
    # 窗口是一个会改的口径（`created:>今天` 结构上恒空，改成了近 7 天），
    # 写死的话每改一次窗口都要有人记得回来同步这里——
    # 而忘记同步时报的是 `ReplayMiss`，看起来像夹具坏了。
    "ghtrend": GitHubTrendingSource(client=_url_only_client())._url(DAY),
    "arxiv": ArxivSource(client=_url_only_client())._url(DAY),
}


def build_registry(
    stack: ExitStack,
    tmp_path: Path,
    kill: str | None = None,
    kill_status: int = 503,
) -> SourceRegistry:
    """Wire all four adapters to replay fixtures; the killed source gets a
    same-day fixture answering with a failure status."""
    flags = FeatureFlags(store=InMemoryFlagStore(), now=lambda: 0.0)
    # Isolation is about four sources failing independently, so all four run here.
    # Weibo and Google Trends are off by default since `DEC-066` froze them
    # (`NARROW-05`); turning them on explicitly keeps this suite about isolation.
    for sid in ADAPTERS:
        flags.set(source_flag_name(sid), True)
    registry = SourceRegistry(flags=flags)
    for sid, adapter_cls in ADAPTERS.items():
        if sid == kill:
            fixture = tmp_path / sid / f"{DAY.isoformat()}.json"
            save_fixture(
                fixture,
                [RecordedExchange("GET", DAY_URLS[sid], kill_status, "text/plain", "down")],
            )
        else:
            fixture = FIXTURES / sid / f"{DAY.isoformat()}.json"
        session = stack.enter_context(HttpReplay(fixture, mode="replay"))
        client = stack.enter_context(session.client())

        def factory(
            cls: type = adapter_cls, c: httpx.Client = client
        ) -> GoogleTrendsSource | WeiboHotSource | GitHubTrendingSource | ArxivSource:
            return cls(client=c, now=lambda: NOW)

        registry.register(sid, factory)
    return registry


@pytest.mark.parametrize("victim", ALL_SOURCES)
def test_kill_any_source_others_continue(victim: str, tmp_path: Path) -> None:
    store = InMemoryDegradationStore()
    with ExitStack() as stack:
        registry = build_registry(stack, tmp_path, kill=victim)
        result = fetch_all_sources(registry, DAY, store=store)
    survivors = sorted(result.items)
    assert survivors == sorted(s for s in ALL_SOURCES if s != victim)
    for sid in survivors:
        assert result.items[sid], f"{sid} should keep producing items"
    assert [n.source_id for n in result.notes] == [victim]
    assert result.notes[0].reason == "fetch_failed"


def test_rate_limited_source_degrades_with_reason(tmp_path: Path) -> None:
    store = InMemoryDegradationStore()
    with ExitStack() as stack:
        registry = build_registry(stack, tmp_path, kill="gtrends", kill_status=429)
        result = fetch_all_sources(registry, DAY, store=store)
    assert sorted(result.items) == ["arxiv", "ghtrend", "weibo"]
    assert result.notes[0].reason == "rate_limited"


def test_all_healthy_produces_no_notes(tmp_path: Path) -> None:
    store = InMemoryDegradationStore()
    with ExitStack() as stack:
        registry = build_registry(stack, tmp_path, kill=None)
        result = fetch_all_sources(registry, DAY, store=store)
    assert sorted(result.items) == ALL_SOURCES
    assert result.notes == []
    assert store.for_day(DAY) == []


def test_degradation_note_is_persisted(tmp_path: Path) -> None:
    store = InMemoryDegradationStore()
    with ExitStack() as stack:
        registry = build_registry(stack, tmp_path, kill="weibo")
        fetch_all_sources(registry, DAY, store=store)
    persisted = store.for_day(DAY)
    assert len(persisted) == 1
    note = persisted[0]
    assert isinstance(note, DegradationNote)
    assert note.source_id == "weibo"
    assert note.day == DAY
    assert note.detail


def test_disabled_source_is_noted_not_fetched(tmp_path: Path) -> None:
    store = InMemoryDegradationStore()
    with ExitStack() as stack:
        registry = build_registry(stack, tmp_path, kill=None)
        registry.flags.set(source_flag_name("arxiv"), False)
        result = fetch_all_sources(registry, DAY, store=store)
    assert sorted(result.items) == ["ghtrend", "gtrends", "weibo"]
    assert [n.source_id for n in result.notes] == ["arxiv"]
    assert result.notes[0].reason == "disabled"


def test_card_gap_annotation_slot_text() -> None:
    """E6 row 1 user copy: 「今日缺 {源} 数据」 must appear on the card slot."""
    note = DegradationNote(
        day=DAY, source_id="weibo", reason="fetch_failed", detail="HTTP 503"
    )
    annotations = card_gap_annotations([note])
    assert len(annotations) == 1
    assert "今日缺 weibo 数据" in annotations[0]
    assert card_gap_annotations([]) == []
