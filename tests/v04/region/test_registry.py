"""REGION-01 验收：SourceRegistry 实现 + 准入标准 + 空表降级。

acceptance（tasks-v04.json#REGION-01）：
  ① 空表 select 走 E6 缺数据行（DegradationNote 落盘）；
  ② 他国强证据保留在选集（不隔离断言）；真实源清单 NEVER 内置（K1）。

## 两个 select 不是一回事

- **采集选集**（`sources_for_ingest`）按 region 取：热点集合本来就是分区的，
  跨区合并会造出哪国都不存在的假热点（`PRINCIPLES#B5`）。
- **检索选集**（`sources_for_retrieval`）**NEVER 按国别排除**：
  排序 MAY 以 region_match 加权，过滤器 NEVER 剔他国源（`PRINCIPLES#B4`）。
  把这两件事写成同一个函数，就等于让「本国优先」悄悄变成「本国隔离」。

## 名字撞车（已登记）

`flint.sources.registry.SourceRegistry` 是 M1-010 的**热点源工厂注册表**（带 feature flag 启停），
与 v04 契约里 I3 的 `SourceRegistry`（**分区源选集表**）**同名不同物**。
两个名字各由自己的规格钉死，改哪个都越界；本测试因此断言二者互不引用。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, date, datetime
from pathlib import Path

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
DAY = date(2026, 8, 2)

from flint.region.registry import (
    RegionSourceService,
    load_seed_registry,
)
from flint.sources.degradation import DegradationNote


class _MemoryStore:
    def __init__(self) -> None:
        self.notes: list[DegradationNote] = []

    def add(self, note: DegradationNote) -> None:
        self.notes.append(note)

    def for_day(self, day: date) -> list[DegradationNote]:
        return [n for n in self.notes if n.day == day]


def _entry(source_id: str, region: str, country: str, tier: str = "official",
           enabled: bool = True) -> object:
    return M.SourceEntry(
        source_id=source_id, region=region, country=country,
        name_native=f"{source_id}-原名", homepage="",
        authority_tier=tier, fetch_legal_status="allowed", enabled=enabled)


def _service(entries: list[object]) -> tuple[object, _MemoryStore]:
    store = _MemoryStore()
    registry = M.SourceRegistry(entries=entries, updated_at=NOW)
    return RegionSourceService(registry=registry, store=store), store


# ── ① 空表 → E6 缺数据行 ──────────────────────────────────────────────

def test_empty_registry_emits_degradation_note() -> None:
    service, store = _service([])
    got = service.sources_for_ingest("JP", day=DAY)
    assert got == [], "空表返回空集"
    assert len(store.notes) == 1, "空表 MUST 落一条 DegradationNote（E6 缺数据行）"
    note = store.notes[0]
    assert note.reason == "no_region_sources"
    assert note.day == DAY
    assert "JP" in note.detail, f"降级说明要写清是哪个区：{note.detail}"


def test_non_empty_registry_emits_no_note() -> None:
    """阴性对照：有源时不落降级——否则「降级」这个信号会被噪音淹没。"""
    service, store = _service([_entry("s-jp", "JP", "JP")])
    assert len(service.sources_for_ingest("JP", day=DAY)) == 1
    assert store.notes == []


def test_degradation_is_per_region_not_global() -> None:
    """一个区没源，其余区照常（E6 部分成功语义）。"""
    service, store = _service([_entry("s-us", "US", "US")])
    assert service.sources_for_ingest("US", day=DAY)
    assert service.sources_for_ingest("JP", day=DAY) == []
    assert [n.source_id for n in store.notes] == ["region:JP"]


# ── ② 他国源不被隔离 ──────────────────────────────────────────────────

def test_retrieval_keeps_foreign_sources() -> None:
    """PRINCIPLES#B4：过滤器 NEVER 按国别排除他国源。"""
    entries = [_entry("s-cn", "CN", "CN"), _entry("s-us", "US", "US"),
               _entry("s-jp", "JP", "JP")]
    service, _ = _service(entries)
    picked = [r.entry.source_id for r in service.sources_for_retrieval("CN")]
    assert set(picked) == {"s-cn", "s-us", "s-jp"}, f"他国源被剔掉了：{picked}"


def test_retrieval_ranks_home_region_first_without_excluding() -> None:
    """本国优先是**排序**，不是过滤——两者混为一谈就成了隔离。"""
    entries = [_entry("s-us", "US", "US"), _entry("s-cn", "CN", "CN")]
    service, _ = _service(entries)
    ranked = service.sources_for_retrieval("CN")
    assert ranked[0].entry.source_id == "s-cn", "本区源排前"
    assert ranked[0].region_match is True and ranked[-1].region_match is False
    assert ranked[0].weight > ranked[-1].weight, "加权体现在 weight 上"
    assert all(r.weight > 0 for r in ranked), "他国源的权重 NEVER 归零（归零＝变相隔离）"


def test_ingest_selection_stays_region_scoped() -> None:
    """采集选集仍按区取：热点集合本就分区（B5），与检索选集是两件事。"""
    entries = [_entry("s-cn", "CN", "CN"), _entry("s-us", "US", "US")]
    service, _ = _service(entries)
    assert [e.source_id for e in service.sources_for_ingest("CN", day=DAY)] == ["s-cn"]


def test_disabled_sources_are_excluded_from_both_paths() -> None:
    entries = [_entry("s-off", "CN", "CN", enabled=False)]
    service, store = _service(entries)
    assert service.sources_for_ingest("CN", day=DAY) == []
    assert service.sources_for_retrieval("CN") == []
    assert store.notes[0].reason == "no_region_sources", "全停用等同没有源，同样落降级"


# ── ③ K1：真实源清单 NEVER 内置 ────────────────────────────────────────

def test_seed_registry_is_empty() -> None:
    """九区源清单待 K1 —— 种子必须是空表，「空」是明确状态。"""
    seed = load_seed_registry()
    assert seed.entries == [], f"种子表里有 {len(seed.entries)} 条源，K1 未决前 NEVER 内置"


def test_no_real_site_baked_into_implementation() -> None:
    import re

    source = (REPO_ROOT / "flint" / "region" / "registry.py").read_text(encoding="utf-8")
    urls = re.findall(r'["\'](https?://[^"\']+)["\']', source)
    domains = re.findall(r'["\']([a-z0-9-]+\.(?:com|org|net|cn|jp|kr|io|gov))["\']', source)
    assert not urls and not domains, f"实现里内置了站点：{urls or domains}"


def test_admission_doc_states_the_undecided_items() -> None:
    doc = (REPO_ROOT / "docs" / "source_admission_v04.md").read_text(encoding="utf-8")
    assert "K1" in doc and "K2" in doc, "准入文档 MUST 指明 K1（源清单）与 K2（合规结论）未决"
    for required in ("authority_tier", "fetch_legal_status", "region", "name_native"):
        assert required in doc, f"准入标准缺字段口径：{required}"


# ── 名字撞车（登记项） ────────────────────────────────────────────────

def test_v04_registry_does_not_shadow_the_m1_source_registry() -> None:
    """两个 SourceRegistry 同名不同物：本实现 NEVER 引用 M1-010 那个。"""
    source = (REPO_ROOT / "flint" / "region" / "registry.py").read_text(encoding="utf-8")
    assert "from flint.sources.registry import" not in source, (
        "flint/region/registry.py 不该引用 M1-010 的工厂注册表——两者同名不同物")
    from flint.sources.registry import SourceRegistry as M1Registry
    assert M1Registry is not M.SourceRegistry
