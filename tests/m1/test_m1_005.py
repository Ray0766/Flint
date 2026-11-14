"""M1-005 acceptance tests: config loading + feature flag skeleton (E8).

Acceptance (tasks.json M1-005):
  - missing required env -> startup fails and lists every missing key
  - flag table read/write + 5min cache unit tests pass
"""
from __future__ import annotations

import pytest

from flint.config import (
    REQUIRED_ENV_KEYS,
    ConfigError,
    FeatureFlags,
    InMemoryFlagStore,
    Settings,
    load_settings,
)

FULL_ENV = {
    "FLINT_ENV": "dev",
    "DATABASE_URL": "postgresql+asyncpg://flint:flint@localhost:5432/flint",
    "REDIS_URL": "redis://localhost:6379/0",
}


# ── settings ──────────────────────────────────────────────


def test_missing_all_required_env_lists_every_key() -> None:
    with pytest.raises(ConfigError) as exc:
        load_settings({})
    assert sorted(exc.value.missing) == sorted(REQUIRED_ENV_KEYS)
    for key in REQUIRED_ENV_KEYS:
        assert key in str(exc.value)


def test_missing_single_env_lists_only_that_key() -> None:
    env = dict(FULL_ENV)
    del env["REDIS_URL"]
    with pytest.raises(ConfigError) as exc:
        load_settings(env)
    assert exc.value.missing == ["REDIS_URL"]


def test_load_settings_ok() -> None:
    s = load_settings(FULL_ENV)
    assert isinstance(s, Settings)
    assert s.env == "dev"
    assert s.database_url == FULL_ENV["DATABASE_URL"]
    assert s.redis_url == FULL_ENV["REDIS_URL"]


def test_unknown_environment_name_rejected() -> None:
    env = dict(FULL_ENV, FLINT_ENV="qa")
    with pytest.raises(ConfigError) as exc:
        load_settings(env)
    assert "FLINT_ENV" in str(exc.value)


# ── feature flags: table read/write + 5min cache ──────────


def make_flags(store: InMemoryFlagStore, start: float = 1000.0) -> tuple[FeatureFlags, list[float]]:
    clock = [start]
    flags = FeatureFlags(store=store, now=lambda: clock[0])
    return flags, clock


def test_flag_write_then_read_roundtrip() -> None:
    store = InMemoryFlagStore()
    flags, _ = make_flags(store)
    flags.set("source_weibo_enabled", True)
    assert flags.is_enabled("source_weibo_enabled") is True
    flags.set("source_weibo_enabled", False)
    assert flags.is_enabled("source_weibo_enabled") is False


def test_unknown_flag_falls_back_to_default() -> None:
    flags, _ = make_flags(InMemoryFlagStore())
    assert flags.is_enabled("no_such_flag") is False
    assert flags.is_enabled("no_such_flag", default=True) is True


def test_billing_disabled_by_default() -> None:
    """S1 non-goal: billing stays off before M5 (E8: billing_enabled=false)."""
    flags, _ = make_flags(InMemoryFlagStore())
    assert flags.is_enabled("billing_enabled", default=True) is False


def test_cache_serves_reads_for_300s_then_refreshes() -> None:
    store = InMemoryFlagStore()
    store.write("revalidation_enabled", True)
    flags, clock = make_flags(store)

    assert flags.is_enabled("revalidation_enabled") is True
    reads_after_first = store.read_count

    # Backend value changes behind the cache.
    store.write("revalidation_enabled", False)

    clock[0] += 299.0  # still inside the 5min window: cached value, no new read
    assert flags.is_enabled("revalidation_enabled") is True
    assert store.read_count == reads_after_first

    clock[0] += 2.0  # 301s since fill: cache expired, backend re-read
    assert flags.is_enabled("revalidation_enabled") is False
    assert store.read_count > reads_after_first


def test_set_invalidates_cache_immediately() -> None:
    store = InMemoryFlagStore()
    store.write("manual_degrade_llm", False)
    flags, _ = make_flags(store)
    assert flags.is_enabled("manual_degrade_llm") is False
    flags.set("manual_degrade_llm", True)  # write-through must not serve stale False
    assert flags.is_enabled("manual_degrade_llm") is True
