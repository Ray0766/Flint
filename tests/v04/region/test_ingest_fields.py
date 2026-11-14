"""REGION-02（前半）验收：采集入库溯源四字段必填 + 缺省注入。

acceptance（tasks-v04.json#REGION-02）：四溯源字段缺省注入。

## 缺省注入不是「随便填一个」

`authority_tier` / `fetch_legal_status` 缺省为 `unknown`——**如实标注不知道**，
而不是给一个中等值蒙混。两个 unknown 各自有下游后果：
unknown 权威度 NEVER 满足判 A/B（REGION-03 门），unknown 合规 NEVER 放行抓取（REGION-07 门）。
所以「缺省」在这里等于「进不了那两道门」，不是「先当作可以」。

`region` / `source_country` **没有缺省**：归区是采集期的事实。
注入器在源注册表里查不到该源时 MUST 报错，NEVER 猜一个区——
猜错的归属会污染该区热点集合（`PRINCIPLES#B5`），而且错得无声无息。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _models() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 2, tzinfo=UTC)

from flint.region.ingest_fields import (
    UnknownSourceRegion,
    provenance_defaults,
    with_provenance,
)


def _entry(source_id: str, region: str, country: str, tier: str = "official",
           legal: str = "allowed") -> object:
    return M.SourceEntry(
        source_id=source_id, region=region, country=country,
        name_native=f"{source_id}-原名", homepage="",
        authority_tier=tier, fetch_legal_status=legal, enabled=True)


def _registry(entries: list[object]) -> object:
    return M.SourceRegistry(entries=entries, updated_at=NOW)


def _raw_doc() -> dict[str, object]:
    return {
        "doc_id": "doc-1", "source_id": "s-jp", "kind": "paper", "title": "全固体電池",
        "url": "https://example.invalid/a", "published_at": date(2026, 8, 1),
        "meta": {}, "origin": "vendor", "access": "public",
    }


def test_four_fields_are_injected_from_the_registry() -> None:
    registry = _registry([_entry("s-jp", "JP", "JP", tier="mainstream", legal="allowed")])
    doc = with_provenance(_raw_doc(), registry=registry, model=M.Doc)
    assert doc.region == "JP"
    assert doc.source_country == "JP"
    assert doc.authority_tier == "mainstream"
    assert doc.fetch_legal_status == "allowed"


def test_unknown_tier_and_legal_default_to_unknown() -> None:
    """源没给权威度/合规态时如实标 unknown —— 不是「先当作可以」。"""
    registry = _registry([_entry("s-x", "US", "US", tier="unknown", legal="unknown")])
    doc = with_provenance(_raw_doc() | {"source_id": "s-x"}, registry=registry, model=M.Doc)
    assert doc.authority_tier == "unknown"
    assert doc.fetch_legal_status == "unknown"


def test_defaults_helper_states_the_two_unknowns() -> None:
    d = provenance_defaults()
    assert d["authority_tier"] == "unknown"
    assert d["fetch_legal_status"] == "unknown"
    assert "region" not in d and "source_country" not in d, (
        "region/source_country NEVER 有缺省：归区是采集期的事实，猜一个会无声地污染该区热点集合")


def test_unregistered_source_raises_instead_of_guessing_a_region() -> None:
    registry = _registry([_entry("s-jp", "JP", "JP")])
    with pytest.raises(UnknownSourceRegion, match="s-unknown"):
        with_provenance(_raw_doc() | {"source_id": "s-unknown"}, registry=registry, model=M.Doc)


def test_existing_doc_fields_are_untouched() -> None:
    """注入只补四个溯源字段，既有字段一个不改。"""
    raw = _raw_doc()
    registry = _registry([_entry("s-jp", "JP", "JP")])
    doc = with_provenance(raw, registry=registry, model=M.Doc)
    for key in ("doc_id", "source_id", "kind", "title", "url", "published_at", "origin", "access"):
        assert getattr(doc, key) == raw[key], f"{key} 被改动了"


def test_injection_never_overwrites_explicit_values() -> None:
    """采集侧已经明确给了值时，注入器 NEVER 用注册表覆盖它。"""
    registry = _registry([_entry("s-jp", "JP", "JP", tier="mainstream")])
    doc = with_provenance(
        _raw_doc() | {"authority_tier": "official"}, registry=registry, model=M.Doc)
    assert doc.authority_tier == "official", "显式值优先——覆盖它等于让注册表悄悄改写采集事实"
