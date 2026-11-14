"""EYE-02 / 终检 F-09：视觉判据可执行化——「用户看不看得见」变成机器可验。

用法（判定是纯函数，量测要浏览器，故真跑用隔离环境的解释器）：
    C:\\pwenv\\Scripts\\python.exe tools/visual_assert.py --html-file frag.html --selector .mark
    C:\\pwenv\\Scripts\\python.exe tools/visual_assert.py --html '<span class="mark"></span>' \\
        --selector .mark --min-contrast 4.5
退出码 0 = 判据在两个主题下全过；1 = 有判据不满足（逐条点名）；2 = playwright 不在当前解释器。

## F-09：DOM 里有 ≠ 屏幕上有

`BlockView.tsx` 的争议记号改成了 `<span data-testid="disputed-mark" />`，而
`.mark--disputed` 全仓**零 CSS**、`web/` 下一个样式表都没有、`_ds` 根本没被应用加载——
那是一个没有文字内容、没有任何样式的空行内元素，**占 0 像素**。
守它的断言 `querySelector(...) !== null` 照样通过：改之前用户看得见一个 `⚠`，
改之后**什么都看不见**，而测试全绿。

## 四条判据

0. `theme-switches`（**前置**，DARK-02 补）：受主题支配的元素，明暗两次量到的
   **颜色对必须不同**——两次相同即判红。先回答「这两次量的是不是两个东西」，
   再谈看得见与看得清；
1. `rendered-size`：元素存在**且渲染宽高均 >0**（F-09 的原形）；
2. `contrast`：元素前景与**有效背景**的对比度 ≥ 阈值（画出来了 ≠ 看得清）；
3. 后两条在**明暗两主题下都要成立**（只在深色下看得见的记号，浅色用户就是看不见）。

## 判据 0 是补上去的，补之前判据 3 在量同一个东西

`docs/blocked/EYE-02-TWO-THEMES-MEASURES-ONE.md` 记的实测：K6-01 量入口按钮，
两个主题量出一位不差的同一组数，而报告 `ok=True`。它**不会误判**（两次都真的过线），
但它**证不到**它字面上声称的那件事：换主题之后仍然看得见。
DARK-01 把 `_ds` 的暗色板做出来之后这条洞才量得出来，DARK-02 把它关上。

`theme_sensitive` 默认 **True**：忘了打开时得到的是红，不是绿。默认关闭的话，
这条洞会以「谁都没想起来传那个参数」的形式无声回来。确有不随主题变的元素
（固定品牌色一类）显式传 `theme_sensitive=False`，**报告里留痕**——
不留痕的话，一份 `ok=True` 读不出它是验过了还是那条判据被关了。

## 两条不肯含糊的地方

- **背景透明时报红，NEVER 当成白底算**。当成白底会在深色主题下给出一片假绿：
  真背景是深色，而算出来的是「黑字白底 21:1」。取不到有效背景色是**量测的问题**，
  它该被报出来，不该被一个默认值盖住。
- **少一个主题算红**，不算「没量到就跳过」。跳过的那一半正是最可能坏的那一半。

## 对比度照 WCAG，不自己发明

相对亮度与对比度按 WCAG 2.x 定义实现（sRGB 线性化 → 0.2126/0.7152/0.0722 加权 →
`(L1+0.05)/(L2+0.05)`）。校准用规范自带的参照值：纯黑/纯白 = 21:1，AA 正文阈值 4.5:1
（SC 1.4.3）、大字号 3:1。**通用问题照权威口径**，自造一套数没人能复核。

## 判据与浏览器解耦（可进 CI 离线部分）

判定吃一份 `VisualObservation`（尺寸 + 前景色 + 背景色），与浏览器无关。
量测由驱动做：默认驱动用 playwright 打开一段**静态 HTML 片段**（`data:` URL，不起前端），
`check_fragment(..., measurer=...)` 可注入假驱动，于是判据面在没有 playwright 的解释器里
也能被完整验证。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "visual-assert/1"

# WCAG 2.x SC 1.4.3。数字写在这里只有一处，NEVER 散落到各处判据里。
AA_NORMAL_TEXT = 4.5
AA_LARGE_TEXT = 3.0

THEMES = ("dark", "light")

THEME_SWITCH = "theme-switches"

_RGB_RE = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)")


@dataclass(frozen=True)
class VisualObservation:
    """一个元素在**一个主题下**的量测结果。颜色用浏览器给的原样字符串。"""

    selector: str
    present: bool
    width: float
    height: float
    color: str
    background_color: str
    theme: str


@dataclass(frozen=True)
class Verdict:
    ok: bool
    criterion: str
    detail: str


def parse_color(text: str) -> tuple[int, int, int]:
    """`rgb()` / `rgba()` / `#rgb` / `#rrggbb` → (r, g, b)。认不出就抛。

    认不出的颜色 NEVER 猜一个默认值：猜出来的对比度是个看起来很像真的假数。
    """
    value = text.strip()
    match = _RGB_RE.fullmatch(value)
    if match:
        return (int(float(match.group(1))), int(float(match.group(2))), int(float(match.group(3))))
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) == 3:
            return tuple(int(c * 2, 16) for c in digits)  # type: ignore[return-value]
        if len(digits) == 6:
            return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
    raise ValueError(f"认不出的颜色 {text!r}：只认 rgb() / rgba() / #rgb / #rrggbb")


def is_transparent(text: str) -> bool:
    """alpha 为 0 或关键字 transparent —— 这时候「背景色」不是真的背景。"""
    value = text.strip().lower()
    if value in ("transparent", ""):
        return True
    match = _RGB_RE.fullmatch(value)
    return bool(match and match.group(4) is not None and float(match.group(4)) == 0)


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.x 相对亮度。"""
    def channel(raw: int) -> float:
        c = raw / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """WCAG 2.x 对比度：纯黑/纯白 = 21:1，自己对自己 = 1:1。"""
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def judge_rendered_size(obs: VisualObservation) -> Verdict:
    """判据①：存在且渲染宽高均 >0。"""
    if not obs.present:
        return Verdict(False, "rendered-size",
                       f"[{obs.theme}] 找不到 {obs.selector}——它根本没被渲染出来")
    if obs.width > 0 and obs.height > 0:
        return Verdict(True, "rendered-size",
                       f"[{obs.theme}] {obs.selector} 渲染尺寸 {obs.width}×{obs.height}")
    return Verdict(False, "rendered-size",
                   f"[{obs.theme}] {obs.selector} 在 DOM 里，渲染尺寸 "
                   f"{obs.width}×{obs.height}——用户看不见它")


