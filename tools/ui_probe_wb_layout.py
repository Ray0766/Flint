"""WB-01 取证：真浏览器 · 真栈 · 三视口 × 两主题量三栏骨架。

跑法（playwright 恒在项目外的 `C:\\pwenv`）：

    C:\\pwenv\\Scripts\\python.exe tools/ui_probe_wb_layout.py

产出 `.ui-probe/wb/layout.json` + 六张截图。判据 `tests/v041/test_wb_layout.py`
只读这份产出——**NEVER 用组件快照冒充整屏**（第 13 批那条纪律）。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(".ui-probe/wb")
OUT.mkdir(parents=True, exist_ok=True)
URL = "http://localhost:3000/workbench"

# 量一栏：位置 / 尺寸 / 那几行让它成立的 computed style。
# `scrollOverflowY` 量的是**栏内那一层**（蓝本三处 `overflow-y:auto` 都在栏内部）。
READ = """() => {
  const cs = el => getComputedStyle(el);
  const col = name => {
    const el = document.querySelector(`[data-wb-col="${name}"]`);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const s = cs(el);
    const sc = el.querySelector(`[data-wb-scroll="${name}"]`);
    return {
      name,
      left: r.left, right: r.right, top: r.top, bottom: r.bottom,
      width: r.width, height: r.height,
      flexGrow: s.flexGrow, minWidth: s.minWidth, minHeight: s.minHeight,
      scrollOverflowY: sc ? cs(sc).overflowY : 'no-scroller',
      scrollHeight: sc ? sc.scrollHeight : 0,
    };
  };
  const root = document.querySelector('.workbench');
  const docEl = document.querySelector('[data-wb-doc]');
  const dr = docEl ? docEl.getBoundingClientRect() : null;
  const paintOf = sel => {
    const el = document.querySelector(sel);
    if (!el) return 'missing:' + sel;
    const s = cs(el);
    return s.backgroundColor + '|' + s.color + '|' + s.borderColor;
  };
  return {
    cards: col('cards'), chat: col('chat'), preview: col('preview'),
    doc: dr ? { width: dr.width, left: dr.left } : null,
    root: { overflow: cs(root).overflow, height: root.getBoundingClientRect().height },
    // DARK-02 的形状：两主题量到同一组颜色就判红。
    paint: {
      workbench: paintOf('.workbench'),
      side: paintOf('.workbench__side'),
      preview: paintOf('.workbench__preview'),
      canvas: paintOf('.workbench__canvas'),
    },
    scrollW: document.documentElement.scrollWidth,
    vw: innerWidth,
  };
}"""

# 往卡片栏的滚动层里塞一块 4000px，量完**当场撤掉**。
# 量的是机制（这一层能不能滚 / 整屏会不会跟着滚），不是「它现在有没有滚」。
SCROLL_PROBE = """() => {
  const sc = document.querySelector('[data-wb-scroll="cards"]');
  const base = sc.scrollHeight;
  const spike = document.createElement('div');
  spike.style.height = '4000px';
  spike.setAttribute('data-probe-spike', 'true');
  sc.appendChild(spike);
  sc.scrollTop = 1000;
  const out = {
    baseScrollHeight: base,
    colScrollTop: sc.scrollTop,
    pageScrollTop: document.scrollingElement.scrollTop || window.scrollY || 0,
  };
  spike.remove();
  sc.scrollTop = 0;
  out.restoredScrollHeight = sc.scrollHeight;
  return out;
}"""


def drag(page, selector: str, dx: int) -> dict[str, object]:
    """按住拖条挪 dx 像素，量拖动前后的宽度。"""
    grip = page.locator(selector)
    box = grip.bounding_box()
    assert box is not None, selector
    cards = page.locator('[data-wb-col="cards"]')
    chat = page.locator('[data-wb-col="chat"]')
    before = cards.bounding_box()["width"]  # type: ignore[index]

    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    # 分步移动：一步跳到位的话，有的实现只在中途的 move 事件里更新。
    for step in range(1, 6):
        page.mouse.move(box["x"] + box["width"] / 2 + dx * step / 5,
                        box["y"] + box["height"] / 2)
    page.mouse.up()
    page.wait_for_timeout(150)
    after = cards.bounding_box()["width"]  # type: ignore[index]

    # 再往右拖到极限，看中栏还剩多少。
    box2 = grip.bounding_box()
    assert box2 is not None
    page.mouse.move(box2["x"] + box2["width"] / 2, box2["y"] + box2["height"] / 2)
    page.mouse.down()
    for step in range(1, 8):
        page.mouse.move(box2["x"] + 200 * step, box2["y"])
    page.mouse.up()
    page.wait_for_timeout(150)
    chat_at_limit = chat.bounding_box()["width"]  # type: ignore[index]

    return {
        "dx": dx,
        "before": before,
        "after": after,
        "chatAtLimit": chat_at_limit,
        "scrollWAtLimit": page.evaluate("document.documentElement.scrollWidth"),
        "vw": page.evaluate("innerWidth"),
    }


def main() -> int:
    report: dict[str, object] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, height in ((1920, 1080), (1440, 900), (390, 844)):
            for theme in ("light", "dark"):
                page = browser.new_page(viewport={"width": width, "height": height},
                                        color_scheme=theme)
                errors: list[str] = []
                # 默认参把**当次循环**的 sink 钉住：直接闭包捕获 `errors` 的话，
                # 回调真正被调用时读到的是最后一次循环的那个列表（B023）。
                page.on("console",
                        lambda m, sink=errors: sink.append(m.text)
                        if m.type == "error" else None)
                page.goto(URL, wait_until="networkidle")
                page.wait_for_selector('[data-wb-col="preview"]')
                page.wait_for_timeout(400)

                measured = page.evaluate(READ)
                measured["errors"] = errors
                if width == 1920 and theme == "light":
                    measured["scrollProbe"] = page.evaluate(SCROLL_PROBE)
                    measured["drag"] = drag(page, '[data-wb-grip="cards"]', 120)
                    # 拖过之后布局不再是初始值——量完再刷回来截图。
                    page.reload(wait_until="networkidle")
                    page.wait_for_selector('[data-wb-col="preview"]')
                    page.wait_for_timeout(300)

                shot = OUT / f"workbench-{width}x{height}-{theme}.png"
                page.screenshot(path=str(shot), full_page=(width == 390))
                measured["shot"] = shot.as_posix()
                report[f"{width}-{theme}"] = measured
                page.close()
        browser.close()

    (OUT / "layout.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for key, m in report.items():
        cards = m["cards"]["width"] if m["cards"] else "—"
        doc = m["doc"]["width"] if m["doc"] else "—"
        ok = "OK" if not m["errors"] and m["scrollW"] <= m["vw"] + 1 else "!!"
        print(f"{ok} {key:12} 卡片栏={cards} 文档列={doc} "
              f"横向={m['scrollW']}/{m['vw']} 报错={len(m['errors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
