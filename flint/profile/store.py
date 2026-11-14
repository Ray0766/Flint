"""Profile 存储与敏感度过滤（M3-014，冻结件 UserProfile / D10 / D12）。

- 敏感度两级（Sensitivity：team / owner_only，v0.3.1 §1.8 冻结）；生效表 =
  DEFAULT_PROFILE_SENSITIVITY 叠加 profile.sensitivity_overrides（键 =
  字段路径，如 "constraints.budget_range"）。
- scoped_view：viewer_role=="team" 时剔除 owner_only 路径（顶层.子键 两级
  路径口径）；过滤在 store 读取面执行——无权字段不出库（验收硬条款）。
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from typing import Any, Literal

import asyncpg

from flint.domain.models import (
    DEFAULT_PROFILE_SENSITIVITY,
    Principal,
    Sensitivity,
    UserProfile,
)

ViewerRole = Literal["owner", "team"]

_GROUP_FIELDS = ("identity", "research", "team", "assets", "constraints",
                 "track_record")


def _effective_sensitivity(profile: UserProfile) -> dict[str, Sensitivity]:
    effective: dict[str, Sensitivity] = dict(DEFAULT_PROFILE_SENSITIVITY)
    effective.update(profile.sensitivity_overrides)
    return effective


def scoped_view(profile: UserProfile, viewer_role: ViewerRole) -> UserProfile:
    if viewer_role == "owner":
        return profile
    owner_only_paths = [
        path for path, level in _effective_sensitivity(profile).items()
        if level == "owner_only" and path != "*"
    ]
    updates: dict[str, Any] = {}
    for path in owner_only_paths:
        group, _, key = path.partition(".")
        current = updates.get(group, getattr(profile, group, None))
        if isinstance(current, dict) and key in current:
            trimmed = dict(current)
            del trimmed[key]
            updates[group] = trimmed
    return replace(profile, **updates) if updates else profile


class PgProfileStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save(self, profile: UserProfile) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO profiles (profile_id, owner, identity, research, team, "
                "assets, constraints, track_record, locale, sensitivity_overrides, "
                "updated_at) VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, "
                "$6::jsonb, $7::jsonb, $8::jsonb, $9, $10::jsonb, $11) "
                "ON CONFLICT (profile_id) DO UPDATE SET identity = EXCLUDED.identity, "
                "research = EXCLUDED.research, team = EXCLUDED.team, "
                "assets = EXCLUDED.assets, constraints = EXCLUDED.constraints, "
                "track_record = EXCLUDED.track_record, locale = EXCLUDED.locale, "
                "sensitivity_overrides = EXCLUDED.sensitivity_overrides, "
                "updated_at = EXCLUDED.updated_at",
                profile.profile_id,
                json.dumps(
                    {"kind": profile.owner.kind, "id": profile.owner.id},
                    ensure_ascii=False,
                ),
                json.dumps(profile.identity, ensure_ascii=False),
                json.dumps(profile.research, ensure_ascii=False),
                json.dumps(profile.team, ensure_ascii=False),
                json.dumps(profile.assets, ensure_ascii=False),
                json.dumps(profile.constraints, ensure_ascii=False),
                json.dumps(profile.track_record, ensure_ascii=False),
                profile.locale,
                json.dumps(profile.sensitivity_overrides, ensure_ascii=False),
                profile.updated_at,
            )
        finally:
            await conn.close()

    async def load(
        self, profile_id: str, viewer_role: ViewerRole = "owner"
    ) -> UserProfile:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM profiles WHERE profile_id = $1", profile_id
            )
        finally:
            await conn.close()
        if row is None:
            raise KeyError(f"unknown profile: {profile_id}")
        owner = json.loads(row["owner"])
        profile = UserProfile(
            profile_id=row["profile_id"],
            owner=Principal(kind=owner["kind"], id=owner["id"]),
            identity=json.loads(row["identity"]),
            research=json.loads(row["research"]),
            team=json.loads(row["team"]),
            assets=json.loads(row["assets"]),
            constraints=json.loads(row["constraints"]),
            track_record=json.loads(row["track_record"]),
            locale=row["locale"],
            sensitivity_overrides=json.loads(row["sensitivity_overrides"]),
            updated_at=_as_datetime(row["updated_at"]),
        )
        return scoped_view(profile, viewer_role)


def _as_datetime(value: datetime) -> datetime:
    return value
