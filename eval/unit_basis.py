"""BL-04：字量的两种基准（`cjk_chars` / `tokens`），显式选择、结果自带基准标注。

## 为什么要显式选

仓里同时存在两套单位：模板的 `Ratio.unit` 对 `human_reader` 是 **words**、对
`ai_executor` 是 **tokens**（`flint/compose/templates.py` 在装载器里强制二选一），
`flint/dag/quality_gate.py` 的 40k 预算也是 tokens。

两套各自成立，**混着比就会得出错的结论**。而报告上只写「字量 6000」时，
读的人没法知道那是哪一种——他多半会直接比。本模块不选边，只做两件事：
**基准是显式参数**，**结果自带基准标注**。

## 没有实测分词器时，tokens 数就是「没有」

`tokens` 侧拿不到真实分词器时 `value is None`——**不是 0，也不是拿汉字数顶上**。
顶上去的那一刻，一个从未被验证过的数就成了下游眼里的事实。

「1 个汉字 ≈ N tokens」这种系数**只能来自实测分词**。所以
`conversion_factor()` 在任一侧未标定时**抛** `ConversionUndefined`，
`compare()` 把系数位置写成「未定」，`basis_note()` 把这句话写进输出。

**「今天算不出这个差值」本身就是一个结论**：它说明现在仓里任何
tokens↔汉字的比较都没有依据。

## 两种基准怎么数

| 基准 | 规则 |
|---|---|
| `cjk_chars` | CJK 表意文字**逐字** 1；非 CJK 的连续串（英文词、数字、URL）**整串** 1。中文「字数」的通行口径 |
| `tokens` | 由**注入的**分词器给出；没有就没有数 |

标点与空白两种基准都不计：它们在两侧的处理方式不同，计进去会让差值里混进
一个与「内容多少」无关的量。
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Literal

Basis = Literal["cjk_chars", "tokens"]
BASES: Final[tuple[Basis, ...]] = ("cjk_chars", "tokens")

# CJK 统一表意文字（含扩展 A）+ 兼容表意文字。假名/谚文不在内——它们不是汉字，
# 算进来等于让「汉字口径」这个名字悄悄变宽。
_CJK_CLASS: Final[str] = r"㐀-䶿一-鿿豈-﫿"
_CJK: Final[re.Pattern[str]] = re.compile(f"[{_CJK_CLASS}]")
# 连续的非空白、非 CJK、非 CJK 标点串（英文词 / 数字 / URL 片段）。
# ASCII 标点**留在串内**：`3.5%` 是一个数不是两个，`a/b.c` 是一个 URL 片段不是三段。
# 代价是纯 ASCII 标点串（`---`、`...`）也会被切出来——所以再滤一道：
# 一个串必须含至少一个**词字符**才算内容。判据用 `\w`（Unicode 口径）而不是
# `[0-9A-Za-z]`：后者会把假名、谚文、西里尔文整串判成 0——那是**静默漏计**，
# 而本模块存在的理由正是不让口径悄悄变化。
_NON_CJK_RUN: Final[re.Pattern[str]] = re.compile(f"[^\\s{_CJK_CLASS}　-〿＀-￯]+")
_HAS_WORD_CHAR: Final[re.Pattern[str]] = re.compile(r"\w")

Tokenizer = Callable[[str], int]


class ConversionUndefined(Exception):
    """两种基准之间的换算系数未标定——NEVER 拍一个数顶上。"""

    def __init__(self, why: str) -> None:
        super().__init__(
            f"换算系数未定：{why}。系数只能来自实测分词；在那之前相关比值 report_only。"
        )


@dataclass(frozen=True)
class Measurement:
    """一次计量。**数与基准是一体的**——分开传，下一段代码就会拿错基准的数去比。

    `value is None` = 这个基准今天量不出来（NEVER 用 0 表示）。
    """

    basis: Basis
    value: int | None
    calibrated: bool
    method: str


def count_cjk_chars(text: str) -> int:
    """汉字口径：CJK 逐字 1，非 CJK 连续串整串 1，标点与空白不计。

    按字母数记英文的话，一段夹了几个英文术语的中文会凭空多出几十「字」。
    """
    runs = [r for r in _NON_CJK_RUN.findall(text) if _HAS_WORD_CHAR.search(r)]
    return len(_CJK.findall(text)) + len(runs)


def count_tokens(text: str, tokenizer: Tokenizer | None = None) -> Measurement:
    """token 口径。给了分词器就是**实测**；没给就**没有数**。"""
    if tokenizer is None:
        return Measurement(
            basis="tokens",
            value=None,
            calibrated=False,
            method="无实测分词器——本基准今天量不出来（NEVER 拿汉字数顶上）",
        )
    name = getattr(tokenizer, "__name__", type(tokenizer).__name__)
    return Measurement(
        basis="tokens", value=tokenizer(text), calibrated=True,
        method=f"实测分词器 {name}",
    )


def measure(text: str, basis: Basis, tokenizer: Tokenizer | None = None) -> Measurement:
    """按指定基准计量。基准**没有默认值**——默认值就是下一次口径不一。"""
    if basis == "cjk_chars":
        return Measurement(
            basis="cjk_chars",
            value=count_cjk_chars(text),
            calibrated=True,
            method="CJK 表意文字逐字 1 + 非 CJK 连续串整串 1（标点与空白不计）",
        )
    if basis == "tokens":
        return count_tokens(text, tokenizer)
    raise ValueError(f"unknown basis: {basis!r}（只有 {BASES}）")


def basis_note(measurement: Measurement) -> str:
    """报告里**必须**带上的那一行：用了哪种基准、标没标定。

    只写数字不写基准，读的人无从判断这个数能不能与另一份比。
    未标定那句话要**成句写出来**——字段要人去查，句子会被读到。
    """
    head = f"字量基准 = {measurement.basis}（{measurement.method}）"
    if measurement.calibrated:
        return head
    return f"{head}｜**未标定**：本数仅供参照，跨基准比值 report_only"


def conversion_factor(left: Measurement, right: Measurement) -> float:
    """`left.value / right.value`。任一侧未标定即**抛**，NEVER 返回一个能被误用的数。"""
    if left.basis == right.basis:
        raise ConversionUndefined(f"两侧是同一基准 {left.basis}，没有换算可言")
    missing = [m.basis for m in (left, right) if not m.calibrated or m.value is None]
    if missing:
        raise ConversionUndefined(f"{missing} 侧没有实测分词器")
    assert left.value is not None and right.value is not None      # 上一步已排除
    if right.value == 0:
        raise ConversionUndefined("分母为 0（样本里没有可计量内容）")
    return left.value / right.value


def compare(text: str, tokenizer: Tokenizer | None = None) -> dict[str, Any]:
    """同一份样本**两种基准各跑一遍**，把差值摆出来（acceptance③）。

    没有分词器时 `delta is None`、系数写「未定」——**NEVER 写 0**：
    0 会被读成「两种基准一样」，那是本模块最想避免的误读。
    """
    chars = measure(text, "cjk_chars")
    tokens = measure(text, "tokens", tokenizer)
    try:
        factor: float | str = conversion_factor(tokens, chars)
    except ConversionUndefined as err:
        factor = f"未定（{err}）"
    delta = (
        None if tokens.value is None or chars.value is None
        else tokens.value - chars.value
    )
    return {
        "cjk_chars": chars,
        "tokens": tokens,
        "delta": delta,
        "tokens_per_char": factor,
        "notes": [basis_note(chars), basis_note(tokens)],
        "report_only": not (chars.calibrated and tokens.calibrated),
    }
