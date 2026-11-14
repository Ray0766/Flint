# SCHEMA-07 trace — I7 产物语言 + 同语一致 @2026-08-02

## 1 装载
SCHEMA-07 卡 + `models_v04.py` 的 Deliverable/Block 类体。~1,200 字符 ≈ 1.2k tokens（3%）。

## 2 test-first（真红 4 条）
先写测试 → **4 failed**（`AttributeError`：没有 `check_deliverable_language` 入口）→
实现后 **5 passed**，additive exit 0，全 schema 套 50 passed。

## 3 为什么这条不能靠 dataclass 自己拦
`Block` 拿不到它所属的 `Deliverable`——`Block.deliverable_id` 只是个字符串。
一致性是**跨对象**不变量，只能由显式校验入口来守。散在各处「记得比一下」等于没有：
一份中英混排的产物，读者看到半篇中文半篇英文，而系统全程认为一切正常。

入口放在 `models_v04`，SCHEMA-12 的三不变量套**复用同一入口**，NEVER 另写一份
（两份实现＝两种口径，不变量当场失效）。

## 4 acceptance 映射
| acceptance | 测试 |
|---|---|
| 两侧都有 lang，zh 默认 | `test_both_carry_lang_with_zh_default` |
| 不一致时被拒 | `test_mismatched_block_language_is_rejected`：三块里只有 b2 不一致，断言**报错只点 b2**、不点 b1/b3，且报错文本含两侧语言 |
| （阴性对照） | `test_matching_languages_pass` —— 一致时必须通过，否则「拒绝」可能只是「什么都拒」 |
| （边界） | `test_empty_block_list_passes` —— 刚建的 Deliverable 还没有块，空列表不是不一致 |
| （不含糊） | `test_blocks_belonging_to_another_deliverable_are_rejected` —— 传错对象要报「传错了」，NEVER 当成语言不一致混过去 |

## 5 产出
`tests/v04/schema/test_i7_lang.py`（5 条）+ `check_deliverable_language()`。
