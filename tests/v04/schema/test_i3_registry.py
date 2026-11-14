"""SCHEMA-03 验收：I3 SourceRegistry + SourceEntry（空表种子）。

acceptance（tasks-v04.json#SCHEMA-03）：
  ① `select(region)` 空表返回空集不抛错（K1 留空绕行）；
  ② NEVER 内置任何真实站点清单（种子文件为空表断言）。

## 为什么「空表不抛错」是一条正经断言

九区源清单是未决项 **K1**（owner 定各国源与合规结论）。在它落地前，注册表**必须是空的**——
但空不能等于坏：`select("JP")` 该返回空集，而不是抛异常、也不是回落到别的区。
「没有源」与「取源失败」是两件事，混起来会让上层把「该区今天没数据」误报成故障。

## 为什么要扫真实站点清单

K1 未决时最容易的失守方式，是「先随手写几个大站顶着」。那是**编造**：
各国源的合规结论（`FetchLegalStatus`）没有 owner 结论前，任何具体站点都是猜的。
本测试因此扫 `contracts_v04/models_v04.py` 的源码，断言里面没有 URL/域名字面量。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()
TEN_REGIONS = ("CN", "HK", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR")


def _empty_registry() -> object:
    return M.SourceRegistry(entries=[], updated_at=NOW)


def test_source_entry_carries_region_tier_and_legal_status() -> None:
    fields = set(M.SourceEntry.__dataclass_fields__)
    for required in ("source_id", "region", "country", "name_native", "homepage",
                     "authority_tier", "fetch_legal_status", "enabled"):
        assert required in fields, f"SourceEntry 缺字段：{required}"


def test_select_on_empty_registry_returns_empty_for_every_region() -> None:
    """空表 → 每个区都返回空集，且**不抛错**（K1 留空绕行）。"""
    registry = _empty_registry()
    for region in TEN_REGIONS:
        got = registry.select(region)
        assert got == [], f"{region} 在空表上应得空集，实得 {got}"


def test_select_never_falls_back_to_another_region() -> None:
    """有源时只返回本区的——NEVER 因为本区空就拿别区顶上。"""
    us = M.SourceEntry(
        source_id="s-us", region="US", country="US", name_native="Example Wire",
        homepage="",                 # K1 未决: 占位空串, NEVER 写真实站点
        authority_tier="unknown", fetch_legal_status="unknown", enabled=True)
    registry = M.SourceRegistry(entries=[us], updated_at=NOW)
    assert registry.select("US") == [us]
    assert registry.select("JP") == [], "JP 无源时 NEVER 回落到 US 的源"


def test_select_excludes_disabled_entries() -> None:
    off = M.SourceEntry(
        source_id="s-off", region="JP", country="JP", name_native="停用源",
        homepage="",
        authority_tier="unknown", fetch_legal_status="unknown", enabled=False)
    registry = M.SourceRegistry(entries=[off], updated_at=NOW)
    assert registry.select("JP") == [], "enabled=False 的源 NEVER 进选集"


def test_no_real_site_list_is_baked_in() -> None:
    """K1 未决 → 契约里 NEVER 出现任何真实站点（URL / 域名字面量）。"""
    source = V04.read_text(encoding="utf-8")
    # 只扫**字符串字面量**里的 URL 与域名；注释与 docstring 里的说明不算清单
    urls = re.findall(r'["\'](https?://[^"\']+)["\']', source)
    domains = re.findall(r'["\']([a-z0-9-]+\.(?:com|org|net|cn|jp|kr|co\.uk|io|gov))["\']', source)
    assert not urls, f"契约里内置了 URL：{urls}（K1 未决，NEVER 先随手写几个大站顶着）"
    assert not domains, f"契约里内置了域名：{domains}"


def test_empty_seed_is_the_declared_baseline() -> None:
    """空表种子本身可构造、可断言为空——「空」是明确状态，不是「还没写」。"""
    registry = _empty_registry()
    assert registry.entries == []
    assert registry.updated_at == NOW
