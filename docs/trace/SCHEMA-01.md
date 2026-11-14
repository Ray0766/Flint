# SCHEMA-01 trace — I1 四枚举 @2026-08-02

## 1 装载

SCHEMA-01~14 十四张卡的元数据一次读齐（~3,000 字符，避免逐卡往返）+ `models_v04.py` 的 I1 增量区。
合计 ~3,500 字符 ≈ 3.5k tokens，占 8.8%。

## 2 test-first 被 SCHEMA-00 的越界破坏了（如实记，影响整个 V1）

**问题**：SCHEMA-00 的职责是「副本基建」，我在建副本时把 **I1~I13 的全部增量一次性落了进去**——
而那些增量各自归 SCHEMA-01~14 所有（每张卡的 outputs 都写着 `contracts_v04/models_v04.py`）。

**后果**：本卡的测试**首跑即绿**，红态无从制造，§4.2 的「先红后绿」顺序在结构上被破坏。

**补救**（恢复 test-first 的**目的**，即「证明这测试能发现缺失」）：
把枚举改坏（`Region` 塞进 `EU`、`SystemLanguage` 多一个 `ja`）后复跑——

```
FAILED test_region_is_nine_and_has_no_eu
FAILED test_system_language_is_exactly_zh_en
FAILED test_out_of_enum_values_are_rejected_by_mypy[EU-...]
FAILED test_out_of_enum_values_are_rejected_by_mypy[CN-ja-...]
4 failed, 5 passed
```

还原后 9 passed（还原以 md5 复核）。**这不是等价于先红后绿，只是等价强度的反空转证据**——
顺序确实被破坏了，我不打算把它说成没破坏。

后续 SCHEMA-02~14 同此处境：预落的形状与各卡 acceptance **有五处不符**
（I8 `source_kind`/`archived`、I9 `evidence_snapshot`/`snapshot_stale`、I10 `slots`/`checksum`、
I11 `password_hash`/friend 缝、I13 `design_check` 三态），这些卡仍有真实的实现工作与真实红态。

## 3 acceptance 映射

| acceptance | 测试 | 说明 |
|---|---|---|
| 九区无 EU | `test_region_is_nine_and_has_no_eu` | 集合逐字比对 + 显式断言 `EU not in` |
| 语言仅 zh/en | `test_system_language_is_exactly_zh_en` | 集合相等 |
| 权威度五值含 unknown | `test_authority_tier_has_five_values_including_unknown` | 集合相等 + 显式断言 `unknown in` |
| **枚举外值构造被拒** | `test_out_of_enum_values_are_rejected_by_mypy`（5 参数化） | 见下 |

**「构造被拒」的执行者是 mypy，不是运行期**：四枚举是 `Literal` 别名，
`Doc(..., authority_tier="bogus")` 在运行期照样构造成功。所以本测试**真的起 mypy 子进程**
编译越界赋值并断言报错；同时编译一段合法赋值断言**不**报错——
阳性/阴性成对，防「mypy 对什么都报错」式的假绿。

只断言 `get_args()` 成员集合是不够的：那只证明「我写的字面量是这几个」，
证明不了「写别的会被挡住」。

## 4 产出

`tests/v04/schema/test_i1_enums.py`（9 条断言全绿）。
`contracts_v04/models_v04.py` 的 I1 区由 SCHEMA-00 预落，本卡未改。
