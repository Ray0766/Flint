# SCHEMA-06 trace — I6 引文原文/派生分离 @2026-08-02

## 1 装载
SCHEMA-06 卡 + 预填表 I6 + `docs/grounding_spec_v04.md#A2`（MIGRATE-01 产出，本卡依赖）
+ `models_v04.py` 的 WhyNowEvidence/Citation 类体。~2,000 字符 ≈ 2k tokens（5%）。

## 2 test-first（真红 1 条）
先写测试 → **1 failed**：`DID NOT RAISE TypeError` —— 原文槽没有任何守卫，
`evidence.event = TranslatedText(...)` 照样写得进去。
实现守卫后 **7 passed**，additive exit 0，全 schema 套 45 passed。

## 3 守卫要防的是什么
不是「有人故意把译文写进原文字段」，而是 ingest 管线里一句
`evidence.event = translated_text`：标注是 `str`、`TranslatedText` 不是 str，
**但 Python 运行期不拦**。一旦写进去，`PRINCIPLES#B10` 的接地比对就会拿译文去比原文——
「引真卡 + 编假证据」那个洞从另一头被打开。
守卫只挡 `TranslatedText` 实例，**普通字符串赋值照常**（`test_plain_string_assignment_still_works`
是这条的阴性对照，防我顺手把字段钉死）。

## 4 acceptance 映射
| acceptance | 测试 |
|---|---|
| 日文 fixture 入库后原文字段字节等同 | `test_japanese_event_round_trips_byte_for_byte` / `..._quote_...`：fixture 含全角数字「２０２７」、片假名、长音符——翻译与归一化最容易改动的字形 |
| 派生槽独立可空 | `test_display_slots_are_independently_optional` |
| 原文槽 NEVER 被翻译写入 | `test_writing_a_translation_into_the_original_slot_is_rejected`，且断言拒绝后原文不变 |
| （不越界） | `test_plain_string_assignment_still_works` |
| （预填表槽位收敛） | `test_event_date_has_no_display_slot`：`event_date` 是 date、无原文文本，本地化在渲染层，反向断言它**没有** display 槽 |

## 5 self_review（self_review=true）
① 见 §4，红态真实（DID NOT RAISE）。② 只改 contracts_v04/，additive exit 0。③ 无禁用词。
④ 本卡把 B10 的约束落到类型层，与 MIGRATE-01 规格同源，无 H 组命中。⑤ 装载 2k tokens（5%）。

## 6 产出
`tests/v04/schema/test_i6_original_display.py`（7 条）+ `WhyNowEvidence.__setattr__` / `Citation.__setattr__` 两处守卫。