def judge_contrast(obs: VisualObservation, threshold: float = AA_NORMAL_TEXT) -> Verdict:
    """判据②：前景与有效背景的对比度 ≥ 阈值。"""
    if not obs.present:
        return Verdict(False, "contrast", f"[{obs.theme}] 找不到 {obs.selector}")
    if is_transparent(obs.background_color):
        return Verdict(False, "contrast",
                       f"[{obs.theme}] {obs.selector} 的背景是透明的，取不到有效背景色——"
                       "对比度无从算起，NEVER 拿白底顶上（深色主题下那是一片假绿）")
    try:
        ratio = contrast_ratio(parse_color(obs.color), parse_color(obs.background_color))
    except ValueError as err:
        return Verdict(False, "contrast", f"[{obs.theme}] {err}")
    ok = ratio >= threshold
    return Verdict(ok, "contrast",
                   f"[{obs.theme}] {obs.selector} 对比度 {ratio:.2f}:1 "
                   f"{'≥' if ok else '<'} 阈值 {threshold}")


def observed_palette(obs: VisualObservation) -> tuple[object, object]:
    """把一次量测归一成「前景 / 背景」颜色对，用于比较两个主题量到的是不是同一组。

    归一到 RGB **是判据的一部分**：按原始字符串比的话，`#F7F8F3` 与
    `rgb(247, 248, 243)` 会被当成「换了」——那等于把假绿换了个写法留下来。
    认不出的颜色留原样（小写去空白），它照样参与比较，NEVER 猜一个值顶上。
    """
    def one(text: str) -> object:
        try:
            return parse_color(text)
        except ValueError:
            return text.strip().lower()

    return (one(obs.color), one(obs.background_color))


def judge_theme_switch(by_theme: dict[str, VisualObservation]) -> Verdict:
    """判据 0（前置）：明暗两次量到的颜色对必须不同——两次相同即判红。

    尺寸不参与比较：调色板换的是颜色。把一像素的布局抖动当成「主题生效了」，
    就会把一个根本没有暗色规则的元素放行，而那正是这条判据要挡的。
    """
    measured = {theme: obs for theme, obs in by_theme.items() if theme in THEMES}
    if len(measured) < len(THEMES):
        missing = [t for t in THEMES if t not in measured]
        return Verdict(False, THEME_SWITCH,
                       f"只量到 {sorted(measured)}，缺 {missing}——"
                       "少于两个主题证不出切换，NEVER「没量到就算过」")

    absent = [theme for theme, obs in measured.items() if not obs.present]
    if absent:
        return Verdict(False, THEME_SWITCH,
                       f"{sorted(absent)} 里找不到元素——它没渲染出来时，"
                       "「颜色没变」是个无意义的结论")

    palettes = {theme: observed_palette(obs) for theme, obs in measured.items()}
    unparsed = sorted(
        theme for theme, pair in palettes.items() if any(isinstance(v, str) for v in pair)
    )
    if unparsed:
        return Verdict(False, THEME_SWITCH,
                       f"{unparsed} 量到的颜色认不出来，比不了："
                       + "；".join(f"[{t}] {measured[t].color} on "
                                   f"{measured[t].background_color}" for t in unparsed))

    shown = "；".join(f"[{t}] {measured[t].color} on {measured[t].background_color}"
                     for t in sorted(measured))
    if len({tuple(pair) for pair in palettes.values()}) == 1:
        return Verdict(False, THEME_SWITCH,
                       f"{next(iter(measured.values())).selector} 在两个主题下量到同一组颜色"
                       f"（{shown}）——这两次量的是同一个东西，判据证不到「换主题之后仍然看得见」")
    return Verdict(True, THEME_SWITCH,
                   f"{next(iter(measured.values())).selector} 两个主题量到不同颜色（{shown}）")


