"""SourceRegistry：配置驱动的热点源注册与启停（M1-010，技术方案 E1/E8）。

- 每源以 source_id 注册一个工厂；启停走 feature flag `source_{id}_enabled`
  （E8 命名），未显式配置默认启用——`FROZEN_SOURCE_IDS` 里的源除外，它们默认关
  （`DEC-066` 冻结，`NARROW-05`）。
- 未注册的 kind 抛 UnknownSourceError（显式错误，不静默返回空）。
- 单源故障降级（kill 一源其余照常）是 M1-015 的范围；本模块只负责
  注册表与配置开关。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from flint.config import FeatureFlags
from flint.domain.protocols import TrendSource

SourceFactory = Callable[[], TrendSource]


class UnknownSourceError(Exception):
    """Raised when a source_id was never registered."""


#: `DEC-066` froze the Weibo and Google Trends sources: no more investment, way in closed.
#: They stay registered and their adapters stay in the tree; only the default flips, so a
#: frozen source runs only when its flag is set on explicitly. Unfreezing takes a new owner
#: ruling (`CLAUDE.md` S1), which empties this set.
FROZEN_SOURCE_IDS: frozenset[str] = frozenset({"weibo", "gtrends"})


def source_flag_name(source_id: str) -> str:
    """E8 flag naming: source_{id}_enabled."""
    return f"source_{source_id}_enabled"


@dataclass
class SourceRegistry:
    flags: FeatureFlags
    _factories: dict[str, SourceFactory] = field(default_factory=dict)

    def register(self, source_id: str, factory: SourceFactory) -> None:
        if source_id in self._factories:
            raise ValueError(f"source already registered: {source_id}")
        self._factories[source_id] = factory

    def _require_registered(self, source_id: str) -> None:
        if source_id not in self._factories:
            raise UnknownSourceError(
                f"unknown source kind: {source_id}; registered: "
                + ", ".join(sorted(self._factories))
            )

    def is_enabled(self, source_id: str) -> bool:
        self._require_registered(source_id)
        return self.flags.is_enabled(
            source_flag_name(source_id), default=source_id not in FROZEN_SOURCE_IDS)

    def source_ids(self) -> list[str]:
        return sorted(self._factories)

    def enabled_source_ids(self) -> list[str]:
        return sorted(sid for sid in self._factories if self.is_enabled(sid))

    def create(self, source_id: str) -> TrendSource:
        self._require_registered(source_id)
        return self._factories[source_id]()
