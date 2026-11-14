"""PAL-03 取证：换板之后重拍——广场六张 + 屏上量到的颜色 == token 里的值。

跑法：`C:\\pwenv\\Scripts\\python.exe tools/ui_probe_palette.py`

产出：
  `.ui-probe/eye04/plaza-{视口}-{主题}.png` + `report.json`（**重拍，覆盖旧的**）
  `.ui-probe/palette/onscreen.json`（屏上量到的颜色 vs `tokens/colors.css` 声明）
  `.ui-probe/palette/before/plaza-1920x1080-light.png`（换板前那张，`PAL-03` 开跑时拷下来的）

## 视口矩阵**复用既有的**（三视口 × 两主题）

`EYE-04` 那份产物的键就是 `1920-light` … `390-dark`，本脚本照它写回去——
另起一套的话会给出两组数，而那时没人知道该信哪一组。

## 判据在测试里，这里只量

`tests/v041/test_palette_onscreen.py` 读 `onscreen.json`：
`getComputedStyle(body).backgroundColor` 归一到 rgb 之后 == `--paper` 的声明值，
且明暗两次量到的**不同**。这里不判，只把数与图一起落盘——
只有图的话，下一个人无从判断它当时算不算合格。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from playwright.sync_api import sync_playwright

REPO = pathlib.Path(".")
EYE04 = REPO / ".ui-probe" / "eye04"
OUT = REPO / ".ui-probe" / "palette"
COLORS = (REPO / "web" / "public" / "_ds"
          / "flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724"
          / "tokens" / "colors.css")
URL = "http://localhost:3000/plaza"
VIEWPORTS = ((1920, 1080), (1440, 900), (390, 844))
THEMES = ("light", "dark")

#: `EYE-04` 那四条老线，一条不放宽。
MEASURE = """() => {
  // 药丸条的选择器**照屏上真实的 DOM**：链接是 `.app-shell__nav-link`，
  // 它们的容器是 `nav.anime-nav`（`NAV-ANIME-01` 之后的形状）。
  // 第一版按记忆写了 `.app-shell__nav`，量到 0 个链接——于是「顶栏是不是一行」
  // 这条判据拿一个空数组去判，恒红。**红的是探针，不是屏。**
  const links = [...document.querySelectorAll('.app-shell__nav-link')];
  const nav = links[0] ? links[0].closest('nav') : document.querySelector('nav');
  const body = document.querySelector('.app-shell__body');
  const style = getComputedStyle(document.body);
  const navBox = nav ? nav.getBoundingClientRect() : null;
  return {
    oneRow: links.length > 0 && new Set(links.map(a => a.offsetTop)).size === 1,
    tops: [...new Set(links.map(a => a.offsetTop))],
    // 「药丸」在宽屏是 9999px 的全圆角；390 折行之后是 24px 的圆角条
    // （`WB-01` 修 390 溢出时那三处配套之一）。两档都记下来，判据分档判——
    // 只记一个布尔的话，窄屏那一档要么恒红，要么被放宽成「有圆角就行」。
    pill: nav ? parseFloat(getComputedStyle(nav).borderRadius) >= 999 : false,
    navRadius: nav ? parseFloat(getComputedStyle(nav).borderRadius) : 0,
    fixed: nav ? getComputedStyle(nav).position === 'fixed' : false,
    navCentred: navBox
      ? Math.abs((navBox.left + navBox.right) / 2 - innerWidth / 2) <= 2 : false,
    bodyW: body ? body.getBoundingClientRect().width : 0,
    vw: innerWidth,
    scrollW: document.documentElement.scrollWidth,
    // 「最右元素右缘」要按**看得见的那一段**算：被祖先 `overflow:hidden` 裁掉的部分
    // 用户看不到，也点不到。广场的卡堆 `.plaza-stack__slot` 是 `absolute` 排开的一叠，
    // 右缘实测 838 > 390——但它整段落在一个裁剪容器里，屏上根本没露出来。
    // 不减去裁剪就把它算成溢出，等于逼着下一个人去「修」一个本来就该被裁掉的东西。
    rightmost: (() => {
      let worst = 0;
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none') continue;
        let right = r.right;
        for (let p = el.parentElement; p; p = p.parentElement) {
          const ps = getComputedStyle(p);
          if (ps.overflowX !== 'visible' || ps.overflowY !== 'visible') {
            right = Math.min(right, p.getBoundingClientRect().right);
          }
        }
        if (right > worst) worst = right;
      }
      return worst;
    })(),
    mascot: !!document.querySelector('[data-nav-mascot], .anime-nav__mascot'),
    title: parseFloat(getComputedStyle(
      document.querySelector('.screen__title') || document.body).fontSize),
    bodyBackground: style.backgroundColor,
    bodyColor: style.color,
  };
}"""


def _declared(theme: str) -> dict[str, str]:
    text = COLORS.read_text(encoding="utf-8")
    root = re.search(r"^:root\{(.*?)\n\}", text, re.DOTALL | re.MULTILINE)
    dark = re.search(r'\[data-theme="dark"\]\{(.*?)\n\}', text, re.DOTALL)
    assert root and dark

    def decls(block: str) -> dict[str, str]:
        return {m.group(1): m.group(2).split("/*")[0].strip()
                for m in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", block)}

    light = decls(root.group(1))
    return light if theme == "light" else {**light, **decls(dark.group(1))}


def _rgb(value: str) -> str:
    v = value.lstrip("#")
    return f"rgb({int(v[0:2], 16)}, {int(v[2:4], 16)}, {int(v[4:6], 16)})"


def main() -> int:
    EYE04.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}
    onscreen: dict[str, object] = {"schema": "palette-onscreen/1", "screens": {}}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, height in VIEWPORTS:
            for theme in THEMES:
                page = browser.new_page(viewport={"width": width, "height": height},
                                        color_scheme=theme)
                errors: list[str] = []
                page.on("console", lambda m, sink=errors: sink.append(m.text)
                        if m.type == "error" else None)
                page.goto(URL, wait_until="networkidle")
                page.wait_for_timeout(1200)
                got = page.evaluate(MEASURE)
                shot = EYE04 / f"plaza-{width}x{height}-{theme}.png"
                page.screenshot(path=str(shot))
                key = f"{width}-{theme}"
                report[key] = {
                    "oneRow": got["oneRow"], "tops": got["tops"], "pill": got["pill"],
                    "fixed": got["fixed"], "bodyW": got["bodyW"], "vw": got["vw"],
                    "fill": (got["bodyW"] / got["vw"]) if got["vw"] else 0,
                    "scrollW": got["scrollW"],
                    "overflow": got["scrollW"] > got["vw"] + 1,
                    "mascot": got["mascot"], "title": got["title"],
                    "navRadius": got["navRadius"],
                    # `EYE-04` 的 390 那一档要判「最右元素右缘 <= 视口宽」——
                    # `fixed` 的药丸条溢出**不撑** `scrollWidth`，只判 overflow 会恒绿
                    # （`NAV-BAR-OVERFLOWS-AT-390` 就是这么被判绿一整批的）。
                    "rightmost": got["rightmost"],
                    "navCentred": got["navCentred"],
                    "errors": errors,
                    "shot": shot.as_posix(),
                }
                declared = _declared(theme)
                onscreen["screens"][key] = {          # type: ignore[index]
                    "theme": theme,
                    "bodyBackground": got["bodyBackground"],
                    "bodyColor": got["bodyColor"],
                    "declaredPaper": _rgb(declared["--paper"]),
                    "declaredInk": _rgb(declared["--ink"]),
                    "shot": shot.as_posix(),
                }
                page.close()
        browser.close()

    (EYE04 / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "onscreen.json").write_text(
        json.dumps(onscreen, ensure_ascii=False, indent=1), encoding="utf-8")

    for key, row in report.items():
        print(f"{key}: 铺满 {row['fill']:.2f} · 溢出 {row['overflow']} · 报错 {len(row['errors'])}")
    for key, row in onscreen["screens"].items():      # type: ignore[union-attr]
        print(f"{key}: body 底 {row['bodyBackground']} · 声明 {row['declaredPaper']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
