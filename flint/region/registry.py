"""REGION-01：分区源选集服务 + 空表降级（E6 缺数据行）。

## 两个 select 不是一回事

- `sources_for_ingest(region)` —— **采集**选集，按区取。热点集合本来就是分区的，
  跨区合并会造出哪国都不存在的假热点 [PRINCIPLES#B5]。
- `sources_for_retrieval(region)` —— **检索**选集，**NEVER 按国别排除**。
  排序 MAY 以 region_match 加权，过滤器 NEVER 剔他国源 [PRINCIPLES#B4]。

把这两件事写成同一个函数，就等于让「本国优先」悄悄变成「本国隔离」——
跨国立场分歧会在检索阶段就被过滤掉，后面 by_source 分列再怎么做也拿不回来。

## 名字撞车（登记项）

`flint.sources.registry.SourceRegistry` 是 M1-010 的**热点源工厂注册表**
（按 source_id 注册工厂 + feature flag 启停），与本模块使用的 v04 契约类型
`SourceRegistry`（I3 **分区源选集表**）**同名不同物**。两个名字各由自己的规格钉死，
改哪个都越界。本模块因此 NEVER 引用 M1-010 那个（测试有断言守着）。

## K1

九区源清单与各国合规结论待 owner（K1/K2）。种子表**是空的**，且实现里
NEVER 内置任何真实站点——空不等于坏：空表返回空集并落一条 E6 缺数据行。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from flint.sources.degradation import DegradationNote

# 本区源的排序加权。他国源的权重 NEVER 归零——归零等于变相隔离。
HOME_REGION_WEIGHT = 1.5
FOREIGN_REGION_WEIGHT = 1.0


class _Store(Protocol):
    def add(self, note: DegradationNote) -> None: ...


@dataclass(frozen=True)
class RankedSource:
    """检索选集的一项：源 + 是否本区 + 排序权重。"""

    entry: Any                       # contracts_v04.SourceEntry
    region_match: bool
    weight: float


def load_seed_registry() -> Any:
    """九区源注册表的**空表种子**（K1 未决）。

    返回一个条目为空的 SourceRegistry。这不是「还没写」，是**明确的空**：
    各国源的合规结论（FetchLegalStatus）没有 owner 结论前，任何具体站点都是猜的。
    """
    from contracts_v04.models_v04 import SourceRegistry

    return SourceRegistry(entries=[], updated_at=datetime.now(UTC))


@dataclass
class RegionSourceService:
    """分区源选集服务。"""

    registry: Any                    # contracts_v04.SourceRegistry
    store: _Store

    def sources_for_ingest(self, region: str, *, day: date) -> list[Any]:
        """该区**启用中**的源；空则落 E6 缺数据行。

        降级是**按区**的：一个区没源，其余区照常（E6 部分成功语义）。
        """
        picked: list[Any] = list(self.registry.select(region))
        if not picked:
            self.store.add(DegradationNote(
                day=day,
                source_id=f"region:{region}",
                reason="no_region_sources",
                detail=f"地区 {region} 无可用源（K1 未决或全部停用）：当日该区无数据，其余区照常",
            ))
        return picked

    def sources_for_retrieval(self, region: str) -> list[RankedSource]:
        """全部启用中的源，本区**加权**排前——NEVER 按国别排除 [PRINCIPLES#B4]。"""
        ranked = [
            RankedSource(
                entry=e,
                region_match=e.region == region,
                weight=HOME_REGION_WEIGHT if e.region == region else FOREIGN_REGION_WEIGHT,
            )
            for e in self.registry.entries
            if e.enabled
        ]
        ranked.sort(key=lambda r: (-r.weight, r.entry.source_id))
        return ranked
