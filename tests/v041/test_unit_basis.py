"""BL-04：字量的两种基准（`cjk_chars` / `tokens`），显式选择 + 必须标注用了哪种。

## 仓里现在是两套单位

模板的 `Ratio.unit` 对 `human_reader` 是 **words**、对 `ai_executor` 是 **tokens**
（`flint/compose/templates.py` 在装载器里强制二选一）；`flint/dag/quality_gate.py`
的 40k 预算也是 tokens。两套各自成立，**混着比就会得出错的结论**——
而报告上只写「字量 6000」时，读的人没法知道那是哪一种，多半会直接比。

## 没有实测分词器时，tokens 数就是**没有**

这是本卡最要紧的一条：`tokens` 侧拿不到真实分词器时，`value` 是 `None`，
**不是 0、也不是拿汉字数顶上**。顶上去的那一刻，一个从未被验证过的数
就变成了下游眼里的事实。

所以 `conversion_factor()` 在任一侧未标定时**抛**，`compare()` 把 `factor` 写成
「未定」——而「今天算不出这个差值」本身就是 owner 要看的数：
它说明现在仓里任何 tokens↔汉字的比较都没有依据。
"""
from __future__ import annotations

import pytest

from eval.unit_basis import (
    BASES,
    ConversionUndefined,
    Measurement,
    basis_note,
    compare,
    conversion_factor,
    count_cjk_chars,
    measure,
)

MIXED = "本季度 GDP 增长 3.5%，AI infra 支出翻倍。"


def fake_tokenizer(text: str) -> int:
    """确定性假分词器：CI 离线（S2-7），真实分词器由调用方注入。"""
    return len(text) // 2


# ───────────────────────── 汉字基准怎么数


def test_cjk_characters_are_counted_one_by_one() -> None:
    assert count_cjk_chars("本季度增长") == 5


def test_a_latin_run_counts_as_one_not_per_letter() -> None:
    """英文词整串记 1——这是中文「字数」的通行口径。

    按字母数记的话，一段夹了几个英文术语的中文会凭空多出几十「字」。
    """
    assert count_cjk_chars("AI") == 1
    assert count_cjk_chars("AI infra") == 2


def test_punctuation_and_whitespace_are_not_counted() -> None:
    """标点与空白两种基准的处理方式不同，计进去会让差值里混进
    一个与「内容多少」无关的量。

    ASCII 标点留在串内（`3.5%` 是一个数），但**纯标点串**不算内容——
    一个串必须含至少一个字母或数字。
    """
    assert count_cjk_chars("，。 \n！") == 0
    assert count_cjk_chars("增长，翻倍。") == 4


def test_a_mixed_sentence_adds_both_kinds() -> None:
    # 汉字 9 个（本季度增长支出翻倍）+ 非 CJK 串 4 个（GDP / 3.5% / AI / infra）
    assert count_cjk_chars(MIXED) == 13


def test_kana_and_hangul_are_not_han_characters() -> None:
    """假名与谚文不算汉字——它们不在 CJK 表意文字区，混进来会让口径悄悄变宽。"""
    assert count_cjk_chars("ひらがな") == 1        # 整串按非 CJK 串记 1
    assert count_cjk_chars("한글") == 1


# ───────────────────────── 基准是显式参数


def test_the_basis_must_be_named_there_is_no_default() -> None:
    """`measure` 没有默认基准——默认值就是下一次口径不一。"""
    import inspect

    params = inspect.signature(measure).parameters

    assert params["basis"].default is inspect.Parameter.empty


def test_an_unknown_basis_is_rejected() -> None:
    with pytest.raises(ValueError, match="basis"):
        measure("x", "words")  # type: ignore[arg-type]


def test_both_bases_are_declared_in_one_place() -> None:
    assert BASES == ("cjk_chars", "tokens")


# ───────────────────────── tokens：没有分词器就是没有数


def test_tokens_without_a_tokenizer_has_no_value_at_all() -> None:
    """**acceptance② 的正题**：拿不到实测分词就没有 tokens 数。

    返回 0 或拿汉字数顶上，都会让一个从未被验证过的数变成下游眼里的事实。
    """
    m = measure(MIXED, "tokens")

    assert m.value is None
    assert m.calibrated is False


def test_tokens_with_an_injected_tokenizer_is_calibrated() -> None:
    """注入实测分词器 → 有数且标定。"""
    m = measure(MIXED, "tokens", fake_tokenizer)

    assert m.value == fake_tokenizer(MIXED)
    assert m.calibrated is True
    assert "fake_tokenizer" in m.method


def test_the_char_basis_is_always_calibrated() -> None:
    """汉字基准的规则写死在代码里，不依赖任何外部件——它恒为已标定。"""
    assert measure(MIXED, "cjk_chars").calibrated is True


# ───────────────────────── 换算系数：未标定就抛


