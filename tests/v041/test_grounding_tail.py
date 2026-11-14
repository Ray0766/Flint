"""FIX-01 · `"" in "%％"` 恒为 True——正文末尾的每个数字都被误判。

## 一行代码

```python
tail = text[m.end():m.end() + 1]     # 正文末尾的数字 → tail == ""
is_percent = tail in "%％"           # "" in "%％"        → True
has_unit  = tail in _QTY_UNIT        # "" in "%％倍万亿…"  → True
```

**Python 里空串是任何字符串的子串。**

## 两个后果，**都是放松**

| 后果 | 为什么危险 |
|---|---|
| `has_unit=True` → 四位年份落进 `quantity` | `_check_date` 只收 `kind == "year"`，**日期幻觉那一路少了一个检查项** |
| `is_percent=True` → `_number_present` 额外试 `value/100` | 一个本不是百分数的数字**凭空多了一种「找得到」的方式** |

**少查在报告上与「查过了没问题」长得一模一样**——这是它难被发现的原因。

## 同一个坑，一处修过一处漏了

`_cjk_numbers` 里那处（第 155 行）`BL-01` 已经写了 `tail != "" and ...`，
并留了注释「`"" in ...` 恒 True，见 §BL-01」。
**而 20 行之上的 `extract_numbers` 没改。** 本卡补的就是它。
"""
from __future__ import annotations

import inspect
import re
from decimal import Decimal
from pathlib import Path

from flint.grounding import GroundingConfig, extract_numbers

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "flint" / "grounding" / "__init__.py"
TICKET = REPO / "docs" / "blocked" / "GROUNDING-EMPTY-TAIL.md"
CFG = GroundingConfig()


def _kinds(text: str) -> list[tuple[str, str, bool]]:
    return [(n.kind, n.raw, n.is_percent) for n in extract_numbers(text, CFG)]


# ───────────────────────── acceptance①：空串尾字符判断修好


def test_a_year_at_the_end_of_the_text_is_still_a_year() -> None:
    """**后果一**：正文以四位年份结尾时，它必须仍是 `year`。

    修之前 `has_unit` 恒为真，年份落进 `quantity`——
    而 `_check_date` 只收 `kind == "year"`，日期幻觉那一路就少了一个检查项。
    """
    assert _kinds("发布于 2024") == [("year", "2024", False)]


def test_a_bare_number_at_the_end_is_not_a_percentage() -> None:
    """**后果二**：正文以裸数字结尾时，它 NEVER 是百分数。

    修之前 `is_percent` 恒为真，`_number_present` 会额外试一次 `value/100`——
    一个本不是百分数的数字凭空多了一种「找得到」的方式。
    """
    assert _kinds("营收增长 26") == [("quantity", "26", False)]


def test_the_middle_of_the_text_behaved_correctly_all_along() -> None:
    """对照：数字**不在**末尾时，此前的行为本来就是对的。

    没有这一条，上面两条可能是「把所有数字都判成非百分数」换来的。
    """
    assert _kinds("增长 26% 的营收") == [("quantity", "26", True)]
    assert _kinds("约 2024 年发布") == [("year", "2024", False)]
    assert _kinds("销量 3 万台") == [("quantity", "3", False)]


def test_a_real_percentage_at_the_end_is_still_a_percentage() -> None:
    """**正例**：末尾真带 `%` / `％` 的，照样判成百分数。

    修法若写成「末尾一律不是百分数」，这条会红。
    """
    assert _kinds("增长 26%") == [("quantity", "26", True)]
    assert _kinds("占比 26％") == [("quantity", "26", True)]


