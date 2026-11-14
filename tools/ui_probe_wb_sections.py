"""WB-05 取证：真浏览器 · 真栈 · 章节导航 + 逐章检查项。

跑法：`C:\\pwenv\\Scripts\\python.exe tools/ui_probe_wb_sections.py`
产出 `.ui-probe/wb/sections.json` + 两张截图。

五套模板各开一次（`?template=`），逐套记下屏上的章 id / 章名 / 检查问句。
另外记：导航的 `position` 与宽度、点一章之后文档有没有真的跳过去、
缺章那几条说了什么、逐章判定这一列的三态各有几个。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(".ui-probe/wb")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:3000/workbench"
#: 拿**真产物**验：它缺好几章（真跑那次账本是空的），
#: 「这一章还没写」那条判据才量得到东西。
REAL = "del-job-4d22d6be-c3dc-47cf-b334-70a573efb7f4"
FIVE = ("generic", "startup", "engineering", "grant", "thesis")

READ_NAV = """() => {
  const items = [...document.querySelectorAll('[data-wb-section]')];
  const nav = document.querySelector('[data-wb-sections]');
  return {
    template: nav ? nav.getAttribute('data-wb-sections') : null,
    ids: items.map(el => el.getAttribute('data-wb-section')),
    names: items.map(el => el.querySelector('[data-wb-section-jump]').textContent.trim()),
    checks: items.map(el => el.querySelector('[data-wb-section-check]').textContent.trim()),
    verdicts: items.map(el => el.getAttribute('data-wb-section-verdict')),
    present: items.map(el => el.getAttribute('data-wb-section-present')),
  };
}"""

READ_GEOMETRY = """() => {
  const nav = document.querySelector('.workbench__nav');
  const inner = document.querySelector('[data-wb-sections]');
  return {
    position: getComputedStyle(nav).position,
    width: nav.getBoundingClientRect().width,
    hasInner: !!inner,
  };
}"""

READ_ABSENT = """() => {
  const items = [...document.querySelectorAll('[data-wb-section-present="false"]')];
  return {
    count: items.length,
    everyAbsentSaysSo: items.every(el => el.querySelector('.wb-sections__absent')),
    everyAbsentJumpDisabled: items.every(
      el => el.querySelector('[data-wb-section-jump]').disabled),
  };
}"""

READ_VERDICTS = """(unknownWord) => {
  const items = [...document.querySelectorAll('[data-wb-section]')];
  const marks = items.map(el => el.getAttribute('data-wb-section-verdict'));
  return {
    unknown: marks.filter(m => m === 'unknown').length,
    pass: marks.filter(m => m === 'pass').length,
    fail: marks.filter(m => m === 'fail').length,
    unknownWording: items.some(
      el => (el.innerText || '').includes(unknownWord)),
  };
}"""


def main() -> int:
    report: dict[str, object] = {}
    zh = json.loads(pathlib.Path("web/messages/zh.json").read_text(encoding="utf-8"))
    unknown_word = zh["wb.sections.check_unknown"]

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="light")
        errors: list[str] = []
        page.on("console",
                lambda m, sink=errors: sink.append(m.text) if m.type == "error" else None)
        asked: list[str] = []
        page.on("request", lambda req, sink=asked: sink.append(req.url)
                if "/quality" in req.url else None)

        tables: dict[str, object] = {}
        for template_id in FIVE:
            page.goto(f"{BASE}?deliverable={REAL}&template={template_id}",
                      wait_until="networkidle")
            page.wait_for_selector("[data-wb-section]", timeout=60_000)
            page.wait_for_timeout(500)
            got = page.evaluate(READ_NAV)
            assert got["template"] == template_id, got["template"]
            tables[template_id] = got
            if template_id == "generic":
                page.screenshot(path=str(OUT / "workbench-sections-1920x1080-light.png"),
                                full_page=True)
        report["templates"] = tables

        # 几何 + 缺章 + 判定：都在最后那一套（thesis）的屏上量，
        # 而**逐章判定那一列与模板无关**（它按 section_id 问后端）。
        page.goto(f"{BASE}?deliverable={REAL}&template=generic", wait_until="networkidle")
        page.wait_for_selector("[data-wb-section]", timeout=60_000)
        page.wait_for_timeout(800)
        report["geometry"] = page.evaluate(READ_GEOMETRY)
        verdicts = page.evaluate(READ_VERDICTS, unknown_word)
        verdicts["asked"] = len(asked) > 0
        report["verdicts"] = verdicts

        # 缺章那条**换一套模板量**：这份真产物是 generic 出的，七章齐全，
        # 在它自己那套模板上「这一章还没写」一条都量不到。切到 thesis——
        # 它那六章正文里一个都没有，于是六条都该说「还没有」且跳转键禁用。
        page.goto(f"{BASE}?deliverable={REAL}&template=thesis", wait_until="networkidle")
        page.wait_for_selector("[data-wb-section]", timeout=60_000)
        page.wait_for_timeout(500)
        report["absent"] = page.evaluate(READ_ABSENT)
        page.goto(f"{BASE}?deliverable={REAL}&template=generic", wait_until="networkidle")
        page.wait_for_selector("[data-wb-section]", timeout=60_000)
        page.wait_for_timeout(800)

        # 点一章：文档真的跳过去了吗。**量滚动位置 + 那一章在不在视口里**，
        # NEVER 只判「点得动」——点得动而没跳，屏上看起来就是没反应。
        canvas = "[data-wb-scroll=preview]"
        target = [sid for sid, present in zip(
            page.evaluate("[...document.querySelectorAll('[data-wb-section]')]"
                          ".map(e => e.getAttribute('data-wb-section'))"),
            page.evaluate("[...document.querySelectorAll('[data-wb-section]')]"
                          ".map(e => e.getAttribute('data-wb-section-present'))"),
            strict=True) if present == "true"][-1]
        before = page.evaluate(f"document.querySelector('{canvas}').scrollTop")
        page.click(f'[data-wb-section-jump="{target}"]')
        page.wait_for_timeout(1200)
        after = page.evaluate(f"document.querySelector('{canvas}').scrollTop")
        in_view = page.evaluate(
            "(sid) => {"
            " const el = document.querySelector(`[data-section-id=\"${sid}\"]`);"
            " if (!el) return false;"
            " const r = el.getBoundingClientRect();"
            " return r.top >= -4 && r.top < innerHeight; }", target)
        report["jump"] = {
            "section": target, "before": before, "after": after,
            "scrolled": after != before, "targetInView": in_view,
        }

        report["errors"] = errors
        page.close()

        dark = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="dark")
        dark.goto(f"{BASE}?deliverable={REAL}&template=grant", wait_until="networkidle")
        dark.wait_for_selector("[data-wb-section]", timeout=60_000)
        dark.wait_for_timeout(800)
        dark.screenshot(path=str(OUT / "workbench-sections-1920x1080-dark.png"),
                        full_page=True)
        dark.close()
        browser.close()

    (OUT / "sections.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for template_id in FIVE:
        rows = report["templates"][template_id]          # type: ignore[index]
        print(f"{template_id}: {len(rows['ids'])} 章 · {rows['names']}")
    print(f"导航 {report['geometry']['position']} · 宽 {report['geometry']['width']}")
    print(f"缺章 {report['absent']['count']} 条 · 都说了 {report['absent']['everyAbsentSaysSo']}")
    print(f"判定 未判 {report['verdicts']['unknown']} · 通过 {report['verdicts']['pass']}"
          f" · 问过后端 {report['verdicts']['asked']}")
    print(f"跳转 {report['jump']['section']}：{report['jump']['before']} → "
          f"{report['jump']['after']} · 在视口 {report['jump']['targetInView']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
