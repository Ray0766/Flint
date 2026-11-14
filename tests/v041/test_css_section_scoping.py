"""FIX-13：`globals.css` 的小节边界固化——判据只量自己那一段。

## 那把尺子错在哪

`UI-01` 的三条样式判据取的是「起点标记 → **文件尾**」，而 `globals.css` 是
**追加式**的：`DS-02` 追加了卡面版式、`PLAZA-01` 追加了堆叠与网格、
`CHAIN-03` 追加了主题两屏、`REGION-10` 追加了筛选器。

于是 **`UI-01` 那三条把后来每一段都当成自己的判**。
第 5 批就地收敛成「起点 → 下一条分隔线」；本卡把它固化。

## 固化 = 边界只有一处定义

改前**四份**判据各写一遍同一个切法，且都带着同一个魔数：

```python
end = body.find("/* ─────", 8)      # 那个 8 是「跳过自己这条分隔线」
```

四份抄件的后果不是重复劳动，而是**它们迟早不一致**——
而不一致时红的那一份看起来像「产品坏了」。
现在只有 `tools/css_sections.py` 一处。

## 本文件的重心是两条阴性对照

- 往 `UI-01` 段内插一处颜色字面量 → 那三条**必红**；
- 往**后来的**段插同样一处 → 那三条**必绿**（它们该由自己的判据管）。

第二条才是这张卡的由来：改前它是红的，而红得毫无道理。
"""
from __future__ import annotations

import re
import sys
from itertools import pairwise
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tools.css_sections import (
    SECTION_BREAK,
    bare_sizes,
    colour_literals,
    section_after,
    section_starts,
    tokens_used,
)

GLOBALS = REPO / "web" / "app" / "globals.css"
UI01_MARKER = "/* UI-01：按蓝本重做现有屏的样式面。"
TESTS = REPO / "tests" / "v041"
SHEET = REPO / "docs" / "blocked" / "UI01-RULER-JUDGES-EVERY-LATER-SECTION.md"


def _css() -> str:
    return GLOBALS.read_text(encoding="utf-8")


# ───────────────────────── 一、边界只有一处定义


def test_no_test_file_slices_the_css_by_hand_any_more() -> None:
    """四份抄件收成一处。

    判的是**魔数那一行**（`find("/* ─────", …)`）：留着它就是留着一份抄件，
    而抄件迟早与真相不一致——**不一致时红的那一份看起来像产品坏了**。
    """
    offenders = [
        f"{path.name}:{no}"
        for path in sorted(TESTS.glob("*.py"))
        if path.name != "test_css_section_scoping.py"
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if 'find("/* ─────"' in line or "find('/* ─────'" in line
    ]

    assert offenders == [], f"这些判据还在自己切 css：{offenders}"


def test_the_break_marker_lives_in_exactly_one_place() -> None:
    """分隔线那个字面量也只写一处。

    各写一遍的话，哪天分隔线换个画法（比如换成 `/* ====`），
    改了一处而另几处没改时，**那几处会静静地把整份 css 当成一段**。
    """
    copies = [
        f"{path.name}:{no}"
        for path in sorted(TESTS.glob("*.py"))
        if path.name != "test_css_section_scoping.py"
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if '"/* ─────' in line or "'/* ─────" in line
    ]

    assert copies == [], f"分隔线字面量被抄进了判据：{copies}"


# ───────────────────────── 二、小节真的分得开


def test_the_file_has_named_sections() -> None:
    """每条分隔线开一段，且段里说得出**自己是谁**（卡号或名字）。

    无名的段没法被自己的判据认领——那正是「后来每一段都归 UI-01 判」的土壤。
    """
    css = _css()
    starts = section_starts(css)

    assert len(starts) >= 5, f"分隔线太少（{len(starts)}），小节可能没分开"
    for start in starts:
        head = css[start:start + 400]
        assert re.search(r"[A-Z]{2,}[A-Z0-9-]*-\d{2}|[A-Z]{3,}-\d{2}", head), (
            f"这一段没写自己是谁：{head.splitlines()[0][:70]}"
        )


def test_the_sections_do_not_overlap_and_cover_the_file() -> None:
    """相邻两段首尾相接，合起来是整份文件——**中间不留没人管的缝**。

    留一条缝的话，写进缝里的样式**哪条判据都不管**，
    而它在屏上照样生效。
    """
    css = _css()
    starts = section_starts(css)
    bounds = [0, *starts, len(css)]
    pieces = [css[a:b] for a, b in pairwise(bounds)]

    assert "".join(pieces) == css, "小节切分把内容弄丢了或弄重了"
    assert all(pieces), "有一段是空的——两条分隔线贴在一起了"


