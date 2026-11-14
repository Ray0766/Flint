"""血缘④ 休眠与复活（M1-026，PDD v0.2 §3.2 步骤 4）。

- active 且连续 dormant_after_days 天无热度（last_active 距今）→ dormant；
  **永不物理删除**——本模块只产出状态变更清单，不做任何删除。
- dormant 簇被当日匹配命中（s1）→ 复活：标 reactivated，cluster_id 原样复用。
- dormant_after_days 配置化（PDD 初值 14 天）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RevivalEvent:
    cluster_id: str
    reactivated: bool


def apply_dormancy(
    states: dict[str, tuple[str, date]],
    today: date,
    dormant_after_days: int,
) -> list[str]:
    """states: cluster_id -> (status, last_active). Returns IDs to mark dormant."""
    result = [
        cluster_id
        for cluster_id, (status, last_active) in states.items()
        if status == "active" and (today - last_active).days >= dormant_after_days
    ]
    return sorted(result)


def detect_revivals(
    matched_cluster_ids: list[str], statuses: dict[str, str]
) -> list[RevivalEvent]:
    """A dormant cluster hit by today's continuation matching reactivates in
    place — same cluster_id, no new identity."""
    return [
        RevivalEvent(cluster_id=cid, reactivated=True)
        for cid in matched_cluster_ids
        if statuses.get(cid) == "dormant"
    ]
