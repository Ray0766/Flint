# SCHEMA-14 trace — I13 AnalysisContext + PricingRecord 币种核实 @2026-08-02

**owner_review: true**（核实新增项 · 事后补审，DEC-000 下不停机）

## 1 装载
SCHEMA-14 卡 + `WORKORDER#4-I13` + `docs/pricebook_currency_v04.md`（MIGRATE-07 产出）
+ `docs/技术方案-v1.2-delta.md#E2`。~1,500 字符 ≈ 1.5k tokens（3.8%）。

## 2 首跑即绿（同 SCHEMA-01 的处境，如实记）
本卡的两个字段在 SCHEMA-00 建副本时已预落，两份文档也在 MIGRATE-02/07 写好，
所以测试**首跑即绿**、红态无从制造——**test-first 顺序在此卡同样是破坏了的**。

补救（等价强度的反空转证据）：抽掉 `AnalysisContext.lang` 与 `PricingRecord.currency` 后复跑 →
**3 failed**；还原后全 schema 套 95 passed、additive exit 0。

## 3 两条判断
**① locale 保留而不是删**：`AnalysisContext.locale: str` 是既有字段、既有代码在用。
删它是**改既有契约**，不是增量。保留 + docstring 写明「v0.4 起 lang/region 为权威（A3），
locale 由 lang 派生填充」——既不破坏既有调用，又让新代码知道该信谁。

**② 本卡不加币种字段**：清单原假设「PriceBook 要加 currency」，真件核实**推翻**了它
（`PricingRecord` 已含 `currency`/`region`）。本卡只做**存在性断言**——把「已经有了」钉成测试，
以后谁删了会当场红。

## 4 acceptance 映射
| acceptance | 测试 |
|---|---|
| lang/region 两字段新增 | `test_analysis_context_gains_lang_and_region`（含类型标注核对）+ `..._constructs_with_all_three` |
| locale 兼容注记入 v04 docstring | `test_locale_is_preserved_for_compatibility` + `test_locale_compat_note_is_in_the_v04_docstring` |
| PricingRecord.currency/region 存在性 | `test_pricing_record_already_carries_currency_and_region` |
| price_entries 表列核对 | `test_price_entries_column_is_reconciled_with_e2`：从 `技术方案-v1.2-delta.md#E2` 里读 `price_entries` + `currency` + 默认 `CNY`，并断言 MIGRATE-07 的登记文档与 E2 同源——**避免出现第三处口径** |
| owner_review 标记在卡与文档双处 | `test_owner_review_is_marked_on_both_card_and_doc`：`tasks-v04.json#SCHEMA-14.owner_review == true` **且** 工单 §4-I13 带标记 |

## 5 产出
`tests/v04/schema/test_i14_ctx_currency.py`（7 条）。`contracts_v04/` 本卡未改（预落已符合）。
