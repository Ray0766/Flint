"""M3-014 acceptance tests: profile storage + sensitivity.

Acceptance (tasks.json M3-014):
  - UserProfile field groups persist + sensitivity grading (D12)
  - reads filter by scope (unauthorized fields never leave the store)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import DEFAULT_PROFILE_SENSITIVITY, Principal, UserProfile
from flint.profile.store import PgProfileStore, scoped_view

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM profiles WHERE profile_id LIKE 'm3014-%'")
        finally:
            await conn.close()

    run(wipe())


def make_profile(**overrides: Any) -> UserProfile:
    base: dict[str, Any] = {
        "profile_id": "m3014-p1",
        "owner": Principal(kind="user", id="u-1"),
        "identity": {"name": "Ray", "org": "Flint Lab", "role": "founder"},
        "research": {"directions": ["battery"], "publications": ["doi:10.1/x"]},
        "team": [{"name": "A", "role": "eng"}],
        "assets": {"gpu": "1x4090"},
        "constraints": {"budget_range": [50000, 200000], "hours_per_week": 20},
        "track_record": [{"project": "prior", "outcome": "shipped"}],
        "locale": "zh-CN",
        "sensitivity_overrides": {},
        "updated_at": NOW,
    }
    base.update(overrides)
    return UserProfile(**base)


def test_default_sensitivity_frozen_shape() -> None:
    assert DEFAULT_PROFILE_SENSITIVITY["constraints.budget_range"] == "owner_only"
    assert DEFAULT_PROFILE_SENSITIVITY["*"] == "team"


def test_save_load_round_trip() -> None:
    store = PgProfileStore(dsn=DSN)
    profile = make_profile()
    run(store.save(profile))
    loaded = run(store.load("m3014-p1"))
    assert loaded == profile


def test_scoped_view_team_drops_owner_only_fields() -> None:
    profile = make_profile()
    team_view = scoped_view(profile, viewer_role="team")
    assert "budget_range" not in team_view.constraints, "default owner_only dropped"
    assert team_view.constraints["hours_per_week"] == 20, "team-level fields kept"
    assert team_view.identity == profile.identity

    owner_view = scoped_view(profile, viewer_role="owner")
    assert owner_view.constraints == profile.constraints, "owner sees everything"


def test_sensitivity_override_honored() -> None:
    profile = make_profile(
        sensitivity_overrides={"research.publications": "owner_only"}
    )
    team_view = scoped_view(profile, viewer_role="team")
    assert "publications" not in team_view.research
    assert team_view.research["directions"] == ["battery"]


def test_scoped_load_never_leaks() -> None:
    store = PgProfileStore(dsn=DSN)
    run(store.save(make_profile()))
    team_loaded = run(store.load("m3014-p1", viewer_role="team"))
    assert "budget_range" not in team_loaded.constraints, "filter applied at the store"
