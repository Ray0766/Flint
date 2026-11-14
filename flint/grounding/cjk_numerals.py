"""BL-01：中文数字解析（接地校验器的数字抽取补一条通道）。

## 为什么补

`flint/grounding/__init__.py` 原先的登记原话是「中文数字暂不解析……真实失败态
（deepseek/gpt）均为阿拉伯数字」。那句话描述的是**当时见过的失败态**，不是保证。
模型换一次口径，正文里的「二十六%」就一个字都不会被查——而**没查到与查过没问题
在报告上长得一模一样**（`number` 规则照样 clean）。

## 两种写法，判据只有一条

- **算术式**（含位字 十/百/千/万/亿）：二十六 = 26、一百零五 = 105；
- **数位串式**（不含位字）：二〇二六 = 2026（年份的写法）。

按哪一种读，取决于串里**有没有位字**。混起来的后果很具体：
把二〇二六按算术式读会得到 6。

## 解不出 NEVER 猜

「两千」「廿六」「俩」这类写法本器读不出，一律返回 `None`——但**它们照样进检查面**，
只是没有数值，只能靠原文比对。猜一个数的代价是拿原文里没有的数字去卡片里找，
然后报「疑编造」，而正文其实一个字都没错。

## 什么才算一个数字

一个串要成为检查项，MUST 含至少一个**数位字**（零〇一二三四五六七八九／两俩廿卅）。
「十分」「万一」「千万」只有位字，是词不是数——把它们当数字，每篇正文都会多出
几个查不到出处的「数字」，而尺子一旦每次都报一堆无关项，就没人再看它了。

孤零零一个数位字（「这一趋势」「三者之中」）也不算，除非后面跟着量词单位
（「六%」「五万台」）。代价是「三者」这种真数字会被放过；选这一侧是因为
前者少见、后者遍地都是。已知上限登记在 `docs/trace/BL-01.md#8`。
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

# 数位字：能读出值的
_DIGITS: Final[dict[str, int]] = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
# 数位字：读不出值的（进面但没有数值）。「两/俩」在口语里是 2，
# 但「两千三」这类省略式读法不唯一，NEVER 替作者决定。
_OPAQUE_DIGITS: Final[frozenset[str]] = frozenset("两俩廿卅")
# 位字
_SMALL_UNITS: Final[dict[str, int]] = {"十": 10, "百": 100, "千": 1000}
_BIG_UNITS: Final[dict[str, int]] = {"万": 10**4, "亿": 10**8}

_NUMERAL_CHARS: Final[frozenset[str]] = frozenset(
    set(_DIGITS) | set(_OPAQUE_DIGITS) | set(_SMALL_UNITS) | set(_BIG_UNITS)
)
_UNIT_CHARS: Final[frozenset[str]] = frozenset(set(_SMALL_UNITS) | set(_BIG_UNITS))
_DIGIT_CHARS: Final[frozenset[str]] = frozenset(set(_DIGITS) | set(_OPAQUE_DIGITS))
# 紧跟数字的量词单位（与 `flint/grounding/__init__.py` 的 `_QTY_UNIT` 同源）
_QTY_TAIL: Final[str] = "%％倍元＄$"
_PERCENT_TAIL: Final[str] = "%％"
_PERCENT_HEAD: Final[str] = "百分之"


@dataclass(frozen=True)
class CjkNumeral:
    """正文里的一个中文数字。`value=None` = 本器读不出，但它仍在检查面上。"""

    raw: str
    value: Decimal | None
    is_percent: bool
    # 在正文里的起始位置。抽取器要把中文与阿拉伯两条扫描的结果**按位置合并**——
    # 顺序错了，`missing` 清单里数字的先后就与正文对不上，人工复核时要重新找一遍。
    start: int = 0


def parse_cjk_numeral(text: str) -> Decimal | None:
    """把一串中文数字读成数值。读不出返回 `None`。"""
    if text == "" or any(ch not in _NUMERAL_CHARS for ch in text):
        return None
    if any(ch in _OPAQUE_DIGITS for ch in text):
        return None                                   # 解不出 NEVER 猜
    if not any(ch in _DIGITS for ch in text):
        # 纯位字串（「千万」）。读法是有的（千万 = 10^7），但**在正文里它多半是词**——
        # 那件事归 `_is_numeral` 判，解析器只管读，NEVER 替扫描器做决定。
        return _arithmetic(text)

    if not any(ch in _UNIT_CHARS for ch in text):
        # 数位串式：二〇二六 → 2026。逐字拼，NEVER 相加。
        return Decimal("".join(str(_DIGITS[ch]) for ch in text))
    return _arithmetic(text)


def _arithmetic(text: str) -> Decimal:
    """算术式：二十六 = 26、一百零五 = 105、一亿二千万 = 120000000。"""
    total = 0
    section = 0
    digit: int | None = None
    for ch in text:
        if ch in _DIGITS:
            digit = _DIGITS[ch]
        elif ch in _SMALL_UNITS:
            # 「十六」的十前面没有数位 → 按 1 算
            section += (1 if digit is None else digit) * _SMALL_UNITS[ch]
            digit = None
        else:
            section += digit or 0
            total += section * _BIG_UNITS[ch]
            section = 0
            digit = None
    return Decimal(total + section + (digit or 0))


def find_cjk_numerals(text: str) -> list[CjkNumeral]:
    """扫出正文里的中文数字（按出现位置）。"""
    out: list[CjkNumeral] = []
    i = 0
    while i < len(text):
        if text[i] not in _NUMERAL_CHARS:
            i += 1
            continue
        start = i
        while i < len(text) and text[i] in _NUMERAL_CHARS:
            i += 1
        raw = text[start:i]
        tail = text[i:i + 1]
        # `tail != ""` 不可省：Python 里 `"" in "%％"` 是 **True**，
        # 正文末尾的数字会被一律标成百分数（`flint/grounding/__init__.py` 的
        # 阿拉伯那条至今如此，登记见 docs/blocked/GROUNDING-EMPTY-TAIL.md）。
        is_percent = (tail != "" and tail in _PERCENT_TAIL) or text[:start].endswith(_PERCENT_HEAD)
        if not _is_numeral(raw, tail, is_percent=is_percent):
            continue
        out.append(
            CjkNumeral(
                raw=raw, value=parse_cjk_numeral(raw), is_percent=is_percent, start=start,
            )
        )
    return out


def _is_numeral(raw: str, tail: str, *, is_percent: bool) -> bool:
    """这一串是数字，还是「十分」「万一」「这一」里的字？

    两条判据，都是为了不让每篇正文多出一堆查不到出处的「数字」——
    尺子一旦每次都报无关项，就没人再看它了。
    """
    if raw[0] not in _DIGIT_CHARS and raw[0] != "十":
        return False                                  # 「万一」「千万」：位字开头的是词
    lone = len(raw) == 1                              # 孤零零一个字：要么带量词，要么是词
    return not (lone and (tail == "" or tail not in _QTY_TAIL) and not is_percent)
