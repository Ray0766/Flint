"""SCHEMA-06 验收：I6 引文原文/派生分离。

acceptance（tasks-v04.json#SCHEMA-06）：
  ① 日文 fixture 入库后原文字段字节等同；
  ② 派生槽独立可空；原文槽 NEVER 被翻译写入。

## 要防的是哪种失守

不是「有人故意把译文写进原文字段」，而是 ingest 管线里一句
`evidence.event = translated_text` —— 类型标注是 `str`，`TranslatedText` 不是 str，
但 Python 运行期不拦；而一旦写进去，`PRINCIPLES#B10` 的接地比对就会拿译文去比原文，
「引真卡+编假证据」那个洞就从另一头被打开了。

`event_date` 是 `date`，无原文文本，本地化在渲染层 → **NEVER 设 display 槽**
（预填表 I6 的槽位收敛）。本测试反向断言它确实没有。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

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

# 日文 fixture：含全角空格、片假名、汉字、长音符——都是翻译或归一化最容易改动的字形
JA_EVENT = "トヨタ、全固体電池の量産ラインを２０２７年に稼働へ"
JA_QUOTE = "量産ラインは２０２７年に稼働する見込み。"


def _evidence(display: object = None) -> object:
    return M.WhyNowEvidence(
        event=JA_EVENT, event_date=date(2026, 8, 2), citation_id="cit-1",
        event_display=display)


def _citation(display: object = None) -> object:
    return M.Citation(
        citation_id="cit-1", doc_id="doc-1", locator="p.3",
        quote_span=JA_QUOTE, quote_span_display=display)


def _translated(text: str, source_field: str) -> object:
    return M.TranslatedText(
        text=text, translated=True, translator="qwen3.6:35b-a3b@v2",
        source_field=source_field)


def test_japanese_event_round_trips_byte_for_byte() -> None:
    e = _evidence()
    assert e.event == JA_EVENT
    assert e.event.encode("utf-8") == JA_EVENT.encode("utf-8"), "event 原文被改动了"


def test_japanese_quote_round_trips_byte_for_byte() -> None:
    c = _citation()
    assert c.quote_span.encode("utf-8") == JA_QUOTE.encode("utf-8"), "quote_span 原文被改动了"


def test_display_slots_are_independently_optional() -> None:
    """派生槽独立可空：没有译文时是 None，原文照常可用。"""
    assert _evidence().event_display is None
    assert _citation().quote_span_display is None


def test_display_slots_hold_translations_without_touching_originals() -> None:
    e = _evidence({"zh": _translated("丰田将于2027年启动全固态电池量产线", "event")})
    c = _citation({"zh": _translated("量产线预计2027年投产。", "quote_span")})
    assert e.event == JA_EVENT, "写译文时原文 MUST 一字不动"
    assert c.quote_span == JA_QUOTE
    assert e.event_display["zh"].source_field == "event"
    assert c.quote_span_display["zh"].source_field == "quote_span"


def test_writing_a_translation_into_the_original_slot_is_rejected() -> None:
    """原文槽 NEVER 被翻译写入——ingest 里一句赋值就能毁掉 B10 的接地前提。"""
    e = _evidence()
    with pytest.raises(TypeError, match="event"):
        e.event = _translated("丰田…", "event")
    assert e.event == JA_EVENT, "拒绝之后原文 MUST 保持不变"

    c = _citation()
    with pytest.raises(TypeError, match="quote_span"):
        c.quote_span = _translated("量产线…", "quote_span")
    assert c.quote_span == JA_QUOTE


def test_plain_string_assignment_still_works() -> None:
    """阴性对照：只挡 TranslatedText，正常的原文修正 NEVER 被误伤。"""
    e = _evidence()
    e.event = "トヨタ、全固体電池の量産ラインを２０２８年に稼働へ"
    assert "２０２８" in e.event


def test_event_date_has_no_display_slot() -> None:
    """预填表 I6 槽位收敛：event_date 是 date，无原文文本，本地化在渲染层。"""
    fields = set(M.WhyNowEvidence.__dataclass_fields__)
    assert "event_date" in fields
    assert not [f for f in fields if "date" in f and "display" in f], (
        f"event_date 不该有 display 槽：{sorted(fields)}")
