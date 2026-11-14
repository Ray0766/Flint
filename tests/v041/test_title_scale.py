"""TITLE-01：②标题做大——屏头标题与品牌字各成一档。

## 实况

owner 2026-08-11：「标题做大」。

改前实测：`h1.screen__title` 是 `--fs-31`（**31px**），
`.app-shell__wordmark` 是 `--fs-20`（**20px**），
而且**1920 与 390 上一样大**——大屏上小得像个小标签，小屏上又挤。

## 改法：加档位，NEVER 在组件里写死 px

两档都写进 `_ds` 的排版 token（acceptance③ 逐字），用 `clamp` 随视口缩放：

```
--text-screen-title: clamp(24px, 2.6vw, 48px)
--text-wordmark:     clamp(20px, 1.6vw, 30px)
```

下界照卡面（24 / 20），上界照蓝本主标那一档（蓝本 h1 是 56px）。

**在组件里写死 px 的话，下一次调档没人找得到它**——
这也是本仓一路在治的同一件事：一个值只该有一处真相。

## 判据一律正向 + 实测

每条都是「MUST ≥ 多少 px」并带真浏览器量到的数。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PW_PYTHON = Path(r"C:\pwenv\Scripts\python.exe")
GLOBALS = REPO / "web" / "app" / "globals.css"

#: 卡面给的四条阈值。
MIN_TITLE_WIDE, MIN_WORDMARK_WIDE = 40.0, 28.0
MIN_TITLE_PHONE, MIN_WORDMARK_PHONE = 24.0, 20.0

_PROBE = r"""
import json
from playwright.sync_api import sync_playwright

OUT = {}
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for w, h in ((1920, 1080), (1440, 900), (390, 844)):
        page = b.new_page(viewport={"width": w, "height": h})
        page.goto("http://localhost:3000/plaza", wait_until="networkidle")
        page.wait_for_timeout(700)
        OUT[str(w)] = page.evaluate('''() => {
            const t = document.querySelector('h1.screen__title');
            const wm = document.querySelector('.app-shell__wordmark');
            return {
              title: t ? parseFloat(getComputedStyle(t).fontSize) : null,
              titleFamily: t ? getComputedStyle(t).fontFamily : null,
              wordmark: wm ? parseFloat(getComputedStyle(wm).fontSize) : null,
              titleTag: t ? t.tagName : null,
            };
        }''')
        page.close()
    b.close()
