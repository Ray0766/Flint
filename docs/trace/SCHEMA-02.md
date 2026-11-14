# SCHEMA-02 trace — I2 溯源四字段落 Doc @2026-08-02

## 1 装载

SCHEMA-02 卡 + `docs/schema_reconcile_prefill_v04.md#I2` + `models_v04.py` 的 `Doc` 类体。
~1,800 字符 ≈ 1.8k tokens，占 4.5%。

## 2 test-first（本卡有**真红**）

先写 `tests/v04/schema/test_i2_origin_fields.py` → 跑 → **红**：

```
TypeError: Doc.__init__() missing 2 required positional arguments:
           'authority_tier' and 'fetch_legal_status'
1 failed, 4 passed
```

SCHEMA-00 预落四字段时**没给默认值**，而本卡 acceptance 要求「缺省值 unknown 生效」。
补默认值后 **5 passed**，additive 校验仍 exit 0（穿透）。

## 3 两处判断写进了代码注释

**① 为什么 `authority_tier`/`fetch_legal_status` 必须是 dataclass 默认值**：
它们的缺省态是产品语义——unknown 权威度 NEVER 满足判 A/B 的必要条件（REGION-03 前置门）、
unknown 合规状态 NEVER 被当作「可抓」（REGION-07）。把「缺省 unknown」只写在文档里，
等于把这条语义交给每个构造点各自记得，那就是它迟早失效的方式。

**② 为什么 `region`/`source_country` 反而 NEVER 给默认值**：
归区是**采集期的事实**。给它默认值等于允许「不知道是哪区也能入库」，
之后所有按 region 分桶的逻辑（B5 聚类分桶、源选集）都会拿到一个假的归属。
测试 `test_region_and_country_are_explicit_not_defaulted` 用 `dataclasses.fields`
断言这两项**没有** default / default_factory。

## 4 acceptance 映射

| acceptance | 测试 |
|---|---|
| 四字段落 `Doc` | `test_four_fields_land_on_doc` |
| （落点核实） | `test_they_did_not_land_on_origin_by_mistake` —— 反向断言：`Origin` 是选题入口五类、与文档溯源无关，四字段 NEVER 出现在它身上。落点错了要能被发现，而不是「Doc 有就算过」 |
| 缺省值 unknown 生效 | `test_unknown_defaults_take_effect`（不传两项构造，断言取值为 unknown） |
| 既有字段零改动（additive 穿透） | `check_frozen_additive` exit 0（本卡改动后复跑） |
| （预填表）TrendItem.region 保留不动 | `test_trenditem_region_is_preserved_untouched`，并断言类型未被收窄 |

## 5 self_review（self_review=true）

① 见 §4；本卡的红态是真的（`TypeError`），不是补造的反证。
② 无冻结件偏离：只改 `contracts_v04/`，`contracts/` 未动；additive 复跑 exit 0。
③ 无禁用词。
④ H 组无命中（schema 卡不碰运行期通道）。
⑤ 装载 1.8k tokens，占 4.5%。

## 6 产出

`tests/v04/schema/test_i2_origin_fields.py`（5 条）+ `contracts_v04/models_v04.py` 的 `Doc` 两处默认值。
