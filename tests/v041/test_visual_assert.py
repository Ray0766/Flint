"""EYE-02：视觉判据可执行化——「用户看不看得见」变成机器可验。

## 三条判据的由来

终检 F-09：`BlockView.tsx` 那个争议记号改成了 `<span data-testid="disputed-mark" />`，
`.mark--disputed` 全仓**零 CSS**、`web/` 下**一个样式表都没有**、`_ds` 根本没被应用加载——
于是它是一个**没有文字内容、没有任何样式的空行内元素，占 0 像素**。
守它的断言 `querySelector(...) !== null` 照样通过。

三条判据分别挡三种「看不见」：

1. **渲染尺寸非零**——DOM 里有 ≠ 屏幕上有（F-09 的原形）；
2. **对比度达阈值**——画出来了 ≠ 看得清（灰底灰字与不画没有区别）；
3. **明暗两主题都满足前两条**——只在深色下看得见的记号，浅色用户就是看不见。

## 判据与浏览器解耦（acceptance③）

判定是纯函数：吃一份 `VisualObservation`（尺寸 + 前景色 + 背景色），吐 `Verdict`。
量测是另一件事，由驱动做——默认驱动用 `C:\\pwenv` 的 playwright 打开一段**静态 HTML 片段**
（`data:` URL，不起前端），测试则注入一个假驱动，于是这份验收在项目 `.venv` 里也能跑。

对比度公式不自己发明：照 WCAG 2.x 的相对亮度与对比度定义写，并用**规范自带的参照值**
校准（纯黑/纯白 = 21:1，AA 正文阈值 4.5）。这类通用问题 NEVER 靠自己造一套数。
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from tools import visual_assert as va

REPO = Path(__file__).resolve().parents[2]


def _obs(**over: object) -> va.VisualObservation:
    base = {
        "selector": ".mark", "present": True, "width": 12.0, "height": 12.0,
        "color": "rgb(0, 0, 0)", "background_color": "rgb(255, 255, 255)", "theme": "light",
    }
    base.update(over)
    return va.VisualObservation(**base)  # type: ignore[arg-type]


# ───────────────────────── 判据①：渲染尺寸非零


def test_a_zero_sized_element_is_red_and_says_why() -> None:
    """acceptance②（阴性对照）：0×0 的空 span 判红——F-09 就是这种。"""
    verdict = va.judge_rendered_size(_obs(width=0.0, height=0.0))

    assert verdict.ok is False
    assert "0" in verdict.detail
    assert verdict.criterion == "rendered-size"


def test_an_element_with_a_real_box_is_let_through() -> None:
    """acceptance②（正例）：正常元素放行——见谁都报红的尺子同样量不出东西。"""
    assert va.judge_rendered_size(_obs()).ok is True


def test_one_zero_dimension_is_enough_to_be_invisible() -> None:
    """宽或高任一为 0 就看不见：12×0 与 0×12 都得红。"""
    assert va.judge_rendered_size(_obs(width=12.0, height=0.0)).ok is False
    assert va.judge_rendered_size(_obs(width=0.0, height=12.0)).ok is False


def test_a_missing_element_is_red_with_a_different_message() -> None:
    """「找不到」与「找到了但 0×0」是两回事：前者查渲染，后者查样式。"""
    missing = va.judge_rendered_size(_obs(present=False, width=0.0, height=0.0))

    assert missing.ok is False
    assert "找不到" in missing.detail


# ───────────────────────── 判据②：对比度


def test_contrast_matches_the_wcag_reference_values() -> None:
    """公式对齐 WCAG 参照值：纯黑/纯白 = 21:1，自己对自己 = 1:1。

    这两个值是规范里写死的，用它们校准比自己构造几组颜色可靠——
    通用问题照权威口径，NEVER 自己发明一套。
    """
    black, white = (0, 0, 0), (255, 255, 255)

    assert math.isclose(va.contrast_ratio(black, white), 21.0, rel_tol=1e-9)
    assert math.isclose(va.contrast_ratio(white, black), 21.0, rel_tol=1e-9)
    assert math.isclose(va.contrast_ratio(white, white), 1.0, rel_tol=1e-9)


def test_the_aa_threshold_sits_where_wcag_puts_it() -> None:
    """AA 正文阈值 4.5:1（WCAG SC 1.4.3）。`#777` 白底约 4.48——**在线下方**。

    这个灰是常被当成「够用」的那一档，实际差一点点。判据要能把它判红。
    """
    assert va.AA_NORMAL_TEXT == 4.5
    ratio = va.contrast_ratio(va.parse_color("#777777"), (255, 255, 255))

    assert 4.4 < ratio < 4.5
    assert va.judge_contrast(_obs(color="#777777")).ok is False


def test_black_on_white_passes_the_threshold() -> None:
    verdict = va.judge_contrast(_obs())

    assert verdict.ok is True
    assert "21" in verdict.detail


def test_a_transparent_background_is_red_not_assumed_white() -> None:
    """背景透明时**报红**，NEVER 当成白底算。

    当成白底会在深色主题下给出一片假绿：真背景是深色，而算出来的是「黑字白底 21:1」。
    """
    verdict = va.judge_contrast(_obs(background_color="rgba(0, 0, 0, 0)"))

    assert verdict.ok is False
    assert "透明" in verdict.detail


def test_color_parsing_covers_the_shapes_a_browser_returns() -> None:
    """`getComputedStyle` 给的是 `rgb()` / `rgba()`，样式表里写的是 `#rgb` / `#rrggbb`。"""
    assert va.parse_color("rgb(17, 34, 51)") == (17, 34, 51)
    assert va.parse_color("rgba(17, 34, 51, 0.5)") == (17, 34, 51)
    assert va.parse_color("#123") == (17, 34, 51)
    assert va.parse_color("#112233") == (17, 34, 51)
    with pytest.raises(ValueError, match="认不出的颜色"):
        va.parse_color("chartreuse-ish")


# ───────────────────────── 判据③：两主题都要满足


def test_both_themes_must_pass_and_the_failing_theme_is_named() -> None:
    """只在深色下看得见的记号，浅色用户就是看不见——必须红且**点名是哪个主题**。"""
    verdicts = va.judge_both_themes({
        "dark": _obs(theme="dark", color="rgb(255,255,255)", background_color="rgb(0,0,0)"),
        "light": _obs(theme="light", color="rgb(230,230,230)"),
    })

    failed = [v for v in verdicts if not v.ok]
    assert failed, "浅色下 230 灰白底应当判红"
    assert any("light" in v.detail for v in failed)
    assert all("dark" not in v.detail for v in failed)


def test_both_themes_green_when_both_are_really_fine() -> None:
    verdicts = va.judge_both_themes({
        "dark": _obs(theme="dark", color="rgb(255,255,255)", background_color="rgb(0,0,0)"),
        "light": _obs(theme="light"),
    })

    assert [v.ok for v in verdicts] == [True] * len(verdicts)


def test_a_missing_theme_is_red_not_skipped() -> None:
    """少给一个主题时报红，NEVER 「没量到就算过」。"""
    verdicts = va.judge_both_themes({"dark": _obs(theme="dark", color="rgb(255,255,255)",
                                                  background_color="rgb(0,0,0)")})

    assert any(not v.ok and "light" in v.detail for v in verdicts)


# ───────────────────────── acceptance③：对静态片段跑，驱动可注入


def test_a_static_fragment_can_be_judged_without_the_front_end() -> None:
    """整条链（片段 → 量测 → 判定）用注入的假驱动跑通，不起前端、不装 playwright。

    真驱动（`C:\\pwenv` 的 playwright 打开 `data:` URL）的实跑输出在 docs/trace/EYE-02.md，
    这里验的是**判据面**能离线闭环——否则它进不了 CI 的离线部分。
    """
    fragment = '<span class="mark"></span>'
    canned = {
        ("dark", ".mark"): _obs(theme="dark", width=0.0, height=0.0,
                                color="rgb(255,255,255)", background_color="rgb(0,0,0)"),
        ("light", ".mark"): _obs(theme="light", width=0.0, height=0.0),
    }

    report = va.check_fragment(
        fragment, ".mark", themes=("dark", "light"),
        measurer=lambda html, selector, theme: canned[(theme, selector)],
    )

    assert report["ok"] is False
    assert [v["criterion"] for v in report["verdicts"] if not v["ok"]][:2] == [
        "rendered-size", "rendered-size",
    ]


def test_the_same_chain_is_green_for_a_real_looking_element() -> None:
    canned = {
        ("dark", ".mark"): _obs(theme="dark", color="rgb(255,255,255)",
                                background_color="rgb(0,0,0)"),
        ("light", ".mark"): _obs(theme="light"),
    }

    report = va.check_fragment(
        '<span class="mark">争议</span>', ".mark", themes=("dark", "light"),
        measurer=lambda html, selector, theme: canned[(theme, selector)],
    )

    assert report["ok"] is True
    assert report["schema"] == va.SCHEMA


def test_playwright_stays_out_of_the_dependency_files() -> None:
    """真驱动用 `C:\\pwenv`：三处依赖清单里 playwright 命中恒为 0（与 EYE-01 同一条线）。"""
    for rel in ("requirements.lock", "pyproject.toml", "web/package.json"):
        assert "playwright" not in (REPO / rel).read_text(encoding="utf-8").lower()
