# SCHEMA-10 trace — I10 TemplateRecord @2026-08-02

## 1 装载
SCHEMA-10 卡 + `models_v04.py` 的 I10 区。~900 字符 ≈ 0.9k tokens（2.3%）。

## 2 test-first（真红 7 条）
先写测试 → **7 failed / 1 passed**：SCHEMA-00 预落的 `TemplateRecord` 只有
template_id/owner/name/source_deliverable_id/html/solidified_at/enabled，
**没有 version / slots / checksum**。按卡补齐后 **8 passed**，additive exit 0，全套 70 passed。

## 3 两条判断写进 docstring
**① checksum 与内容绑定**：模板固化（G5）后会被**生产渲染反复使用**。
若 checksum 与 html 无关，改了模板却不改 checksum，下游拿到的就是
「版本号没变、内容已变」的东西——**产物不可复现**（CLAUDE.md S2-2 第三条铁律）。
实现：`template_checksum(html)` 由内容算出，`__post_init__` 断言 `checksum == 期望值`，
不符即构造期拒绝。**checksum NEVER 由人手填**。

**② slots 是元组且非空**：没有插槽的模板不是模板，是一张静态页——固化它没有意义，
却会占着 `template_id` 让人以为可以拿来生成。用**元组**是因为插槽集合固化后不该被就地追加，
那会绕过 checksum 绑定（`test_slots_is_a_tuple_not_a_list` 断言传 list 抛 `TypeError`）。

## 4 acceptance 映射
| acceptance | 测试 |
|---|---|
| slots 元组非空校验 | `test_empty_slots_are_rejected` / `test_blank_slot_name_is_rejected`（空白项也拒）/ `test_slots_is_a_tuple_not_a_list` |
| checksum 与内容绑定 | `test_checksum_must_match_content`（改 html 不改 checksum → 拒）+ `test_checksum_changes_when_content_changes` |
| （阴性对照） | `test_valid_record_constructs` |
| （预填表 I10） | `test_template_record_coexists_with_template_spec`：与真件既有 `TemplateSpec` 并存且不是同一个类 |

## 5 产出
`tests/v04/schema/test_i10_template.py`（8 条）+ `template_checksum()` + `TemplateRecord`
的 version/slots/checksum 与 `__post_init__`。
