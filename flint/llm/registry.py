"""提供商注册表骨架（V2-002 多提供商选择器地基）。

**纯机制**：provider_id → 零参工厂 的映射 + tier（free/paid）分组查询。
- **空默认**：`ProviderRegistry()` 不含任何条目——**NEVER 内置任何具体 provider、
  tier→provider 映射、或 key/base_url/价目**。tier→provider 的映射与「谁付 key」
  属 owner **决策③**（docs/前端-owner决策备忘.md），本类只提供承载它的机制。
- 具体配置（base_url/model/api_key/pricing）由上游注入进工厂闭包；本表不触碰
  key，NEVER 读/存/记 key。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from flint.domain.protocols import LLMProvider

ProviderTier = Literal["free", "paid"]


class ProviderNotRegistered(KeyError):
    """请求了未注册的 provider_id。"""


class ProviderAlreadyRegistered(ValueError):
    """重复注册同一 provider_id——NEVER 静默覆盖既有条目。"""


@dataclass(frozen=True)
class ProviderEntry:
    provider_id: str
    tier: ProviderTier
    factory: Callable[[], LLMProvider]  # 零参工厂：配置/key 在闭包里由上游注入


class ProviderRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, ProviderEntry] = {}

    def register(self, entry: ProviderEntry) -> None:
        if entry.provider_id in self._entries:
            raise ProviderAlreadyRegistered(entry.provider_id)
        self._entries[entry.provider_id] = entry

    def get(self, provider_id: str) -> LLMProvider:
        return self._entry(provider_id).factory()

    def tier_of(self, provider_id: str) -> ProviderTier:
        return self._entry(provider_id).tier

    def available(self) -> list[str]:
        return sorted(self._entries)

    def available_for_tier(self, tier: ProviderTier) -> list[str]:
        return sorted(
            pid for pid, entry in self._entries.items() if entry.tier == tier
        )

    def _entry(self, provider_id: str) -> ProviderEntry:
        try:
            return self._entries[provider_id]
        except KeyError as err:
            raise ProviderNotRegistered(provider_id) from err
