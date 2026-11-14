"""REGION-02（后半）验收：接地原文-only 接线。

acceptance（tasks-v04.json#REGION-02）：
  ① 对派生槽调用接地 → `GroundingOnTranslationError`；
  ② event 文本/日期一致性校验按 **MIGRATE-01 规格**实现并过**反例 fixture**。

规格：`docs/grounding_spec_v04.md`（§A2 译文禁入比对、§B 双判据、§C 错误类型）。
反例来自 PRIN-02 的 fixture 集（`PRINCIPLES#B9/#B10` 两条的「反例」段），
NEVER 在这里另编一套反例——那样测的就不是规范里那条了。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _models() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()

from flint.grounding.original_only import (
    GroundingOnTranslationError,
    check_grounding_a,
)
from tests.v04.principles.fixtures import load

JA_EVENT = "トヨタ、全固体電池の量産ラインを２０２７年に稼働へ"
JA_SOURCE = "トヨタは全固体電池の量産ラインを２０２７年に稼働させる。発表は２０２６年８月１日。"
EVENT_DATE = date(2027, 1, 1)


def _evidence(event: str = JA_EVENT, when: date = EVENT_DATE, display: object = None) -> object:
    return M.WhyNowEvidence(
        event=event, event_date=when, citation_id="cit-1", event_display=display)


def _citation(quote: str | None = JA_SOURCE, display: object = None) -> object:
    return M.Citation(
        citation_id="cit-1", doc_id="doc-1", locator=None,
        quote_span=quote, quote_span_display=display)


def _translated(text: str, source_field: str) -> object:
    return M.TranslatedText(
        text=text, translated=True, translator="fixture-identity@v1",
        source_field=source_field)


# ── ① 译文禁入比对（规格 §A2 / §C） ──────────────────────────────────

def test_translated_event_slot_raises() -> None:
    bad = _translated("丰田将于2027年启动全固态电池量产线", "event")
    with pytest.raises(GroundingOnTranslationError, match="event"):
        check_grounding_a(evidence=bad, cited=_citation(), doc_text=JA_SOURCE)


def test_translated_source_text_raises() -> None:
    bad = _translated("丰田将于2027年启动量产线。", "quote_span")
    with pytest.raises(GroundingOnTranslationError, match="doc_text"):
        check_grounding_a(evidence=_evidence(), cited=_citation(), doc_text=bad)


def test_display_slot_of_citation_raises() -> None:
    """被引侧取 quote_span_display 也是译文入比对——同样拒。"""
    cited = _citation(quote=None, display={"zh": _translated("丰田…", "quote_span")})
    with pytest.raises(GroundingOnTranslationError):
        check_grounding_a(evidence=_evidence(), cited=cited, doc_text=JA_SOURCE)


def test_both_stages_are_guarded() -> None:
    """规格 §A2：verdict 与 draft 两段同受约束，NEVER 只设防一段。"""
    bad = _translated("丰田…", "event")
    for stage in ("verdict", "draft"):
        with pytest.raises(GroundingOnTranslationError):
            check_grounding_a(
                evidence=bad, cited=_citation(), doc_text=JA_SOURCE, stage=stage)


# ── ② 双判据（规格 §B） ───────────────────────────────────────────────

def test_faithful_event_with_matching_date_passes() -> None:
    result = check_grounding_a(
        evidence=_evidence(), cited=_citation(), doc_text=JA_SOURCE)
    assert result.passed is True
    assert result.text_ok is True and result.date_ok is True


def test_fabricated_event_fails_text_criterion() -> None:
    """引真卡 + 编假证据：引用合法，叙述是模型自己写的。"""
    made_up = _evidence(event="トヨタ、全固体電池の量産を２０２５年に前倒し完了と発表")
    result = check_grounding_a(
        evidence=made_up, cited=_citation(), doc_text=JA_SOURCE)
    assert result.passed is False and result.text_ok is False
    assert result.reason


def test_date_mismatch_fails_even_when_text_is_faithful() -> None:
    wrong_date = _evidence(when=date(2030, 1, 1))
    result = check_grounding_a(
        evidence=wrong_date, cited=_citation(), doc_text=JA_SOURCE)
    assert result.passed is False and result.date_ok is False


def test_source_without_extractable_date_fails() -> None:
    """规格 §B：来源无可提取日期 → 判**不过**。

    「来源没写日期」与「日期对得上」是两回事，把前者当后者放行正是这个洞的成因。
    """
    result = check_grounding_a(
        evidence=_evidence(), cited=_citation(quote="トヨタは全固体電池の量産ラインを稼働させる。"),
        doc_text="トヨタは全固体電池の量産ラインを稼働させる。")
    assert result.passed is False and result.date_ok is False


def test_quote_span_is_preferred_over_full_doc() -> None:
    """有 quote_span 时以它为证据源（规格 §B）——全文里有、引语里没有的事实不算数。"""
    cited = _citation(quote="トヨタは電池工場を建設する。２０２７年。")
    result = check_grounding_a(
        evidence=_evidence(event="トヨタ、全固体電池の量産ラインを２０２７年に稼働へ"),
        cited=cited, doc_text=JA_SOURCE)
    assert result.text_ok is False, "引语里没有『全固体電池の量産ライン』，不该靠全文兜底"


# ── 反例 fixture（PRIN-02 的 B9/B10 两条） ────────────────────────────

def test_b9_and_b10_counterexamples_are_covered() -> None:
    """反例来自规范正文，NEVER 在测试里另编一套。"""
    b9 = load("B9")["counter_examples"]
    b10 = load("B10")["counter_examples"]
    assert any("ingest" in c and "翻" in c for c in b9), b9
    assert any("display" in c for c in b10), b10

    # B9 反例：ingest 时统一翻成中文写入原文字段 → 原文槽守卫拦住
    with pytest.raises(TypeError):
        M.WhyNowEvidence(
            event=JA_EVENT, event_date=EVENT_DATE, citation_id="c", event_display=None,
        ).event = _translated("丰田…", "event")

    # B10 反例：对 event_text_display 跑一致性比对 → GroundingOnTranslationError
    with pytest.raises(GroundingOnTranslationError):
        check_grounding_a(
            evidence=_translated("丰田…", "event"), cited=_citation(), doc_text=JA_SOURCE)
