"""FIX-05 · 语言与地区表单在 390px 横向溢出 48px。

## 单子猜的地方不是溢出的地方

单子写着「溢出的是表单那一行——三件套不换行」，并建议「`.locale` 那一行加
`flex-wrap` 即可（一行样式）」。**照着改会白改**：`.locale` 根本没有任何样式规则
（那些 `locale__*` 类名在 `globals.css` 与 `_ds` 里一条都查不到）。

逐元素量下来，越界的只有一个：

```
MAIN .app-shell__body   right=438  width=438   ← 越界的是它
SECTION .screen         right=414  width=390
SECTION .locale         right=414  width=390   ← 单子怀疑的这个，宽度正好是视口
```

## 算术能对上，所以不用猜

```css
.app-shell__body {
  inline-size: 100%;          /* = 390px */
  padding: var(--sp-5);       /* = 24px，且没有 border-box */
}
```

`content-box` 下内容盒 390 + 左右各 24 = **438**。单子实测的溢出量正是 48px。

**一个能对上小数点的算式，比一句「大概是没换行」值钱得多。**

## 那这不止一屏

`.app-shell__body` 是**所有屏**的容器。所以这条溢出十三屏全有，
只是此前只有 `/settings/locale` 被在 390px 下量过（`EYE-03` 只跑三屏、且没跑 mobile）。
本卡修的是那个容器；全量清点是 `FIX-06`。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CSS = REPO / "web" / "app" / "globals.css"
TICKET = REPO / "docs" / "blocked" / "LOCALE-FORM-OVERFLOWS-ON-MOBILE.md"
PROBE = REPO / "scripts" / "ui_probe.py"
PWPY = Path(r"C:\pwenv\Scripts\python.exe")
URL = os.environ.get("FLINT_WEB_BASE", "http://localhost:3000") + "/settings/locale"


def _rule(name: str) -> str:
    """取出一条 CSS 规则的声明块。**判的是规则本身，不是文件里有没有那个词。**"""
    css = CSS.read_text(encoding="utf-8")
    match = re.search(re.escape(name) + r"\s*\{([^}]*)\}", css)
    assert match, f"{name} 这条规则不见了"
    return match.group(1)


def _probe(theme: str) -> list[dict]:
    """真跑一次探针取 `scroll_width`。**NEVER 只断言样式类名在**（卡面 acceptance②）。

    探针不在项目依赖里（它住在 `C:\\pwenv`），也要真前端起着——
    两者缺一时 skip 并说清楚缺的是什么，**NEVER 当它通过**。
    """
    if not PWPY.exists():
        pytest.skip(f"取证解释器不在：{PWPY}（playwright 恒在项目外）")
    done = subprocess.run(
        [str(PWPY), str(PROBE), "--url", URL, "--theme", theme, "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, timeout=300, check=False)   # 非零退出码在下面逐种分诊
    if done.returncode == 3:
        pytest.skip("前端没起（localhost:3000）：这条要真栈才量得准")
    report = json.loads(done.stdout[done.stdout.index("{"):])
    if report.get("frontend_down"):
        pytest.skip("探针报前端没起")
    return list(report["pages"])


# ───────────────────────── acceptance①②：真实 scroll_width 不超视口


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_locale_screen_does_not_overflow_on_a_390px_viewport(theme: str) -> None:
    """390px 视口下 `scroll_width` 不超过视口宽（实测改前 438 > 390）。"""
    mobile = [s for s in _probe(theme) if s["viewport"] == "mobile"]

    assert mobile, "探针没跑 mobile 视口——那就等于没量"
    for screen in mobile:
        assert screen["scroll_width"] <= screen["viewport_width"], (
            f"{theme} 移动视口横向溢出 "
            f"{screen['scroll_width'] - screen['viewport_width']}px")
        assert screen["horizontal_overflow"] is False


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_desktop_viewport_does_not_regress(theme: str) -> None:
    """桌面视口不倒（卡面 acceptance③）：改窄屏最容易把宽屏改坏。"""
    desktop = [s for s in _probe(theme) if s["viewport"] == "desktop"]

    assert desktop, "探针没跑 desktop 视口"
    for screen in desktop:
        assert screen["scroll_width"] <= screen["viewport_width"], screen
        assert screen["console_error_count"] == 0, screen["console_errors"]


# ───────────────────────── 根因：算得出来的那一条


def test_the_container_counts_its_padding_inside_its_width() -> None:
    """`.app-shell__body` 用 `border-box`。

    改前 `inline-size: 100%` + `padding: var(--sp-5)`（24px）在 `content-box` 下
    是 390 + 48 = **438**——单子实测的溢出量正是 48px。
    """
    block = _rule(".app-shell__body")

    assert "border-box" in block, "还是 content-box：内容 100% 再加内边距必然越界"
    assert "inline-size: 100%" in block


def test_no_bare_pixel_value_was_introduced() -> None:
    """修法**没有新起一个裸像素或裸颜色**（`globals.css` 的既有纪律）。

    `box-sizing` 是盒模型口径，不是新的间距——换成写死一个 `width: 342px`
    才是那条纪律要拦的东西（那样每次改内边距都要有人回来重算一遍）。
    """
    block = _rule(".app-shell__body")

    assert not re.search(r":\s*\d+px", block), f"引入了裸像素：{block}"
    assert "var(--sp-5)" in block, "内边距不再走 token 了"


def test_the_fix_is_on_the_container_not_on_the_form() -> None:
    """**判在根因那一层**：修的是容器，不是单子怀疑的那一行表单。

    `.locale` 至今没有任何样式规则（它的宽度正好是视口）。
    往它上面加 `flex-wrap` 改不动 438 那个数——**照单子的猜想改会白改**。
    """
    css = CSS.read_text(encoding="utf-8")

    assert not re.search(r"^\.locale\s*\{", css, re.MULTILINE), (
        "给 .locale 加了样式：那不是溢出的来源，加了会让下一个人以为是")


# ───────────────────────── acceptance④：单子关掉


def test_the_ticket_is_closed_and_records_the_wrong_guess() -> None:
    """单子关掉，**并把「猜错了」写下来**。

    只写「已修复」的话，下一个人还会照那句「加 flex-wrap 即可」去改别处。
    """
    text = TICKET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:16])

    assert "**状态** closed" in head
    assert "FIX-05" in head
    assert "app-shell__body" in text, "没写真正的根因"
    assert "438" in text
