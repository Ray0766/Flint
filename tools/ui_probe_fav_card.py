r"""FAV-CARD-01 的取证脚本：收藏屏三视口 × 两主题共六张截图 + 实测数。

**跑法**（playwright 恒在项目外）：

    C:\pwenv\Scripts\python.exe tools/ui_probe_fav_card.py

产出落 `.ui-probe/favcard/`：六张 png + 一份 `report.json`。
判据 `tests/v041/test_fav_card.py` 读的就是那份 json——
**截图与数一起落盘**：只有图的话，下一个人无从判断它当时算不算合格。
"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = pathlib.Path(".ui-probe/favcard")
OUT.mkdir(parents=True, exist_ok=True)

READ = """() => {
  const cards = [...document.querySelectorAll('.favorites .hotspot-card')];
  const plazaClass = 'hotspot-card';
  // **量看得见的文字**：`.favorites__target` 那一格是 `sr-only`
  // （1×1 + clip-path，屏上看不见，只给读屏软件与判据用）。
  // 读 `innerText` 会把它算进来——于是「屏上有没有裸簇 id」这条
  // 会永远说「有」，而屏上其实没有。
  const visible = el => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden'
           && cs.display !== 'none';
  };
  const body = [...document.querySelectorAll('.favorites *')]
    .filter(el => el.children.length === 0 && visible(el))
    .map(el => el.textContent)
    .join(' ');
  const slots = cards[0]
    ? [...cards[0].querySelectorAll('[class*=hotspot-card__]')]
        .map(e => String(e.className).replace('hotspot-card__', ''))
    : [];
  return {
    cards: cards.length,
    sameClass: cards.every(c => String(c.className).includes(plazaClass)),
    slots,
    filled: cards[0]
      ? [...cards[0].querySelectorAll('[class*=hotspot-card__]')]
          .every(e => String(e.textContent).trim().length > 0)
      : false,
    rawId: new RegExp('c-[0-9]{8}-[0-9]{3}').test(body),
    actions: document.querySelectorAll('[data-favorite-action]').length,
    noFace: document.querySelectorAll('[data-favorite-no-face]').length,
    scrollW: document.documentElement.scrollWidth,
    vw: innerWidth,
  };
}"""

report = {}
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for w, h in ((1920, 1080), (1440, 900), (390, 844)):
        for theme in ("light", "dark"):
            page = b.new_page(viewport={"width": w, "height": h}, color_scheme=theme)
            errs = []
            page.on("console",
                    lambda m, sink=errs: sink.append(m.text)
                    if m.type == "error" else None)
            page.goto("http://localhost:3000/favorites", wait_until="networkidle")
            page.wait_for_timeout(1200)
            m = page.evaluate(READ)
            shot = OUT / f"favorites-{w}x{h}-{theme}.png"
            page.screenshot(path=str(shot))
            m["errors"] = errs
            m["shot"] = shot.as_posix()
            report[f"{w}-{theme}"] = m
            page.close()
    b.close()

(OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
for k, v in report.items():
    ok = "✓" if (v["cards"] > 0 and v["sameClass"] and not v["rawId"]
                 and not v["errors"]) else "✗"
    print(f"{ok} {k:12} 卡={v['cards']} 同类名={v['sameClass']} 槽={len(v['slots'])} "
          f"裸id={v['rawId']} 动作={v['actions']} 报错={len(v['errors'])}")