def judge_both_themes(
    by_theme: dict[str, VisualObservation], threshold: float = AA_NORMAL_TEXT,
    *, theme_sensitive: bool = True,
) -> list[Verdict]:
    """判据③：明暗两主题都要满足前两条。缺一个主题算红。

    `theme_sensitive` 为真（默认）时，先追加前置的 `theme-switches`。
    """
    verdicts: list[Verdict] = []
    if theme_sensitive:
        verdicts.append(judge_theme_switch(by_theme))
    for theme in THEMES:
        obs = by_theme.get(theme)
        if obs is None:
            verdicts.append(Verdict(False, "both-themes",
                                    f"没有量到 {theme} 主题——少量的那一半正是最可能坏的那一半"))
            continue
        verdicts.append(judge_rendered_size(obs))
        verdicts.append(judge_contrast(obs, threshold))
    return verdicts


Measurer = Callable[[str, str, str], VisualObservation]


def _playwright_measurer(html: str, selector: str, theme: str) -> VisualObservation:
    """默认驱动：用 playwright 打开一段静态片段（`data:` URL），量一个元素。

    **不起前端**——片段直接进浏览器。真背景色沿祖先链上溯到第一个非透明的，
    因为元素自己的背景通常是 transparent，而用户看到的是祖先那层。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("playwright 不在当前解释器里：请用 C:\\pwenv\\Scripts\\python.exe 跑本文件"
              "（NEVER 装进项目 .venv）", file=sys.stderr)
        raise SystemExit(2) from None

    page_html = f"<!doctype html><meta charset='utf-8'><body>{html}</body>"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(color_scheme=theme)
        page = ctx.new_page()
        page.set_content(page_html)
        found = page.query_selector(selector)
        box = found.bounding_box() if found is not None else None
        colors = page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const fg = getComputedStyle(el).color;
                let node = el, bg = 'rgba(0, 0, 0, 0)';
                while (node) {
                    const c = getComputedStyle(node).backgroundColor;
                    if (c && !/rgba\\(.*,\\s*0\\)$/.test(c) && c !== 'transparent') { bg = c; break; }
                    node = node.parentElement;
                }
                return {fg, bg};
            }""",
            selector,
        )
        browser.close()

    return VisualObservation(
        selector=selector, present=found is not None,
        width=float(box["width"]) if box else 0.0,
        height=float(box["height"]) if box else 0.0,
        color=(colors or {}).get("fg", ""), background_color=(colors or {}).get("bg", ""),
        theme=theme,
    )


def check_fragment(
    html: str, selector: str, *, themes: tuple[str, ...] = THEMES,
    threshold: float = AA_NORMAL_TEXT, measurer: Measurer | None = None,
    theme_sensitive: bool = True,
) -> dict[str, Any]:
    """整条链：静态片段 → 逐主题量测 → 四条判据 → 结构化报告。

    `theme_sensitive` 恒写进报告：关掉过的报告与没关过的报告，读的人分得出来。
    """
    measure = measurer or _playwright_measurer
    by_theme = {theme: measure(html, selector, theme) for theme in themes}
    verdicts = judge_both_themes(by_theme, threshold, theme_sensitive=theme_sensitive)
    return {
        "schema": SCHEMA,
        "selector": selector,
        "threshold": threshold,
        "theme_sensitive": theme_sensitive,
        "observations": {theme: obs.__dict__ for theme, obs in by_theme.items()},
        "verdicts": [v.__dict__ for v in verdicts],
        "ok": all(v.ok for v in verdicts),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="视觉判据：看得见 / 看得清 / 两个主题都行")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--html", help="要判的 HTML 片段")
    src.add_argument("--html-file", help="要判的 HTML 片段文件")
    ap.add_argument("--selector", required=True)
    ap.add_argument("--min-contrast", type=float, default=AA_NORMAL_TEXT)
    ap.add_argument("--theme-agnostic", action="store_true",
                    help="关掉前置的 theme-switches：只给确实不随主题变的元素用")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    html = args.html if args.html else Path(args.html_file).read_text(encoding="utf-8")
    report = check_fragment(html, args.selector, threshold=args.min_contrast,
                            theme_sensitive=not args.theme_agnostic)

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for row in report["verdicts"]:
            print(f"  {'✓' if row['ok'] else '✗'} {row['criterion']} —— {row['detail']}")
    if report["ok"]:
        return 0
    failed = [row["detail"] for row in report["verdicts"] if not row["ok"]]
    print(f"判据不满足 {len(failed)} 条：" + "；".join(failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
