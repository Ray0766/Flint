"""SCHEMA-14 验收：I13 AnalysisContext.lang/region + PricingRecord 币种存在性。

acceptance（tasks-v04.json#SCHEMA-14）：
  ① lang/region 两字段新增；locale 兼容注记入 v04 docstring；
  ② PricingRecord.currency/region 存在性断言 + price_entries 表列核对；
  ③ 核实新增项 owner_review 标记在**卡与文档双处**。

## 为什么 locale 保留而不是删掉

`AnalysisContext.locale: str` 是既有字段，既有代码在用。删它是**改既有契约**，
不是增量。保留 + 在 docstring 写明「v0.4 起 lang/region 为权威（A3），locale 由 lang 派生填充」，
既不破坏既有调用，又让新代码知道该信谁。

## 为什么这张卡不加币种字段

清单原假设「PriceBook 要加 currency」。真件核实推翻了它——`PricingRecord` **已含**
`currency` 与 `region`。本卡因此只做**存在性断言**：把「已经有了」这件事钉成测试，
以后谁把它删了会当场红。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
TECHPLAN = REPO_ROOT / "docs" / "技术方案-v1.2-delta.md"
CURRENCY_DOC = REPO_ROOT / "docs" / "pricebook_currency_v04.md"
TASKS = REPO_ROOT / "tasks-v04.json"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


def test_analysis_context_gains_lang_and_region() -> None:
    fields = set(M.AnalysisContext.__dataclass_fields__)
    assert {"lang", "region"} <= fields
    assert str(M.AnalysisContext.__dataclass_fields__["lang"].type) == "SystemLanguage"
    assert str(M.AnalysisContext.__dataclass_fields__["region"].type) == "Region"


def test_locale_is_preserved_for_compatibility() -> None:
    """既有字段 NEVER 删——删它是改既有契约，不是增量。"""
    assert "locale" in M.AnalysisContext.__dataclass_fields__


def test_locale_compat_note_is_in_the_v04_docstring() -> None:
    """兼容口径写进 docstring：新代码要知道该信谁。"""
    source = V04.read_text(encoding="utf-8")
    block = source[source.index("class AnalysisContext:"):]
    block = block[:block.index("Audience = ")]
    assert "lang" in block and "权威" in block, "AnalysisContext 处应写明 lang/region 为权威"
    assert "locale" in block


def test_analysis_context_constructs_with_all_three() -> None:
    ctx = M.AnalysisContext(
        project_id="proj-1", budget_cny=100.0, locale="zh-CN", lang="zh", region="CN")
    assert (ctx.lang, ctx.region, ctx.locale) == ("zh", "CN", "zh-CN")


def test_pricing_record_already_carries_currency_and_region() -> None:
    """真件核实推翻清单预估：本轮不加字段，只把「已经有了」钉成测试。"""
    fields = set(M.PricingRecord.__dataclass_fields__)
    assert {"currency", "region"} <= fields, "PricingRecord 应已含币种与地区"
    assert str(M.PricingRecord.__dataclass_fields__["currency"].type) == "str"


def test_price_entries_column_is_reconciled_with_e2() -> None:
    """表列核对：字段层已有、表列层补齐，两层对齐后不再有第三处口径。"""
    techplan = TECHPLAN.read_text(encoding="utf-8")
    e2 = techplan[techplan.index("## E2"):techplan.index("## E3")]
    assert "price_entries" in e2 and "currency" in e2, "E2 应登记 price_entries 加 currency 列"
    assert "CNY" in e2, "E2 应写明默认值"
    currency_doc = CURRENCY_DOC.read_text(encoding="utf-8")
    assert "price_entries" in currency_doc and "E2" in currency_doc, (
        "MIGRATE-07 的登记文档应与 E2 同源，避免出现第三处口径")


def test_owner_review_is_marked_on_both_card_and_doc() -> None:
    """acceptance ③：核实新增项的 owner_review 标记在卡与文档双处。"""
    card = next(t for t in json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
                if t["id"] == "SCHEMA-14")
    assert card["owner_review"] is True, "卡上 owner_review 应为 true"
    workorder = (REPO_ROOT / "WORKORDER-v04.md").read_text(encoding="utf-8")
    i13 = workorder[workorder.index("### I13"):]
    i13 = i13[:i13.index("### ", 5)] if "### " in i13[5:] else i13
    assert "owner_review" in i13, "工单 §4-I13 应带 owner_review 标记"
