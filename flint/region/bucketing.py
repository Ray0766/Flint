"""REGION-04：聚类先按 region 分桶 + 簇血缘的 region 维度。

## 为什么分桶必须在聚类之前，而不是聚完再拆

`PRINCIPLES#B5`：先聚后拆是拆不干净的——一旦 US 与 JP 对同一事件的报道被 embedding
合成一簇，簇心已经是两国报道的平均，再按 region 拆开时每一半的簇心都不是它自己的。
产出的是**哪国都不存在的假热点**。所以分桶是前置步骤，不是后处理。

## 跨区关联的唯一合法通道

`same_event_group` **显式建立**（REGION-05），由用户或系统操作。
本模块的参数面里 NEVER 有 auto_merge / cross_region 之类的开关——
留一个开关，就等于留一条「打开它就自动跨区合并」的路。

## 血缘的 region 维度

簇血缘（parent/merged 关系）**只在同区内成立**：`link_lineage` 拒绝跨区父子。
血缘跨了区，等于从另一头把 B5 绕过去——簇没合并，但血缘把它们连成了一条线，
下游按血缘取「同一事件的历史」时又拿到了两国混合的东西。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

Similarity = Callable[[Any, Any], bool]


class CrossRegionLineageError(Exception):
    """血缘关系跨区 —— NEVER 允许 [PRINCIPLES#B5]。"""


@dataclass(frozen=True)
class ClusterMember:
    """簇成员：来源条目 + 它的 region（region 随成员走，不靠簇去推断）。"""

    item_id: str
    region: str
    item: Any = None


@dataclass
class RegionCluster:
    """一个**区内**的簇。region 是簇的固有属性，成员与它必须一致。"""

    region: str
    members: list[ClusterMember] = field(default_factory=list)
    parent_cluster_ids: list[str] = field(default_factory=list)


def bucket_and_cluster(
    *,
    items: Sequence[Any],
    region_of: Callable[[Any], str],
    are_similar: Similarity,
) -> list[RegionCluster]:
    """先按 region 分桶，再在**每个桶内**聚类。

    参数面里刻意没有任何跨区开关：跨区关联的唯一合法通道是 same_event_group
    （REGION-05 显式建立），NEVER 靠相似度自动合并 [PRINCIPLES#B5]。
    """
    buckets: dict[str, list[Any]] = {}
    for item in items:
        buckets.setdefault(region_of(item), []).append(item)

    clusters: list[RegionCluster] = []
    for region in sorted(buckets):
        for group in _cluster_within(buckets[region], are_similar):
            clusters.append(RegionCluster(
                region=region,
                members=[
                    ClusterMember(
                        item_id=getattr(it, "item_id", str(index)),
                        region=region, item=it)
                    for index, it in enumerate(group)
                ],
            ))
    return clusters


def _cluster_within(group: list[Any], are_similar: Similarity) -> list[list[Any]]:
    """桶内单链聚类：与簇中任一成员相似即归入该簇。"""
    out: list[list[Any]] = []
    for item in group:
        for existing in out:
            if any(are_similar(item, other) for other in existing):
                existing.append(item)
                break
        else:
            out.append([item])
    return out


def link_lineage(child: RegionCluster, parents: Sequence[RegionCluster]) -> RegionCluster:
    """给簇挂血缘。**跨区父子直接拒绝**。

    血缘跨了区，等于从另一头把 B5 绕过去：簇没合并，但血缘把两国的簇连成一条线，
    下游按血缘取「同一事件的历史」时又拿到了两国混合的东西。
    """
    offenders = [p.region for p in parents if p.region != child.region]
    if offenders:
        raise CrossRegionLineageError(
            f"簇血缘跨区: child.region={child.region!r}, parents={offenders}; "
            "跨区关联的唯一合法通道是 same_event_group（REGION-05 显式建立）"
            " [PRINCIPLES#B5]")
    child.parent_cluster_ids = [
        f"{p.region}:{p.members[0].item_id if p.members else 'empty'}" for p in parents
    ]
    return child
