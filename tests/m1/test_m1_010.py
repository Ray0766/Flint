"""M1-010 acceptance tests: SourceRegistry (config-driven register/enable/disable).

Acceptance (tasks.json M1-010):
  - any source can be switched on/off via configuration
  - an unregistered source kind raises an explicit error
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pytest

from flint.config import FeatureFlags, InMemoryFlagStore
from flint.domain.models import TrendItem
from flint.sources.registry import SourceRegistry, UnknownSourceError, source_flag_name


@dataclass
class StubSource:
    """Minimal structural TrendSource implementation."""

    source_id: str
    items: list[TrendItem] = field(default_factory=list)

    def fetch_daily(self, day: date) -> list[TrendItem]:
        return self.items


def make_registry() -> tuple[SourceRegistry, FeatureFlags]:
    flags = FeatureFlags(store=InMemoryFlagStore(), now=lambda: 0.0)
    registry = SourceRegistry(flags=flags)
    for sid in ("gtrends", "weibo", "ghtrend", "arxiv"):
        registry.register(sid, lambda sid=sid: StubSource(source_id=sid))
    return registry, flags


def test_flag_name_convention_matches_e8() -> None:
    assert source_flag_name("weibo") == "source_weibo_enabled"


def test_registered_sources_enabled_by_default() -> None:
    """Every registered source is on by default, except the two DEC-066 froze
    (Weibo, Google Trends): those are off until a flag turns them on (NARROW-05)."""
    registry, _ = make_registry()
    assert registry.enabled_source_ids() == ["arxiv", "ghtrend"]
    assert registry.source_ids() == ["arxiv", "ghtrend", "gtrends", "weibo"]


def test_disable_any_source_via_config() -> None:
    registry, flags = make_registry()
    flags.set(source_flag_name("gtrends"), True)
    flags.set(source_flag_name("weibo"), True)
    flags.set(source_flag_name("weibo"), False)
    assert registry.is_enabled("weibo") is False
    assert "weibo" not in registry.enabled_source_ids()
    # the other three keep running (degradation isolation is M1-015's scope)
    assert registry.enabled_source_ids() == ["arxiv", "ghtrend", "gtrends"]


def test_reenable_source_via_config() -> None:
    registry, flags = make_registry()
    flags.set(source_flag_name("arxiv"), False)
    assert registry.is_enabled("arxiv") is False
    flags.set(source_flag_name("arxiv"), True)
    assert registry.is_enabled("arxiv") is True


def test_create_returns_working_source() -> None:
    registry, _ = make_registry()
    src = registry.create("gtrends")
    assert src.source_id == "gtrends"
    assert src.fetch_daily(date(2026, 7, 26)) == []


def test_unregistered_kind_raises_explicit_error() -> None:
    registry, _ = make_registry()
    with pytest.raises(UnknownSourceError, match="tiktok"):
        registry.create("tiktok")
    with pytest.raises(UnknownSourceError, match="tiktok"):
        registry.is_enabled("tiktok")


def test_duplicate_registration_rejected() -> None:
    registry, _ = make_registry()
    with pytest.raises(ValueError, match="weibo"):
        registry.register("weibo", lambda: StubSource(source_id="weibo"))
