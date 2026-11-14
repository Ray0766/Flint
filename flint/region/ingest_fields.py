"""REGION-02（前半）：采集入库的溯源四字段注入。

## 缺省注入不是「随便填一个」

`authority_tier` / `fetch_legal_status` 缺省为 `unknown` —— **如实标注不知道**，
不是给一个中等值蒙混。两个 unknown 各自有下游后果:
unknown 权威度 NEVER 满足判 A/B 的必要条件 (REGION-03 门)、
unknown 合规态 NEVER 放行抓取 (REGION-07 门)。
所以「缺省」在这里等于「进不了那两道门」, 而不是「先当作可以」。

`region` / `source_country` **没有缺省**: 归区是采集期的事实。注册表里查不到该源时
抛 UnknownSourceRegion, NEVER 猜一个区——猜错的归属会污染该区热点集合
[PRINCIPLES#B5], 而且错得无声无息。
"""
from __future__ import annotations

from typing import Any

# 只有这两项有缺省, 且缺省值都是 unknown（如实标注「不知道」）。
_DEFAULTS: dict[str, str] = {
    "authority_tier": "unknown",
    "fetch_legal_status": "unknown",
}


class UnknownSourceRegion(Exception):
    """源不在注册表里, 无从确定 region —— NEVER 猜。"""


def provenance_defaults() -> dict[str, str]:
    """溯源字段的缺省值（副本, 调用方改它不影响本模块）。"""
    return dict(_DEFAULTS)


def with_provenance(raw: dict[str, Any], *, registry: Any, model: Any) -> Any:
    """给一条采集结果补齐溯源四字段, 再构造 Doc。

    - `region` / `source_country` 取自源注册表；查不到即抛错。
    - `authority_tier` / `fetch_legal_status` 取注册表值, 注册表没有则 unknown。
    - **显式值优先**: raw 里已经给了的字段 NEVER 被注册表覆盖——
      覆盖它等于让注册表悄悄改写采集期的事实。
    - 既有字段一个不改。
    """
    source_id = raw.get("source_id")
    entry = next((e for e in registry.entries if e.source_id == source_id), None)
    if entry is None:
        raise UnknownSourceRegion(
            f"源 {source_id!r} 不在源注册表里, 无从确定 region: "
            "NEVER 猜一个区——猜错的归属会无声地污染该区热点集合 [PRINCIPLES#B5]")

    filled: dict[str, Any] = dict(raw)
    filled.setdefault("region", entry.region)
    filled.setdefault("source_country", entry.country)
    filled.setdefault("authority_tier", entry.authority_tier or _DEFAULTS["authority_tier"])
    filled.setdefault(
        "fetch_legal_status", entry.fetch_legal_status or _DEFAULTS["fetch_legal_status"])
    return model(**filled)
