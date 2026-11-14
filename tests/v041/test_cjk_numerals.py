"""BL-01：接地校验器补中文数字（「二十六%」当前解不出）。

## 这条缝为什么危险

`extract_numbers` 只认阿拉伯数字，登记原话是「中文数字暂不解析……真实失败态
（deepseek/gpt）均为阿拉伯数字」。那句话描述的是**当时见过的失败态**，不是保证。
模型改一次口径，正文里的「二十六%」就一个字都不会被查——而**没查到与查过没问题
在报告上长得一模一样**（`number` 规则照样 clean）。

## 解不出也要出声

「两成」「廿六」这类写法本器解不出。解不出时 **NEVER 静默跳过**：
它们照样进入检查面，只是没有数值，只能靠原文比对。卡面原话——
「静默＝正文里一个没出处的数字溜过去」。

## 两种写法，两种含义

- **算术式**（带位）：二十六 = 26、一百零五 = 105、一亿二千万 = 120000000；
- **数位串式**（不带位）：二〇二六 = 2026（年份的写法）。

同一串字符按哪一种读，取决于**里面有没有位字**。混起来的后果很具体：
把二〇二六按算术式读会得到 6。

## 只加不改

阿拉伯数字那条路一个字不动（acceptance③）——本文件末尾用既有用例的输入
逐条复核它的输出。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from flint.grounding import GroundingConfig, extract_numbers
from flint.grounding.cjk_numerals import CjkNumeral, find_cjk_numerals, parse_cjk_numeral

CFG = GroundingConfig()


# ───────────────────────── 算术式：十/百/千/万/亿


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("一", 1),
        ("十", 10),
        ("十六", 16),
        ("二十", 20),
        ("二十六", 26),
        ("一百", 100),
        ("一百零五", 105),
        ("三百二十一", 321),
        ("一千", 1000),
        ("一千零一", 1001),
        ("三千二百", 3200),
        ("一万", 10000),
        ("三万五千", 35000),
        ("一亿", 100000000),
        ("一亿二千万", 120000000),
        ("十二亿三千四百五十六万七千八百九十", 1234567890),
    ],
)
def test_arithmetic_forms(text: str, expected: int) -> None:
    assert parse_cjk_numeral(text) == Decimal(expected)


def test_zero_is_a_placeholder_not_a_digit_to_append() -> None:
    """「一百零五」是 105，不是 1005——零在算术式里是**占位**。

    读成 1005 的那天，接地校验会拿一个不存在的数字去卡原文里找，
    找不到就报「疑编造」——而正文其实一个字都没错。
    """
    assert parse_cjk_numeral("一百零五") == Decimal(105)
    assert parse_cjk_numeral("一千零一") == Decimal(1001)


# ───────────────────────── 数位串式：年份的写法


@pytest.mark.parametrize(
    ("text", "expected"),
    [("二〇二六", 2026), ("二零二五", 2025), ("一九九八", 1998)],
)
def test_digit_string_forms(text: str, expected: int) -> None:
    """不带位字 = 数位串式。按算术式读「二〇二六」会得到 6。"""
    assert parse_cjk_numeral(text) == Decimal(expected)


def test_which_reading_is_decided_by_the_presence_of_a_unit_character() -> None:
    """两种读法的判据只有一条：**里面有没有位字**。

    「二〇二六」（无位）→ 2026；「二十六」（有十）→ 26。
    两串长得像，含义差两个数量级。
    """
    assert parse_cjk_numeral("二〇二六") == Decimal(2026)
    assert parse_cjk_numeral("二十六") == Decimal(26)


# ───────────────────────── 解不出的要报出原文


@pytest.mark.parametrize("text", ["两", "俩", "廿", "卅", "廿六", "两千"])
def test_forms_this_parser_cannot_read_return_none(text: str) -> None:
    """解不出返回 None——**NEVER 猜一个数**。

    猜错的代价是拿一个原文里没有的数字去卡片里找，然后报「疑编造」。
    """
    assert parse_cjk_numeral(text) is None


def test_an_unreadable_numeral_still_shows_up_with_its_raw_text() -> None:
    """acceptance②：解不出**不等于**没有数字。

    它照样进检查面，`value=None`、`raw` 是原文——上层只能靠原文比对，
    但至少它在面上。静默跳过 = 正文里一个没出处的数字溜过去。
    """
    found = find_cjk_numerals("增长廿六%")

    assert [(n.raw, n.value, n.is_percent) for n in found] == [("廿六", None, True)]


# ───────────────────────── 在句子里找（scanner 的面）


def test_a_percent_mix_is_found_with_the_percent_flag() -> None:
    """卡面点名的那一例：「二十六%」。"""
    found = find_cjk_numerals("该指标同比上升二十六%。")

    assert found == [CjkNumeral(raw="二十六", value=Decimal(26), is_percent=True, start=7)]


def test_the_full_width_percent_sign_counts_too() -> None:
    """全角％与半角%一样算——中文正文里两种都常见。"""
    assert find_cjk_numerals("上升二十六％")[0].is_percent is True


def test_bai_fen_zhi_is_a_percent_too() -> None:
    """「百分之二十六」也是百分数，且**不会**把「百分之」自己读成一个数。"""
    found = find_cjk_numerals("占比百分之二十六。")

    assert [(n.raw, n.value, n.is_percent) for n in found] == [("二十六", Decimal(26), True)]


def test_several_numerals_in_one_sentence_are_all_found() -> None:
    found = find_cjk_numerals("一千二百家门店，同比增长三十五%。")

    assert [n.raw for n in found] == ["一千二百", "三十五"]


def test_a_run_without_any_digit_character_is_not_a_numeral() -> None:
    """没有数位字的串不算数字：「十分」「万一」「千万」是词，不是数。

    把它们当数字的后果是每篇正文都多出几个查不到出处的「数字」，
    而尺子一旦每次都报一堆无关项，就没人再看它了。
    """
    assert find_cjk_numerals("十分满意，万一失手，千万小心") == []


def test_a_lone_digit_without_a_unit_is_left_alone() -> None:
    """孤零零一个数位字（「一个」「三者」）不算——**已知上限，登记在 trace §8**。

    代价是「三」这种真数字也会被放过；收益是不会把「一直」「一致」里的
    「一」变成检查项。选这一侧是因为前者少见、后者遍地都是。
    """
    assert find_cjk_numerals("这一趋势") == []
    assert find_cjk_numerals("三者之中") == []


def test_a_lone_digit_with_a_unit_is_a_numeral() -> None:
    """带单位就算：「六%」「五万」。"""
    assert [n.raw for n in find_cjk_numerals("涨了六%")] == ["六"]
    assert [n.raw for n in find_cjk_numerals("五万台")] == ["五万"]


# ───────────────────────── 接进接地校验器


def test_extract_numbers_now_sees_chinese_quantities() -> None:
    """acceptance①：`extract_numbers` 把中文数字一并交出来。"""
    nums = extract_numbers("同比上升二十六%", CFG)

    assert [(n.raw, n.kind, n.value, n.is_percent) for n in nums] == [
        ("二十六", "quantity", Decimal(26), True),
    ]


def test_a_chinese_year_is_classified_as_a_year() -> None:
    """「二〇二六年」是年份，不是数量——分错的话它会被拿去 number 规则里查出处。"""
    nums = extract_numbers("二〇二六年发布", CFG)

    assert [(n.raw, n.kind) for n in nums] == [("二〇二六", "year")]


def test_a_chinese_year_with_a_unit_is_a_quantity() -> None:
    """带量词的四位数不是年份（与阿拉伯那条同一口径）。"""
    nums = extract_numbers("二〇二六万元", CFG)

    assert [n.kind for n in nums] == ["quantity"]


def test_mixed_text_yields_both_kinds() -> None:
    """阿拉伯与中文混排：两边都在，**顺序按各自出现的位置**。"""
    nums = extract_numbers("2026 年营收增长二十六%，达 35 亿", CFG)

    assert [n.raw for n in nums] == ["2026", "二十六", "35"]


def test_an_unreadable_chinese_numeral_reaches_the_checker_with_no_value() -> None:
    """解不出的也进检查面（value=None），上层照样会拿 raw 去卡原文里找。"""
    nums = extract_numbers("增长廿六%", CFG)

    assert [(n.raw, n.kind, n.value) for n in nums] == [("廿六", "quantity", None)]


# ───────────────────────── acceptance③：阿拉伯那条路逐字不变


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026 年发布", [("2026", "year")]),
        ("增长 26%", [("26", "quantity")]),
        ("1,234 万元", [("1,234", "quantity")]),
        ("3.14 倍", [("3.14", "quantity")]),
        ("没有数字", []),
        ("1998 与 2026 年", [("1998", "year"), ("2026", "year")]),
    ],
)
def test_the_arabic_path_is_unchanged(text: str, expected: list[tuple[str, str]]) -> None:
    """本卡**只加不改**：纯阿拉伯输入的输出逐条与改前相同。

    这些输入取自接地校验器既有用例的形状（年份 / 百分比 / 千分位 / 小数 / 空）。
    """
    assert [(n.raw, n.kind) for n in extract_numbers(text, CFG)] == expected


def test_a_number_at_the_very_end_is_read_correctly_now() -> None:
    """`FIX-01` 修好了——本条随之从「钉缺陷」翻成正面断言。

    ## 它此前是什么样

    原判据把**缺陷本身**钉住：断言「1998 与 2026」里末尾的 2026 被判成
    `quantity` 且 `is_percent=True`，并在 docstring 里写明
    「**这一条在那天被修好时会红，提醒那时的人来删它**」。

    根因是 `tail in _QTY_UNIT`——Python 里 `"" in "%％倍万亿千元＄$"` 是 **True**，
    而正文末尾的数字取到的 tail 正是空串。
    `BL-01` 当时的 acceptance③ 是「既有阿拉伯路径逐字不变」，所以没有顺手改，
    登记在 `docs/blocked/GROUNDING-EMPTY-TAIL.md`（`FIX-01` 已关闭）。

    `FIX-01` 补上 `tail != "" and ...` 之后本条当场变红，照那句话翻成了现在这样。
    **钉缺陷比留 TODO 强的地方就在这里：TODO 不会红，也不会告诉你怎么改。**
    """
    tail_num = extract_numbers("1998 与 2026", CFG)[-1]

    assert (tail_num.raw, tail_num.kind, tail_num.is_percent) == ("2026", "year", False)


def test_the_new_chinese_path_does_not_inherit_that_bug() -> None:
    """新写的这条路**没有**照抄那个写法：末尾的中文数字不会被当成百分数。

    照抄的诱惑是真实的——两处逻辑长得一模一样，复制过来最省事。
    """
    nums = extract_numbers("同比增长二十六", CFG)

    assert [(n.raw, n.is_percent) for n in nums] == [("二十六", False)]


def test_no_chinese_numeral_means_no_extra_work() -> None:
    """一句中文没有数字时，一条都不该多出来。"""
    assert extract_numbers("这份报告没有任何数字", CFG) == []
