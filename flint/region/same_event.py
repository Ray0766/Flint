"""REGION-05：same_event_group 的显式建立与解除。

## 跨区关联的唯一合法通道

`PRINCIPLES#B5`：聚类先按 region 分桶（REGION-04），跨区**永不自动合并**；
两国对同一事件的报道要关联起来, 只能由**用户或系统操作**显式建组。

本模块的导出面上因此**没有**任何「按相似度自动建组」的入口。
留一个 `auto_group(threshold=…)` 而默认不调用是不够的——留一条路就等于允许它被走,
而 B5 要防的正是 embedding 把两国报道合成一簇。
源码里也 NEVER 出现 embedding / cosine / centroid 这类符号（测试有断言）。

## 显式 = 有主体、可追溯

每个组记 `established_by` 与 `established_at`。没有主体的组就是「系统自动建的」,
那正是要禁的东西；空 actor 直接拒绝。

## 幂等

建组与解组都幂等: 端点重放（网络重试、用户连点）NEVER 产出第二个组、
NEVER 因为「已经解过了」而抛错。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

_MIN_CLUSTERS = 2


@dataclass(frozen=True)
class SameEventGroup:
    """一组「被显式认定为同一事件」的簇。跨区与否本模块不关心——它只记录人的判断。"""

    group_id: str
    cluster_ids: tuple[str, ...]
    established_by: str
    established_at: datetime


@dataclass
class SameEventStore:
    """内存实现；SQL 实现随 E2 的 `same_event_groups` 表接入（本卡不接库）。"""

    _groups: dict[str, SameEventGroup] = field(default_factory=dict)

    def get(self, group_id: str) -> SameEventGroup | None:
        return self._groups.get(group_id)

    def put(self, group: SameEventGroup) -> None:
        self._groups[group.group_id] = group

    def drop(self, group_id: str) -> bool:
        return self._groups.pop(group_id, None) is not None

    def all(self) -> list[SameEventGroup]:
        return list(self._groups.values())


def establish_group(
    store: SameEventStore,
    *,
    group_id: str,
    cluster_ids: list[str],
    actor: str,
    now: datetime,
) -> SameEventGroup:
    """显式建组（POST /clusters/same-event-group）。幂等: 同 id 同内容重放返回同一个组。

    入参只有**显式给定的簇 id** 与操作主体——没有任何「按什么自动找」的参数。
    """
    if not actor.strip():
        raise ValueError(
            "same_event_group 必须记录 actor: 没有主体的组就是「系统自动建的」, "
            "而自动建组正是 B5 要禁的")
    if len(cluster_ids) < _MIN_CLUSTERS:
        raise ValueError(
            f"cluster_ids 至少 {_MIN_CLUSTERS} 个: 一个簇自己不构成「同一事件」的关联")

    existing = store.get(group_id)
    ids = tuple(cluster_ids)
    if existing is not None and existing.cluster_ids == ids:
        return existing                                  # 幂等重放

    group = SameEventGroup(
        group_id=group_id, cluster_ids=ids,
        established_by=actor, established_at=now)
    store.put(group)
    return group


def dissolve_group(store: SameEventStore, *, group_id: str) -> bool:
    """显式解组（DELETE /clusters/same-event-group）。幂等: 不存在时返回 False, NEVER 抛错。"""
    return store.drop(group_id)
