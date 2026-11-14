"""SCHEMA-04 验收：I5 TranslatedText。

acceptance（tasks-v04.json#SCHEMA-04）：
  translated 恒 True；translator 非空；source_field 指向原文字段名。

## 三条要求指向同一件事：译文永远知道自己是译文

`PRINCIPLES#B8`：`name_display[lang]` 是**机翻派生**，MUST 带 `translated=True` 与
`translator` 标记，UI 上只能是次要行。三条要求各自堵一个洞：

- `translated` 恒 True —— 这个槽里放的东西**没有一种情况是原文**。若允许 False，
  就会有人把原文塞进 display 槽，B7「name_native 唯一权威」当场失效。
- `translator` 非空 —— 译者/模型版本是缓存键的一部分（E5：内容 hash = 原文字节 +
  目标语言 + translator 版本）。空 translator 意味着旧译文能冒充新译者的产物。
- `source_field` 指向原文字段名 —— 没有它就不知道这段译文派生自谁，
  「可展开到原文」（B10）也就无从实现。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import get_args

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()


def _ok() -> object:
    return M.TranslatedText(
        text="Solid-state battery", translated=True,
        translator="qwen3.6:35b-a3b@v2", source_field="name_native")


def test_fields_present() -> None:
    assert set(M.TranslatedText.__dataclass_fields__) >= {
        "text", "translated", "translator", "source_field"}


def test_translated_is_pinned_to_true_at_type_level() -> None:
    """`translated` 的类型 MUST 是 Literal[True]——bool 允许 False 就等于允许原文混进来。"""
    ann = M.TranslatedText.__dataclass_fields__["translated"].type
    assert "Literal[True]" in str(ann), f"translated 的标注是 {ann}，应为 Literal[True]"


def test_constructing_with_translated_false_is_rejected() -> None:
    with pytest.raises(ValueError, match="translated"):
        M.TranslatedText(text="x", translated=False, translator="t", source_field="f")


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_translator_is_rejected(bad: str) -> None:
    """空 translator = 旧译文可以冒充新译者的产物（E5 缓存键失效）。"""
    with pytest.raises(ValueError, match="translator"):
        M.TranslatedText(text="x", translated=True, translator=bad, source_field="f")


@pytest.mark.parametrize("bad", ["", "   "])
def test_empty_source_field_is_rejected(bad: str) -> None:
    """没有 source_field 就不知道这段译文派生自谁，B10 的「可展开到原文」无从实现。"""
    with pytest.raises(ValueError, match="source_field"):
        M.TranslatedText(text="x", translated=True, translator="t", source_field=bad)


def test_valid_instance_constructs_and_keeps_values() -> None:
    """阴性对照：合法值必须构造得出来，否则上面三条可能只是「什么都拒」。"""
    t = _ok()
    assert (t.text, t.translated, t.translator, t.source_field) == (
        "Solid-state battery", True, "qwen3.6:35b-a3b@v2", "name_native")


def test_display_slots_are_keyed_by_system_language() -> None:
    """派生槽的键是 SystemLanguage（zh/en），NEVER 是任意字符串。"""
    for cls, field in (
        (M.Cluster, "name_display"),
        (M.WhyNowEvidence, "event_display"),
        (M.Citation, "quote_span_display"),
    ):
        ann = str(cls.__dataclass_fields__[field].type)
        assert "SystemLanguage" in ann and "TranslatedText" in ann, (
            f"{cls.__name__}.{field} 的槽型是 {ann}")
    assert set(get_args(M.SystemLanguage)) == {"zh", "en"}