def test_the_factor_is_refused_when_either_side_is_uncalibrated() -> None:
    """NEVER 返回一个能被误用的数——抛出去，让调用方自己决定怎么办。"""
    with pytest.raises(ConversionUndefined) as err:
        conversion_factor(measure(MIXED, "tokens"), measure(MIXED, "cjk_chars"))

    assert "实测" in str(err.value)


def test_the_factor_is_computed_when_both_sides_are_calibrated() -> None:
    """阴性对照：两侧都标定就照算——这道闸拦的是未标定，不是拦所有换算。"""
    tokens = measure(MIXED, "tokens", fake_tokenizer)
    chars = measure(MIXED, "cjk_chars")

    assert conversion_factor(tokens, chars) == pytest.approx(
        (tokens.value or 0) / chars.value  # type: ignore[operator]
    )


def test_an_uncalibrated_measurement_that_does_have_a_number_is_still_refused() -> None:
    """守的是 `calibrated`，**不是** `value is None`。

    这一条是变异考补上来的：把守卫改成只看 `value is None` 时，23 条全绿地活了下来——
    因为今天这两个条件恰好总是同时成立（没分词器 → 既未标定又没有数）。

    但它们不是一回事：哪天有人写一个「估算器」交出
    `Measurement(value=1234, calibrated=False)`，只看 `value` 的守卫会拿这个
    从未被验证过的数算出一个系数——而那正是本模块唯一要拦的事。
    """
    proxy = Measurement(
        basis="tokens", value=1234, calibrated=False, method="某个估算器（未标定）",
    )

    with pytest.raises(ConversionUndefined):
        conversion_factor(proxy, measure(MIXED, "cjk_chars"))


def test_the_same_basis_on_both_sides_is_refused() -> None:
    """同基准之间没有「换算」可言，问这个问题本身就是错的。"""
    with pytest.raises(ConversionUndefined, match="同一基准"):
        conversion_factor(measure(MIXED, "cjk_chars"), measure(MIXED, "cjk_chars"))


def test_a_zero_denominator_is_refused_not_infinite() -> None:
    """空样本 → 未定，NEVER 让它变成一个无穷大或 ZeroDivisionError。"""
    with pytest.raises(ConversionUndefined, match="0"):
        conversion_factor(measure("", "tokens", fake_tokenizer), measure("", "cjk_chars"))


# ───────────────────────── 输出必须标注基准


def test_the_note_names_the_basis_and_the_rule() -> None:
    """acceptance①：报告里必须能看出这次用的是哪种基准。"""
    note = basis_note(measure(MIXED, "cjk_chars"))

    assert "cjk_chars" in note
    assert "CJK" in note


def test_an_uncalibrated_note_says_report_only_in_words() -> None:
    """未标定要**在输出里写明**，不是只在字段里留个 False。

    字段要人去查，句子会被读到——而这句话正是拦住误用的那一下。
    """
    note = basis_note(measure(MIXED, "tokens"))

    assert "未标定" in note
    assert "report_only" in note


def test_a_calibrated_note_does_not_cry_wolf() -> None:
    """阴性对照：标定过的不带那句话，否则那句话会被读成噪音。"""
    assert "未标定" not in basis_note(measure(MIXED, "tokens", fake_tokenizer))


# ───────────────────────── 同一样本两种基准各跑一遍（acceptance③）


def test_compare_runs_both_bases_on_the_same_sample() -> None:
    result = compare(MIXED, fake_tokenizer)

    assert result["cjk_chars"].value == count_cjk_chars(MIXED)
    assert result["tokens"].value == fake_tokenizer(MIXED)
    assert result["delta"] == fake_tokenizer(MIXED) - count_cjk_chars(MIXED)
    assert result["report_only"] is False


def test_compare_without_a_tokenizer_says_undefined_instead_of_a_number() -> None:
    """没有分词器时，差值位置写的是**未定**，不是 0。

    写 0 会被读成「两种基准一样」——那是本卡最想避免的误读。
    """
    result = compare(MIXED)

    assert result["delta"] is None
    assert isinstance(result["tokens_per_char"], str)
    assert "未定" in result["tokens_per_char"]
    assert result["report_only"] is True


def test_compare_carries_both_notes_so_a_report_can_print_them() -> None:
    notes = compare(MIXED)["notes"]

    assert any("cjk_chars" in n for n in notes)
    assert any("tokens" in n and "未标定" in n for n in notes)


def test_the_measurement_is_frozen() -> None:
    """计量结果不可改——改一个已经标注过基准的数，标注就成了假的。"""
    m = measure(MIXED, "cjk_chars")

    with pytest.raises(Exception, match="(?i)frozen|cannot assign"):
        m.value = 1  # type: ignore[misc]


def test_measurement_carries_its_basis_with_it() -> None:
    """数与基准是**一体**的：分开传，下一段代码就会拿错基准的数去比。"""
    assert isinstance(measure(MIXED, "cjk_chars"), Measurement)
    assert measure(MIXED, "cjk_chars").basis == "cjk_chars"
