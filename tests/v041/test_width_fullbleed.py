"""WIDTH-01：长文行长的排版 token 被当成了应用容器宽度。

## 根因

`--measure-longform: 34em`（≈476px）定义在 `_ds/.../tokens/typography.css:15`，
那是**长文一行最多多少字才好读**——一条排版事实。
而 `globals.css` 拿它当 `.app-shell__inner` 与 `.app-shell__body` 的 `max-inline-size`，
也就是**应用外壳有多宽**——一个布局决定。

两件事共用一个 token，于是：

| owner 的意见 | 这一处怎么造成的 |
|---|---|
| 「顶栏挤成三行」 | 9 个控件（6 导航 + 地区 + 主题 + 语言）在 476px 里放不下 |
| 「把这一块铺满整个屏幕」 | 卡片网格被收进 476px，一张 520px 的卡都放不下 |

**`--measure-longform` 一个字没改**——它对正文段落是对的。改的是**谁在用它**。

## 判据一律正向（本批 `positive_criteria`）

每条都是「这个元素 MUST 长成什么样」并带**实测数值**
（`getBoundingClientRect()` / computed style，playwright 真浏览器打 `:3000`）。

由来：`UI-01~11` 挂的四条禁止性判据全绿，而那一屏是个 4072px 的裸 `<ul><li>`——
**禁止性判据挡得住做错，挡不住没做**。

## 两个方向各断言一次

放宽外壳最容易顺手把正文也拉满，而一行 1440px 的中文正文读起来会不断丢行——
**那是把一个错换成另一个错**。所以：

| 屏 | MUST |
|---|---|
| 网格屏（广场） | 主体 ≥ 视口 × 0.9 |
| 长文屏（报告正文） | 正文仍 ≈ 34em，**NEVER 跟着变宽** |
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
GLOBALS = REPO / "web" / "app" / "globals.css"
PW_PYTHON = Path(r"C:\pwenv\Scripts\python.exe")
BASE = "http://localhost:3000"

#: 实测那一轮的数（2026-08-11，见 `docs/trace/WIDTH-01.md`）。
#: 判据用阈值而不是逐字相等——**换一台机器字体宽度会差几像素**，
#: 而本卡要守的是「铺满」，不是「刚好 1760」。
MIN_FILL_RATIO = 0.9

_PROBE = r"""
import json, sys
from playwright.sync_api import sync_playwright

OUT = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for url, kind in (("/plaza?region=CN", "grid"),
                      ("/deliverables/del-demo-fixture-report", "longform")):
        for w, h in ((1920, 1080), (1440, 900), (390, 844)):
            page = b.new_page(viewport={"width": w, "height": h})
            errors = []
            page.on("console", lambda m: errors.append(m.text)
                    if m.type == "error" else None)
            page.goto("http://localhost:3000" + url, wait_until="networkidle")
            m = page.evaluate('''() => {
                const body = document.querySelector('.app-shell__body');
                const inner = document.querySelector('.app-shell__inner');
                const lf = document.querySelector('.screen--longform .screen__body');
                return {
                  bodyW: body ? body.getBoundingClientRect().width : null,
                  innerW: inner ? inner.getBoundingClientRect().width : null,
                  lfW: lf ? lf.getBoundingClientRect().width : null,
                  vw: innerWidth,
                  scrollW: document.documentElement.scrollWidth,
                };
            }''')
            m.update(kind=kind, viewport=w, errors=errors)
            OUT.append(m)
            page.close()
    b.close()
