# SCHEMA-05 trace — I4 名称三元组落 Cluster @2026-08-02

## 1 装载

SCHEMA-05 卡 + 预填表 I4 与注记 2 + `PRINCIPLES#B7/#B8` + `models_v04.py` 的 `Cluster` 类体。
~2,000 字符 ≈ 2k tokens（5%）。

## 2 真冲突：acceptance 写「frozen」，真件是非 frozen

四份来源里三份口径一致（真件非 frozen / 预填表注记 2 / 工单 §3-B7「写路径校验」），
只有 `tasks-v04.json` 的 acceptance 措辞滞后写着「frozen 拒二次赋值」。

按 §1.4 **以 contracts/ 为准**并留痕 → `docs/blocked/SCHEMA-05-FROZEN-WORDING.md`（非阻塞）。

**为什么不能照字面改 frozen**：`Cluster` 有 `status` / `last_active` / `merged_into` / `aliases`
等本来就要变的字段（簇活跃度与合并血缘每日更新）。整类 frozen 会改既有字段语义，
那不是增量，是改既有契约。

**实现**：字段级写一次——`__setattr__` 只拒 `name_native` 的二次赋值，其余字段照常可变。
既满足 acceptance 的意图，又不动既有语义。

## 3 test-first（真红 3 条）

先写测试 → **3 failed**（二次赋值没被拒）→ 实现 `__setattr__` → **9 passed**，
additive exit 0，全 schema 套 38 passed。

## 4 acceptance 映射

| acceptance | 测试 |
|---|---|
| name_native 写后读回**字节**等同 | `test_name_native_round_trips_byte_for_byte`，三个真实样本参数化：日文 / 全角字母与全角空格 / 韩文含连续空格 |
| 拒二次赋值 | `test_name_native_rejects_second_assignment`，且断言**拒绝后原值不变** |
| （不越界） | `test_other_fields_stay_mutable` —— 反向断言其余字段仍可变，防我「顺手全钉死」 |
| name_display 槽为 TranslatedText 判别 | `test_name_display_slot_is_translated_text_keyed_by_language`：标注含 `SystemLanguage` 与 `TranslatedText`，且真构造一个 en 译名断言 `source_field == "name_native"` |
| （预填表）canonical_name 保留 | `test_canonical_name_is_preserved_alongside_native` |

**为什么「字节等同」值得单独测**：B7 的失守方式不是有人手动改名，而是**入库时顺手归一化**
（全角转半角、去空白、大小写折叠、NFC/NFKC）。这些都「看起来没改内容」，
但 embedding 与去重吃的是字节——一次归一化就让同一个热点在两天里变成两个簇。
三个样本正是照这三种归一化挑的。

## 5 产出

`tests/v04/schema/test_i4_names.py`（9 条）+ `Cluster.__setattr__` 字段级写一次
+ `docs/blocked/SCHEMA-05-FROZEN-WORDING.md`。
