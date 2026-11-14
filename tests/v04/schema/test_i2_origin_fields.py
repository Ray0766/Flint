"""SCHEMA-02 验收：I2 溯源四字段落 `Doc`（落点由预填表核实修正）。

acceptance（tasks-v04.json#SCHEMA-02）：
  ① region/source_country/authority_tier/fetch_legal_status 四字段落 Doc；
  ② 缺省值 unknown 生效；既有字段零改动（additive 校验穿透）。

## 落点为什么是 Doc 而不是 Origin

清单原假设落 `Origin`。真件核实：`Origin` 是**选题入口五类**
（combo / idea / domain / competitor / document，payload 含 `combo{card_ids, hypothesis}`），
与文档溯源无关；文档溯源的载体是 `Doc`。见 `docs/schema_reconcile_prefill_v04.md#I2`。
本测试因此**同时断言 Origin 没有被误加这四个字段**——落点错了要能被发现。

## 「缺省值 unknown 生效」为什么必须是 dataclass 默认值

`authority_tier` 与 `fetch_legal_status` 的缺省态是产品语义的一部分：
未知权威度的证据 NEVER 满足判 A/B（REGION-03 前置门）、未知合规状态 NEVER 当作可抓。
把「缺省 unknown」写在文档里而不写进 dataclass，等于把这条语义交给每个构造点各自记得——
那就是它迟早失效的方式。
"""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
FOUR_FIELDS = ("region", "source_country", "authority_tier", "fetch_legal_status")


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


def test_four_fields_land_on_doc() -> None:
    fields = set(M.Doc.__dataclass_fields__)
    missing = [f for f in FOUR_FIELDS if f not in fields]
    assert not missing, f"Doc 缺溯源字段：{missing}"


def test_they_did_not_land_on_origin_by_mistake() -> None:
    """落点核实：Origin 是选题入口五类，与文档溯源无关，NEVER 误加这四个字段。"""
    origin_fields = set(M.Origin.__dataclass_fields__)
    wrong = [f for f in FOUR_FIELDS if f in origin_fields]
    assert not wrong, f"这四个字段被误加到 Origin 上：{wrong}（落点应为 Doc，见预填表 I2）"


def test_unknown_defaults_take_effect() -> None:
    """缺省值 unknown 必须是 dataclass 默认值——构造时不给也得是 unknown。"""
    doc = M.Doc(
        doc_id="d1", source_id="s1", kind="paper", title="t", url="u",
        published_at=date(2026, 8, 2), meta={}, origin="vendor", access="public",
        region="JP", source_country="JP",
    )
    assert doc.authority_tier == "unknown", "未指定权威度时 MUST 是 unknown（REGION-03 前置门依赖它）"
    assert doc.fetch_legal_status == "unknown", "未指定合规状态时 MUST 是 unknown（NEVER 默认可抓）"


def test_region_and_country_are_explicit_not_defaulted() -> None:
    """region / source_country 没有默认值：归区是采集期的事实，NEVER 由缺省顶替。"""
    specs = {f.name: f for f in dataclasses.fields(M.Doc)}
    for name in ("region", "source_country"):
        f = specs[name]
        assert f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING, (
            f"Doc.{name} 不该有默认值——给它默认值等于允许「不知道是哪区也能入库」")


def test_trenditem_region_is_preserved_untouched() -> None:
    """预填表：TrendItem.region 既存（采集态），保留不动、类型不收窄。"""
    assert "region" in M.TrendItem.__dataclass_fields__
    ann = M.TrendItem.__dataclass_fields__["region"].type
    assert "str" in str(ann), f"TrendItem.region 类型被收窄了：{ann}"