print(json.dumps(OUT, ensure_ascii=False))
"""


def _measure() -> list[dict[str, object]]:
    """打真浏览器真栈量一轮。**NEVER 用组件快照冒充整屏**（本批 `real_browser`）。"""
    if not PW_PYTHON.exists():
        pytest.skip("playwright 环境不在（它恒在项目外 C:\\pwenv）")
    done = subprocess.run(
        [str(PW_PYTHON), "-c", _PROBE], capture_output=True, text=True,
        check=False,  # 跑不起来要 skip 而不是抛——真栈没起是环境问题，不是判据失败
        encoding="utf-8", errors="replace", timeout=300)
    if done.returncode != 0:
        pytest.skip(f"真栈没起来（:3000）：{(done.stderr or '')[-300:]}")
    return list(json.loads(done.stdout.strip().splitlines()[-1]))


@pytest.fixture(scope="module")
def measured() -> list[dict[str, object]]:
    return _measure()


# ───────────────────────── 一、网格屏 MUST 铺满


@pytest.mark.compose
@pytest.mark.parametrize("viewport", [1920, 1440])
def test_the_grid_screen_fills_the_viewport(
    measured: list[dict[str, object]], viewport: int,
) -> None:
    """**正向**：网格屏主体实测宽度 MUST ≥ 视口 × 0.9。

    实测（2026-08-11）：1920 → 1760px（0.92）· 1440 → 1392px（0.97）。
    改前两者都是 476px（0.25 / 0.33）。
    """
    row = next(r for r in measured
               if r["kind"] == "grid" and r["viewport"] == viewport)
    ratio = float(row["bodyW"]) / float(row["vw"])

    assert ratio >= MIN_FILL_RATIO, (
        f"{viewport} 视口下主体只有 {row['bodyW']:.0f}px = 视口的 {ratio:.2f}，"
        f"低于阈值 {MIN_FILL_RATIO}——「铺满整个屏幕」没做到")


@pytest.mark.compose
def test_the_narrow_viewport_has_no_horizontal_overflow(
    measured: list[dict[str, object]],
) -> None:
    """390 下 MUST **无横向溢出**。

    放宽容器最容易在窄屏上撑出横条——`--width-app-inset` 用
    `min(..., 100vw - 2*sp5)` 收回来，这一条量的就是它真的收住了。
    """
    for row in (r for r in measured if r["viewport"] == 390):
        assert float(row["scrollW"]) <= float(row["vw"]) + 1, (
            f"{row['kind']} 屏 390 下横向溢出："
            f"scrollWidth {row['scrollW']:.0f} > 视口 {row['vw']:.0f}")


@pytest.mark.compose
def test_the_top_bar_is_as_wide_as_the_body(
    measured: list[dict[str, object]],
) -> None:
    """顶栏与主体**同宽**——它们是同一个容器档。

    两者各用一个宽度的话，屏上会出现「顶栏比内容窄一截」的错位，
    而那正是 owner 说「挤成三行」时看到的东西。
    """
    for row in (r for r in measured if r["kind"] == "grid"):
        inner, body = float(row["innerW"]), float(row["bodyW"])
        # 顶栏含左右内边距，主体也含——两者的**外框**同宽
        assert abs(inner - body) <= 2 * 24 + 2, (
            f"{row['viewport']} 下顶栏 {inner:.0f}px 与主体 {body:.0f}px 差太多")


# ───────────────────────── 二、长文屏 MUST 仍然窄


@pytest.mark.compose
@pytest.mark.parametrize("viewport", [1920, 1440])
def test_the_longform_screen_keeps_the_reading_measure(
    measured: list[dict[str, object]], viewport: int,
) -> None:
    """**反方向**：报告正文 MUST 仍是 34em 阅读行长，NEVER 跟着铺满。

    实测：1920 与 1440 下都是 476px（= 34em × 14px）。
    让长文也铺满的话，一行会有 1760px——**把一个错换成另一个错**。
    """
    row = next(r for r in measured
               if r["kind"] == "longform" and r["viewport"] == viewport)

    assert row["lfW"] is not None, (
        "报告正文屏上没有 `.screen--longform`——那一屏没有声明自己是长文")
    width = float(row["lfW"])
    assert 400 <= width <= 560, (
        f"长文正文实测 {width:.0f}px，不在阅读行长附近（34em≈476px）")
    assert width < float(row["bodyW"]), (
        f"长文正文 {width:.0f}px 与外壳 {row['bodyW']:.0f}px 一样宽了——"
        f"「铺满」把正文也拉满了")


@pytest.mark.compose
def test_the_longform_screen_still_fits_a_phone(
    measured: list[dict[str, object]],
) -> None:
    """390 下长文正文按视口收窄（不是恒 476px 撑出横条）。"""
    row = next(r for r in measured
               if r["kind"] == "longform" and r["viewport"] == 390)

    assert float(row["lfW"]) <= float(row["vw"]), (
        f"390 下长文正文 {row['lfW']:.0f}px 比视口还宽")


# ───────────────────────── 三、两个 token 各自命名（本卡的产品）


def test_the_two_widths_are_two_tokens() -> None:
    """排版档与容器档**各自命名**，NEVER 共用一个。

    这一条是本卡真正的产品：数值可以再调，而「两件事两个名字」不能退。
    """
    tokens = next((REPO / "web" / "public" / "_ds").glob("*/tokens/spacing.css"))
    typography = next(
        (REPO / "web" / "public" / "_ds").glob("*/tokens/typography.css"))

    assert "--width-app" in tokens.read_text(encoding="utf-8"), "容器档不在"
    assert "--measure-longform" in typography.read_text(encoding="utf-8")


def test_the_typography_token_was_not_touched() -> None:
    """`--measure-longform` **一个字没改**——它对正文段落是对的。

    本卡改的是「谁在用它」。改它的话，报告正文会跟着一起变宽，
    而那与本卡要治的事没有关系。
    """
    typography = next(
        (REPO / "web" / "public" / "_ds").glob("*/tokens/typography.css"))

    assert "--measure-longform:34em;" in typography.read_text(encoding="utf-8"), (
        "有人动了长文行长那个 token")


def test_the_shell_no_longer_uses_the_typography_token() -> None:
    """**阴性对照**（acceptance④）：外壳的容器宽度改回 `--measure-longform` → 红。

    造法是判源码：外壳那两条规则里 NEVER 再出现那个排版 token。
    改回去的话上面那些实测判据会全部红，而这一条**先一步说清是哪一处改回去了**——
    「主体只有 476px」这句话对排障没有用，「外壳又在用长文行长」才有。
    """
    # **先把块注释整段剥掉再扫**：改动旁边那段注释本来就要把旧 token 的名字
    # 引出来说明它为什么被换掉，而一条只认字面的判据会把那句解释当成违规本身。
    # 按行首 `/*` 剥不够——CSS 的块注释可以横跨多行且不以 `*` 起头。
    # （本仓这一坑第九次，所以这里连怎么剥都写下来。）
    css = re.sub(r"/\*.*?\*/", "", GLOBALS.read_text(encoding="utf-8"), flags=re.DOTALL)
    for selector in (".app-shell__inner", ".app-shell__body"):
        code = css.split(selector + " {", 1)[1].split("}", 1)[0]
        assert "--measure-longform" not in code, (
            f"{selector} 又在用长文行长那个排版 token 当容器宽度了——"
            f"那正是 WIDTH-01 的根因")
        assert "--width-app-inset" in code, f"{selector} 没用容器宽度档"


def test_the_breakout_hack_is_gone() -> None:
    """`PLAZA-01` 那个负外边距 hack **退役了**。

    它当初是为了从 34em 里挣出来；外壳放宽之后再叠一层负外边距
    会真的撑出横向滚动条。
    """
    css = GLOBALS.read_text(encoding="utf-8")
    block = css.split(".screen:has(.plaza),", 1)[1].split("}", 1)[0]

    assert "margin-inline: calc((100%" not in block, "负外边距 hack 还在"
    assert "display: block" in block, (
        "整条规则被删了——那两屏会退回 flex 列，症状与它改前几乎一样")