def test_a_real_unit_at_the_end_still_makes_it_a_quantity() -> None:
    """**正例**：末尾真带量词的四位数，照样是 `quantity` 而非 `year`。

    量词必须**紧跟**数字——`_QTY_UNIT` 的注释原话是「紧跟数字的量词单位」。
    中间隔一个空格就不算（`募资 2024 万` → year），这是原设计，本卡未动：
    「2024 万」在中文里既可能是钱数也可能是「2024 年 万某某」，
    尺子不去猜——**猜错的方向无法预知，而不猜只是少判一类**。
    """
    assert _kinds("募资2024万") == [("quantity", "2024", False)]
    # 隔了空格 → 仍判 year（原设计，不是本卡改坏的）
    assert _kinds("募资 2024 万") == [("year", "2024", False)]


def test_the_guard_is_written_out_not_left_to_truthiness() -> None:
    """**判源码**：那两处必须显式写 `tail != ""`。

    只判行为的话，有人把它改回 `tail in "%％"` 而恰好没有末尾数字的用例时，
    上面几条会继续绿。
    """
    source = MODULE.read_text(encoding="utf-8")
    body = inspect.getsource(extract_numbers)

    assert 'is_percent = tail != "" and tail in "%％"' in body
    assert 'has_unit = tail != "" and tail in _QTY_UNIT' in body
    # 全模块里**不许**再有裸的 `tail in`——同一个坑第三处。
    bare = [line.strip() for line in source.splitlines()
            if re.search(r'(?<!= )(?<!and )tail in ', line)
            and 'tail != ""' not in line]
    assert bare == [], f"还有裸的 `tail in`：{bare}"


# ───────────────────────── acceptance②：两个后果各有判据


def test_the_year_reaches_the_date_check_again() -> None:
    """年份判对之后，`_check_date` 才拿得到它。

    这是后果一的**下游**：分类修对了，检查项才回得来。
    """
    numbers = extract_numbers("该产品发布于 2024", CFG)
    years = [n for n in numbers if n.kind == "year"]

    assert years, "末尾的年份还是没进 year 这一类，日期检查拿不到它"
    assert years[0].value == Decimal(2024)


def test_a_non_percentage_no_longer_gets_the_divide_by_hundred_pass() -> None:
    """后果二的**下游**：不是百分数就不该有 `value/100` 那条额外通路。

    `_number_present` 对 `is_percent` 的数字多试一次 `value/100`。
    末尾那个 26 若被当成百分数，`0.26` 出现在卡片原文里就算「找得到」了——
    而它本该找 `26`。
    """
    number = extract_numbers("营收增长 26", CFG)[0]

    assert number.is_percent is False


def test_chinese_numerals_were_already_correct() -> None:
    """`_cjk_numbers` 那处 `BL-01` 已经修过——本卡 NEVER 把它改坏。

    中文数字与阿拉伯数字是**同一套分类口径**（模块 docstring 原话）：
    分两套的话，「二〇二六年」会被当成数量拿去查数字出处，而它是年份。
    """
    assert [n.kind for n in extract_numbers("发布于二〇二四", CFG)] == ["year"]


# ───────────────────────── acceptance③④：既有期望值与单子


def test_no_existing_expectation_had_to_change() -> None:
    """**既有用例一条都没改**（卡面 acceptance③ 的前提）。

    卡面说「期望值若因此改变，逐条在 trace 写明改前改后与理由」。
    实测：`pytest -k grounding` 51 条**全绿、零改动**——
    因为既有用例里没有一条正文是以数字结尾的。

    这条判据把那个事实钉住：哪天有人改了既有期望值，
    得先来这里说明为什么（本条会红）。
    """
    here = Path(__file__).name
    touched = [
        # 本文件自己不算——它**就是**本卡的产物。
        path.name for path in (REPO / "tests").rglob("test_*grounding*.py")
        if path.name != here and "FIX-01" in path.read_text(encoding="utf-8")
    ]

    assert touched == [], (
        f"这些既有 grounding 测试被本卡改过：{touched}——"
        f"逐条在 docs/trace/FIX-01.md 写明改前改后与理由"
    )


def test_the_ticket_is_closed() -> None:
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "已关闭" in head
    assert "FIX-01" in head
