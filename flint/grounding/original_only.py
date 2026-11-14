"""REGION-02（后半）：接地增强(a) 的原文-only 实现。

规格: `docs/grounding_spec_v04.md`（MIGRATE-01）。本模块只做规格 §B 的双判据 + §A2 的守卫。

## 为什么守卫在判据之前

译文进比对会两头都错: 机翻改写措辞与数字表述, 于是「翻得不一样」被判成
「证据不忠实」, 「翻得像」被判成一致。所以先拒绝, 再谈判据 [PRINCIPLES#B10]。

## 为什么「来源没有可提取日期」判不过

「来源没写日期」与「日期对得上」是两回事。把前者当后者放行, 正是
「引真卡 + 编假证据」这个洞的成因——引用编号完全合法, 日期却无人核对。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

Stage = Literal["verdict", "draft"]

# 全角数字 → 半角（仅用于**读取日期**, NEVER 回写原文字段）
_FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")
_DATE_PATTERNS = (
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})"),
    re.compile(r"(\d{4})\s*年"),
)
# 事实锚点: 数字（含全角）与 ≥2 字的词块。判「文本忠实」看的是锚点, 不是逐字包含——
# 规格 §B 明写「改写措辞可以, 引入原文没有的事实 NEVER 可以」。
_NUMBER = re.compile(r"\d+")
_PUNCT = re.compile(r"[、。，,\.\s：:；;（）()「」『』・…—\-~〜]+")
# 中日文没有词间空格, 按「词」切要么需要分词器（新依赖）、要么整句变成一个词块。
# 这里用**字符 3-gram**: 确定性、零依赖, 且对改写措辞宽容、对换内容敏感。
_NGRAM = 3
# 3-gram 重合率下限。低于它 = event 讲的是另一件事。
_MIN_NGRAM_OVERLAP = 0.6


class GroundingOnTranslationError(Exception):
    """接地比对收到译文派生槽。原文字段是唯一合法输入 [PRINCIPLES#B10]。"""


@dataclass(frozen=True)
class GroundingResult:
    """(a) 判据结果。只有过/不过两态, NEVER 与 Alignment 的四态混用。"""

    passed: bool
    text_ok: bool
    date_ok: bool
    reason: str | None


def _reject_if_translated(value: Any, where: str) -> None:
    if value is None or isinstance(value, str):
        return
    if type(value).__name__ == "TranslatedText" or isinstance(value, dict):
        raise GroundingOnTranslationError(
            f"接地比对的 {where} 收到译文派生槽（event / quote_span 等原文槽）: "
            "原文字段才是唯一合法输入 "
            "[PRINCIPLES#B10]; 译文只进 *_display 槽")


def _source_text(cited: Any, doc_text: Any) -> str:
    """证据源: 有 quote_span 以它为准, 否则回落被引 Doc 原文（规格 §B）。"""
    quote = getattr(cited, "quote_span", None)
    _reject_if_translated(quote, "cited.quote_span")
    if quote:
        return str(quote)
    display = getattr(cited, "quote_span_display", None)
    if quote is None and display:
        raise GroundingOnTranslationError(
            "被引侧只有 quote_span_display（译文）而无原文: NEVER 拿译文当证据源")
    return str(doc_text)


def _anchors(text: str) -> tuple[set[str], set[str]]:
    """(数字锚点, 字符 3-gram 集)。归一只用于比对, NEVER 回写原文字段。"""
    normalized = text.translate(_FULLWIDTH)
    numbers = set(_NUMBER.findall(normalized))
    compact = _PUNCT.sub("", normalized)
    grams = {compact[i:i + _NGRAM] for i in range(max(0, len(compact) - _NGRAM + 1))}
    return numbers, grams


def _spans_support_event(event: str, source: str) -> bool:
    """event 的事实性内容 MUST 可在被引原文里定位（规格 §B 判据一）。

    **不是逐字包含**——改写措辞可以。看的是事实锚点:
      · 数字锚点（年份、数量…）**一个都不能是原文里没有的**: 编造最常见的形态
        就是换个数字, 而数字换了句子读起来照样通顺;
      · 字符 3-gram 要有足够重合, 否则 event 讲的是另一件事。
    语义级判定属后续里程碑（沿用既有 CitationAligner 通道, 规格 §B 已写明）,
    这里只做确定性的、宁可漏过不可错放的那一半。
    """
    event_numbers, event_grams = _anchors(event)
    source_numbers, source_grams = _anchors(source)

    if event_numbers - source_numbers:
        return False                                  # 原文没有的数字 = 编造
    if not event_grams:
        return False
    return len(event_grams & source_grams) / len(event_grams) >= _MIN_NGRAM_OVERLAP


def _extract_source_dates(source: str) -> set[date]:
    """被引原文里出现的**全部**日期。

    NEVER 只取第一个: 一段来源常同时含发布日与事件日（「２０２７年に稼働。発表は
    ２０２６年８月１日」）, 取第一个就会把两者搞混, 然后把对的判成错的。
    """
    normalized = source.translate(_FULLWIDTH)
    found: set[date] = set()
    for pattern in _DATE_PATTERNS:
        for m in pattern.finditer(normalized):
            groups = m.groups()
            year = int(groups[0])
            month = int(groups[1]) if len(groups) > 1 else 1
            day = int(groups[2]) if len(groups) > 2 else 1
            found.add(date(year, month, day))
    return found


def check_grounding_a(
    *, evidence: Any, cited: Any, doc_text: Any, stage: Stage = "draft"
) -> GroundingResult:
    """(a) event 文本/日期一致性。输入 MUST 全为原文字段（规格 §A1）。

    `stage` 只用于错误上下文: verdict 与 draft **同规则**, NEVER 只设防一段（§A2）。
    """
    _reject_if_translated(evidence, f"evidence（stage={stage}）")
    _reject_if_translated(doc_text, f"doc_text（stage={stage}）")

    source = _source_text(cited, doc_text)
    text_ok = _spans_support_event(str(evidence.event), source)

    source_dates = _extract_source_dates(source)
    date_ok = evidence.event_date in source_dates

    if text_ok and date_ok:
        return GroundingResult(passed=True, text_ok=True, date_ok=True, reason=None)

    gaps = []
    if not text_ok:
        gaps.append("event 文本含被引原文里定位不到的内容")
    if not source_dates:
        gaps.append("被引原文里提取不到日期（NEVER 以「没写就算过」放行）")
    elif not date_ok:
        gaps.append(
            f"日期不一致: 原文出现 {sorted(source_dates)}, event_date {evidence.event_date}")
    return GroundingResult(
        passed=False, text_ok=text_ok, date_ok=date_ok, reason="；".join(gaps))
