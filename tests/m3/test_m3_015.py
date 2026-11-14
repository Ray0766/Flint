"""M3-015 acceptance tests: ProfileRef channel + missing_permission wiring.

Acceptance (tasks.json M3-015):
  - self-referential sections cite only via ProfileRef (naked profile values
    in blocks rejected)
  - unauthorized field group -> GapHint(missing_permission, required_scope)
    (audit 8)
"""
from __future__ import annotations

from datetime import UTC, datetime

from flint.domain.models import (
    GapHint,
    Principal,
    ProfileRef,
    TextSpan,
    UserProfile,
)
from flint.profile.ref import (
    find_naked_profile_values,
    make_ref_or_gap,
    resolve_profile_field,
)
from flint.profile.store import scoped_view

NOW = datetime(2026, 7, 29, tzinfo=UTC)


def make_profile() -> UserProfile:
    return UserProfile(
        profile_id="p-1", owner=Principal(kind="user", id="u-1"),
        identity={"name": "Ray", "org": "Flint Lab"},
        research={"publications": ["doi:10.1/x", "doi:10.2/y"]},
        team=[{"name": "A"}], assets={"gpu": "1x4090"},
        constraints={"budget_range": [50000, 200000], "hours_per_week": 20},
        track_record=[], locale="zh-CN", sensitivity_overrides={},
        updated_at=NOW,
    )


def test_resolve_and_ref_happy_path() -> None:
    profile = make_profile()
    assert resolve_profile_field(profile, "identity.org") == "Flint Lab"
    assert resolve_profile_field(profile, "research.publications[1]") == "doi:10.2/y"

    ref = make_ref_or_gap(profile, "identity.org", viewer_role="owner")
    assert isinstance(ref, ProfileRef)
    assert ref.field_path == "identity.org"


def test_unauthorized_field_yields_missing_permission_gap() -> None:
    profile = make_profile()
    team_view = scoped_view(profile, viewer_role="team")
    gap = make_ref_or_gap(team_view, "constraints.budget_range", viewer_role="team")
    assert isinstance(gap, GapHint)
    assert gap.cause == "missing_permission"
    assert gap.action == "request_permission"
    assert gap.required_scope == "constraints.budget_range"
    assert gap.suggested_sources == [], "never disguised as missing data (audit 8)"


def test_absent_field_yields_missing_data_gap() -> None:
    gap = make_ref_or_gap(make_profile(), "research.orcid", viewer_role="owner")
    assert isinstance(gap, GapHint)
    assert gap.cause == "missing_data"
    assert gap.action == "ask_user"
    assert gap.required_scope is None


def test_naked_profile_values_detected_in_spans() -> None:
    profile = make_profile()
    spans = [
        TextSpan(kind="text", text="本团队隶属 "),
        TextSpan(kind="text", text="Flint Lab"),          # 裸值：identity.org
        ProfileRef(kind="profile", field_path="identity.org"),  # 通道内，合法
        TextSpan(kind="text", text="doi:10.1/x"),          # 裸值：publications[0]
        TextSpan(kind="text", text="预算充足"),             # 普通文本
    ]
    violations = find_naked_profile_values(spans, profile)
    assert len(violations) == 2
    assert "Flint Lab" in violations[0] and "doi:10.1/x" in violations[1]


def test_clean_spans_pass() -> None:
    profile = make_profile()
    spans = [
        TextSpan(kind="text", text="团队情况见 "),
        ProfileRef(kind="profile", field_path="team"),
    ]
    assert find_naked_profile_values(spans, profile) == []
