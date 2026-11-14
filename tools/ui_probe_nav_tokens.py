"""TAIL-01 取证：药丸条与吉祥物的 computed color，**搬家前后各量一次**。

跑法（playwright 恒在项目外的 `C:\\pwenv`）：

    C:\\pwenv\\Scripts\\python.exe tools/ui_probe_nav_tokens.py .ui-probe/tail01/nav-before.json
    …搬…
    C:\\pwenv\\Scripts\\python.exe tools/ui_probe_nav_tokens.py .ui-probe/tail01/nav-after.json

`TAIL-01` **搬的是位置不是值**。这份取证是那句话唯一的证明方式：
两份 JSON 逐键相等 → 位置换了、值没变；有一处不等 → 借搬家顺手调了色。

## 为什么量两层

- **token 层**：`getComputedStyle(html)` 读那 14 个变量的解析值。
  只量这一层的话，「变量还在但没人读它了」会被判成通过；
- **元素层**：药丸条与吉祥物身上真正生效的 `background-color` /
  `border-color` / `box-shadow` / `color`。这一层才是屏上看得见的东西。

两个主题各量一遍（`data-theme` 显式钉住，NEVER 靠系统偏好——
那样量到的是这台机器此刻的设置）。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from playwright.sync_api import sync_playwright

URL = "http://localhost:3000/plaza"

TOKENS = [
    "--mascot-face", "--mascot-ink", "--mascot-blush",
    "--nav-ink-on-dark", "--nav-ink-on-light",
    "--nav-surface", "--nav-border", "--nav-shadow",
    "--nav-ink", "--nav-ink-active", "--nav-hover-bg",
    "--nav-accent", "--nav-top",
]

#: 元素层：选择器 → 要读的属性。**药丸条与吉祥物各占几行**。
ELEMENTS = {
    ".anime-nav": ["background-color", "border-top-color", "box-shadow"],
    ".anime-nav__tab": ["color"],
    '.anime-nav__tab[data-active="true"]': ["color"],
    ".anime-nav__mascot-head": ["background-color", "box-shadow"],
    ".anime-nav__mascot-eye": ["background-color"],
    ".anime-nav__mascot-blush": ["background-color"],
}

READ = """([tokens, elements]) => {
  const html = getComputedStyle(document.documentElement);
  const out = {tokens: {}, elements: {}, missing: []};
  for (const name of tokens) out.tokens[name] = html.getPropertyValue(name).trim();
  for (const [selector, props] of Object.entries(elements)) {
    const el = document.querySelector(selector);
    if (!el) { out.missing.push(selector); continue; }
    const style = getComputedStyle(el);
    out.elements[selector] = Object.fromEntries(
      props.map((p) => [p, style.getPropertyValue(p)]));
  }
  return out;
}"""


def main() -> int:
    out_path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                            else ".ui-probe/tail01/nav-before.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for theme in ("light", "dark"):
            page = browser.new_page(viewport={"width": 1440, "height": 900},
                                    color_scheme=theme)  # type: ignore[arg-type]
            page.goto(URL, wait_until="networkidle")
            # 主题**显式钉住**：靠系统偏好量到的是这台机器此刻的设置。
            page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
            page.wait_for_selector(".anime-nav", timeout=60_000)
            page.wait_for_timeout(500)
            report[theme] = page.evaluate(READ, [TOKENS, ELEMENTS])
            page.screenshot(path=str(out_path.parent
                                     / f"nav-{out_path.stem.split('-')[-1]}-{theme}.png"),
                            clip={"x": 0, "y": 0, "width": 1440, "height": 220})
            page.close()
        browser.close()
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    for theme in ("light", "dark"):
        block = dict(report[theme])          # type: ignore[arg-type]
        print(f"[{theme}] token {len(block['tokens'])} 个 · "        # type: ignore[arg-type]
              f"元素 {len(block['elements'])} 个 · "                 # type: ignore[arg-type]
              f"缺 {block['missing']}")
        print(f"    --nav-surface = {block['tokens']['--nav-surface']}")  # type: ignore[index]
    print(f"写入 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
