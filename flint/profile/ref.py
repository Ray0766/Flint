"""ProfileRef 通道（M3-015，v0.3.2 §1 涉我类型化出处 / 审8）。

- resolve_profile_field：两级路径 + [index] 口径（"research.publications[2]"）。
- make_ref_or_gap 三分支：可解析 → ProfileRef；因敏感度被过滤（team 视角
  拿不到、owner 视角拿得到）→ GapHint(missing_permission, required_scope=
  路径, suggested_sources 空——绝不伪装成缺资料)；本就不存在 →
  GapHint(missing_data, ask_user 补录引导)。
- find_naked_profile_values：涉我章节的裸值检测——TextSpan 全文与 profile
  任一字符串叶值精确相等即违规（确定性规则；ProfileRef 通道内引用合法）。
"""
from __future__ import annotations

import re
from typing import Any

from flint.domain.models import (
    DEFAULT_PROFILE_SENSITIVITY,
    GapHint,
    InlineSpan,
    ProfileRef,
    UserProfile,
)
from flint.profile.store import ViewerRole

_INDEX_RE = re.compile(r"^(?P<key>[^\[\]]+)(?:\[(?P<index>\d+)\])?$")


def _walk(value: Any, part: str) -> Any:
    match = _INDEX_RE.match(part)
    if match is None:
        return None
    key, index = match.group("key"), match.group("index")
    if isinstance(value, dict):
        value = value.get(key)
    else:
        value = getattr(value, key, None)
    if index is not None:
        if isinstance(value, list) and int(index) < len(value):
            return value[int(index)]
        return None
    return value


def resolve_profile_field(profile: UserProfile, field_path: str) -> Any:
    value: Any = profile
    for part in field_path.split("."):
        value = _walk(value, part)
        if value is None:
            return None
    return value


def _owner_only(profile: UserProfile, field_path: str) -> bool:
    effective = dict(DEFAULT_PROFILE_SENSITIVITY)
    effective.update(profile.sensitivity_overrides)
    return effective.get(field_path) == "owner_only"


def make_ref_or_gap(
    profile: UserProfile, field_path: str, viewer_role: ViewerRole
) -> ProfileRef | GapHint:
    value = resolve_profile_field(profile, field_path)
    if value is not None:
        return ProfileRef(kind="profile", field_path=field_path)
    if viewer_role != "owner" and _owner_only(profile, field_path):
        return GapHint(
            missing_what=f"涉我字段组不可访问：{field_path}",
            cause="missing_permission",
            suggested_sources=[],
            action="request_permission",
            required_scope=field_path,
        )
    return GapHint(
        missing_what=f"Profile 字段缺失：{field_path}",
        cause="missing_data",
        suggested_sources=["Profile 补录"],
        action="ask_user",
    )


def _string_leaves(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [leaf for v in value.values() for leaf in _string_leaves(v)]
    if isinstance(value, list):
        return [leaf for v in value for leaf in _string_leaves(v)]
    return []


def find_naked_profile_values(
    spans: list[InlineSpan], profile: UserProfile
) -> list[str]:
    leaves = {
        leaf
        for group in (
            profile.identity, profile.research, profile.team,
            profile.assets, profile.constraints, profile.track_record,
        )
        for leaf in _string_leaves(group)
    }
    violations: list[str] = []
    for span in spans:
        if span.kind == "text" and span.text.strip() in leaves:
            violations.append(
                f"naked profile value {span.text.strip()!r} must go through "
                "ProfileRef"
            )
    return violations
