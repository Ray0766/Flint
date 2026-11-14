# SCHEMA-04 trace — I5 TranslatedText @2026-08-02

## 1 装载

SCHEMA-04 卡 + `PRINCIPLES#B8/#B9` + `models_v04.py` 的 I5 区。~1,400 字符 ≈ 1.4k tokens（3.5%）。

## 2 test-first（真红 6 条）

先写测试 → **6 failed / 3 passed**：SCHEMA-00 预落的 `TranslatedText` 用的是
`translated: bool`（允许 False），且对 `translator` / `source_field` **零非空强制**。

实现三条不变量后 **9 passed**，additive exit 0，全 schema 套 29 passed。

## 3 一处刻意破例：契约里写了 `__post_init__`

冻结件的风格是「纯类型定义, 无实现」。这里破例加了 `__post_init__` 校验，理由：

- `translated` 恒 True 能靠类型钉（`Literal[True]`），但 **`translator` 非空 / `source_field`
  非空钉不住**——类型系统表达不了「非空字符串」；
- 这三条是**构造期不变量**。只写在文档里，就等于交给每个构造点各自记得，
  那正是它失效的方式。

破例范围仅限「拒绝非法构造」，不含任何业务逻辑。

## 4 acceptance 映射

| acceptance | 测试 |
|---|---|
| translated 恒 True | `test_translated_is_pinned_to_true_at_type_level`（标注必须是 `Literal[True]`）+ `test_constructing_with_translated_false_is_rejected` |
| translator 非空 | `test_empty_translator_is_rejected`（`""` 与 `"   "` 两参数化——只挡空串挡不住空白串） |
| source_field 指向原文字段名 | `test_empty_source_field_is_rejected` + `test_valid_instance_constructs_and_keeps_values` 断言值确为 `name_native` |
| （阴性对照） | `test_valid_instance_constructs_and_keeps_values` —— 合法值必须构造得出来，否则上面三条可能只是「什么都拒」 |
| （槽型一致） | `test_display_slots_are_keyed_by_system_language`：三个 display 槽都是 `dict[SystemLanguage, TranslatedText]`，键 NEVER 是任意字符串 |

## 5 产出

`tests/v04/schema/test_i5_translated_text.py`（9 条）+ `TranslatedText` 的 `Literal[True]` 与 `__post_init__`。