print(json.dumps(OUT, ensure_ascii=False))
"""


def _probe() -> dict[str, dict[str, object]]:
    if not PW_PYTHON.exists():
        pytest.skip("playwright 环境不在（它恒在项目外 C:\\pwenv）")
    done = subprocess.run(
        [str(PW_PYTHON), "-c", _PROBE], capture_output=True, text=True,
        check=False,  # 跑不起来要 skip 而不是抛——真栈没起是环境问题，不是判据失败
        encoding="utf-8", errors="replace", timeout=300)
    if done.returncode != 0:
        pytest.skip(f"真栈没起来（:3000）：{(done.stderr or '')[-300:]}")
    return dict(json.loads(done.stdout.strip().splitlines()[-1]))


@pytest.fixture(scope="module")
def sizes() -> dict[str, dict[str, object]]:
    return _probe()


# ───────────────────────── 一、大屏上真的大了


@pytest.mark.compose
def test_the_screen_title_is_big_on_a_desktop(
    sizes: dict[str, dict[str, object]],
) -> None:
    """1920 下 `h1.screen__title` MUST ≥ 40px（实测 48px，改前 31px）。"""
    got = float(sizes["1920"]["title"])

    assert got >= MIN_TITLE_WIDE, (
        f"1920 下屏头标题只有 {got:.0f}px，低于 {MIN_TITLE_WIDE:.0f}px——"
        f"「标题做大」没做到")


@pytest.mark.compose
def test_the_wordmark_is_big_on_a_desktop(
    sizes: dict[str, dict[str, object]],
) -> None:
    """1920 下品牌字 MUST ≥ 28px（实测 30px，改前 20px）。"""
    got = float(sizes["1920"]["wordmark"])

    assert got >= MIN_WORDMARK_WIDE, (
        f"1920 下品牌字只有 {got:.0f}px，低于 {MIN_WORDMARK_WIDE:.0f}px")


# ───────────────────────── 二、小屏上按比例缩，而不是缩没


@pytest.mark.compose
def test_it_scales_down_on_a_phone_without_getting_tiny(
    sizes: dict[str, dict[str, object]],
) -> None:
    """390 下两者 MUST ≥ 24px / 20px（实测 24 / 20）。

    「做大」不等于「到处都塞一个 48px」——390 上那样会把标题挤成三行。
    """
    title = float(sizes["390"]["title"])
    wordmark = float(sizes["390"]["wordmark"])

    assert title >= MIN_TITLE_PHONE, f"390 下标题只有 {title:.0f}px"
    assert wordmark >= MIN_WORDMARK_PHONE, f"390 下品牌字只有 {wordmark:.0f}px"


@pytest.mark.compose
def test_the_size_really_follows_the_viewport(
    sizes: dict[str, dict[str, object]],
) -> None:
    """**分级是真的**：1920 > 1440 > 390，逐级变小。

    改前三个视口上是同一个数（31px）——一条「≥40px」的判据
    在一个恒 48px 的实现上也会绿，而那个实现在手机上会挤爆。
    """
    wide = float(sizes["1920"]["title"])
    mid = float(sizes["1440"]["title"])
    phone = float(sizes["390"]["title"])

    assert wide > mid > phone, (
        f"字号没有随视口分级：1920={wide:.1f} 1440={mid:.1f} 390={phone:.1f}")


# ───────────────────────── 三、走 `_ds` 的档，NEVER 组件里写死


def test_the_two_sizes_are_tokens_in_the_design_system() -> None:
    """两档 MUST 写进 `_ds` 的排版 token（acceptance③ 逐字）。"""
    tokens = next((REPO / "web" / "public" / "_ds").glob("*/tokens/typography.css"))
    text = tokens.read_text(encoding="utf-8")

    assert "--text-screen-title" in text, "屏头标题那一档不在 _ds 里"
    assert "--text-wordmark" in text, "品牌字那一档不在 _ds 里"


def test_no_hardcoded_pixel_size_on_those_two() -> None:
    """**阴性对照**（acceptance④）：把字号改回原档或写死 px → 判据红。

    判的是源码：那两条规则里 MUST 用新档，NEVER 出现写死的 `font-size: NNpx`。
    实测判据能证明「今天够大」，这一条证明「它是从一处真相来的」——
    组件里写死一个 48px 也能让上面那些绿，而下一次调档没人找得到它。
    """
    # 先整段剥掉块注释：解释里正写着改前那个档的名字。
    css = re.sub(r"/\*.*?\*/", "", GLOBALS.read_text(encoding="utf-8"), flags=re.DOTALL)

    for selector, token in ((".screen__title", "--text-screen-title"),
                            (".anime-nav .app-shell__wordmark", "--text-wordmark")):
        block = css.split(selector + " {", 1)[1].split("}", 1)[0]
        assert f"var({token})" in block, f"{selector} 没用 {token}"
        assert not re.search(r"font-size:\s*\d+px", block), (
            f"{selector} 里写死了 px——下一次调档没人找得到它")


def test_the_title_is_still_a_real_heading(
    sizes: dict[str, dict[str, object]],
) -> None:
    """屏头标题仍是 `h1`——**做大的是字号，不是把它换成一个大 div**。

    换成 div 的话字号判据照样绿，而读屏软件失去了这一屏的标题。
    """
    assert sizes["1920"]["titleTag"] == "H1", (
        f"屏头标题不是 h1 了：{sizes['1920']['titleTag']}")


def test_the_title_keeps_the_display_face(
    sizes: dict[str, dict[str, object]],
) -> None:
    """标题仍走显示体（`--font-display`），字号变大不换字。"""
    family = str(sizes["1920"]["titleFamily"])

    assert "Smiley Sans" in family or "得意黑" in family, (
        f"标题不走显示体了：{family[:60]}")