def test_ui01_stops_at_the_first_break() -> None:
    """`UI-01` 那一段**到第一条分隔线为止**，NEVER 到文件尾。"""
    css = _css()
    section = section_after(css, UI01_MARKER)

    assert SECTION_BREAK not in section, "UI-01 段里包含了分隔线——它吃到了下一段"
    assert len(section) < len(css) // 2, (
        f"UI-01 段占了整份文件的一半以上（{len(section)}/{len(css)}）——多半又扫到尾了"
    )
    assert ".app-shell" in section, "UI-01 段里没有它自己的选择器，切错了"


def test_a_missing_marker_blows_up_instead_of_returning_everything() -> None:
    """**阴性对照**：起点标记找不到时抛，NEVER 悄悄返回全文。

    返回全文的话，判据会把整份 css 当成这一段判，而它看起来仍然是绿的
    （多半没有违规），直到某天别的段里出现一处违规，**红在一张不相干的卡上**。
    """
    with pytest.raises(ValueError, match="找不到小节起点标记"):
        section_after(_css(), "/* 这个标记不存在 */")


# ───────────────────────── 三、两条阴性对照（本卡的重心）


def _ui01() -> str:
    return section_after(_css(), UI01_MARKER)


def _later_section() -> str:
    """最后一条分隔线开的那一段——**后来追加的**那些之一。"""
    css = _css()
    return css[section_starts(css)[-1]:]


def test_injecting_a_colour_into_ui01_turns_it_red() -> None:
    """往 `UI-01` 段里插一处颜色字面量 → 那条判据必红。

    没有这一条，把 `colour_literals` 写成 `return []` 也能让全仓绿。
    """
    poisoned = _ui01() + "\n.injected { color: #1B2A2E; }\n"

    assert colour_literals(poisoned) == ["#1B2A2E"]


def test_injecting_the_same_colour_into_a_later_section_leaves_ui01_green() -> None:
    """**这一条就是这张卡的由来**。

    往后来的段里插同样一处，`UI-01` 那三条**必须仍然绿**——
    那一处该由**它自己那一段的判据**管。
    改前它们是红的，而红得毫无道理：谁都看不出「UI-01 的样式面」出了什么问题。
    """
    css = _css()
    tail = section_starts(css)[-1]
    poisoned_file = css[:tail] + css[tail:] + "\n.injected { color: #1B2A2E; }\n"

    section = section_after(poisoned_file, UI01_MARKER)

    assert colour_literals(section) == [], "后面那段的违规又算到 UI-01 头上了"
    assert bare_sizes(section) == [], "同上（字号/间距那条）"


def test_injecting_a_bare_size_into_ui01_turns_it_red() -> None:
    """字号/间距那条同理。**发丝线那条例外仍然放行**。"""
    assert bare_sizes(_ui01() + "\n.injected { font-size: 13px; }\n") == [
        ".injected { font-size: 13px; }"
    ]
    assert bare_sizes(_ui01() + "\n.injected { border: 1px solid var(--rule); }\n") == []


def test_a_size_inside_a_comment_is_not_an_offence() -> None:
    """**注释里的算式不算**。

    `FIX-05` 在 `.app-shell__body` 上加的注释里写着 `width: 342px`（那是反例），
    当场被判成「写死了间距」——**说明问题的那句话被当成犯下问题**。
    本仓栽过多次，所以剥注释这一步也固化在工具里。
    """
    assert bare_sizes(_ui01() + "\n/* 反例：width: 342px 会溢出 */\n") == []


# ───────────────────────── 四、三条判据的语义一字不动（acceptance④）


def test_the_three_rules_still_mean_what_they_meant() -> None:
    """零颜色字面量 / 零裸字号间距 / token 必须存在于 `_ds`——三条都还在，
    且**对 `UI-01` 那一段仍然是绿的**（本卡只改边界，不改规则）。
    """
    section = _ui01()

    assert colour_literals(section) == []
    assert bare_sizes(section) == []

    bundles = [p for p in (REPO / "web" / "public" / "_ds").iterdir() if p.is_dir()]
    assert len(bundles) == 1
    declared = set(re.findall(
        r"(--[a-z0-9-]+)\s*:",
        "".join(p.read_text(encoding="utf-8")
                for p in (bundles[0] / "tokens").glob("*.css"))))
    unknown = sorted(tokens_used(section) - declared)

    assert unknown == [], f"用了 _ds 里没有的 token：{unknown}"


# ───────────────────────── 五、单据关掉


def test_the_sheet_is_closed() -> None:
    text = SHEET.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:8] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据还开着：{state!r}"
    assert "FIX-13" in text
