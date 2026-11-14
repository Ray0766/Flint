"""WB-02 取证：真浏览器 · 真栈 · 左栏选卡与「本次组合」。

跑法（playwright 恒在项目外的 `C:\\pwenv`）：

    C:\\pwenv\\Scripts\\python.exe tools/ui_probe_wb_cards.py

产出 `.ui-probe/wb/cards.json` + 两张截图。

**量的是「屏上显示的值 == 数据源里的值」**（第 13 批那条补充），
不是「有没有两个 chip」——只数个数的话，点了 A 而 chip 上写着 B 也会绿。
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

# 左栏那一列卡与它们各自的簇 id / 卡面主行。
READ_CARDS = """() => {
  const items = [...document.querySelectorAll('[data-wb-card]')];
  return {
    cardCount: items.length,
    allArePlazaCards: items.every(el => el.querySelector('.hotspot-card')),
    ids: items.map(el => el.getAttribute('data-wb-card')),
    // 卡面主行在 `NativeName` 里（`.native-name__primary`）——
    // **不是** `.hotspot-card__name`：那个类名不存在，第一版按记忆写的，
    // 于是这一格恒是空串，而「chip 上印的是不是那两条」这条判据
    // 会拿两个空串去比，永远不可能对上。
    names: items.map(el => {
      const n = el.querySelector('[data-testid=native-primary]');
      return n ? n.textContent.trim() : '';
    }),
    picked: items.filter(el => el.getAttribute('data-wb-picked') === 'true')
                 .map(el => el.getAttribute('data-wb-card')),
  };
}"""

READ_TRAY = """() => {
  const chips = [...document.querySelectorAll('[data-wb-tray-id]')];
  const box = document.querySelector('[data-wb-tray]');
  return {
    trayIds: chips.map(c => c.getAttribute('data-wb-tray-id')),
    trayLabels: chips.map(c => c.querySelector('.wb-tray__chip-label').textContent.trim()),
    trayCount: Number(box.getAttribute('data-wb-tray-count')),
  };
}"""

READ_EVIDENCE = """() => {
  const rows = [...document.querySelectorAll('[data-wb-evidence]')];
  const box = document.querySelector('[data-wb-evidence-state]');
  return {
    count: rows.length,
    state: box ? box.getAttribute('data-wb-evidence-state') : 'missing',
    clusterIds: rows.map(r => r.getAttribute('data-wb-evidence-cluster')),
    everyRowNamesItsCluster: rows.every(r =>
      (r.getAttribute('data-wb-evidence-cluster') || '').length > 0
      && r.querySelector('.wb-cards__evidence-from')),
  };
}"""


def main() -> int:
    report: dict[str, object] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="light")
        errors: list[str] = []
        page.on("console",
                lambda m, sink=errors: sink.append(m.text) if m.type == "error" else None)
        page.goto(URL, wait_until="networkidle")
        # 左栏取数要往回找有数据的那一天，给它时间。
        page.wait_for_selector("[data-wb-card]", timeout=60_000)
        page.wait_for_timeout(600)

        cards = page.evaluate(READ_CARDS)
        report.update(cards)

        # 一条都没选时证据那一格说什么。
        report["evidenceEmpty"] = {
            **page.evaluate(READ_EVIDENCE),
            "says": bool(page.evaluate(
                "document.querySelector('[data-wb-evidence-state]')?.textContent.trim()")),
        }

        # 选两张：**记下点的是哪两条**，再去比屏上显示的是不是那两条。
        clicked = list(cards["ids"])[:2]
        clicked_names = [cards["names"][cards["ids"].index(i)] for i in clicked]
        for cluster_id in clicked:
            page.click(f'[data-wb-pick="{cluster_id}"]')
            page.wait_for_timeout(200)
        page.wait_for_timeout(800)

        tray = page.evaluate(READ_TRAY)
        report["pick"] = {
            **tray,
            "clicked": clicked,
            "clickedNames": clicked_names,
            "cardsMarkedPicked": page.evaluate(READ_CARDS)["picked"],
        }

        # 证据跟着已选热点走。
        page.wait_for_timeout(1200)
        report["evidence"] = {
            **page.evaluate(READ_EVIDENCE),
            "pickedClusters": clicked,
        }

        page.screenshot(path=str(OUT / "workbench-cards-1920x1080-light.png"))

        # 阴性对照：取消第一条，**看少的是不是正是那一条**。
        removed = clicked[0]
        page.click(f'[data-wb-tray-remove="{removed}"]')
        page.wait_for_timeout(500)
        after = page.evaluate(READ_TRAY)
        report["unpick"] = {
            "removed": removed,
            "trayCount": tray["trayCount"],
            "trayIdsAfter": after["trayIds"],
            "trayCountAfter": after["trayCount"],
            "expectedAfter": [i for i in clicked if i != removed],
        }

        report["errors"] = errors
        report["scrollW"] = page.evaluate("document.documentElement.scrollWidth")
        report["vw"] = page.evaluate("innerWidth")
        report["cardsScrollHeight"] = page.evaluate(
            "document.querySelector('[data-wb-scroll=cards]').scrollHeight")
        report["cardsClientHeight"] = page.evaluate(
            "document.querySelector('[data-wb-scroll=cards]').clientHeight")
        report["pageScrollTop"] = page.evaluate(
            "document.scrollingElement.scrollTop || window.scrollY || 0")
        page.close()

        dark = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="dark")
        dark.goto(URL, wait_until="networkidle")
        dark.wait_for_selector("[data-wb-card]", timeout=60_000)
        dark.wait_for_timeout(600)
        dark.screenshot(path=str(OUT / "workbench-cards-1920x1080-dark.png"))
        dark.close()
        browser.close()

    (OUT / "cards.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"卡 {report['cardCount']} 张 · 同类名 {report['allArePlazaCards']}")
    print(f"选中 {report['pick']['clicked']} → 组合 {report['pick']['trayIds']}")
    print(f"证据 {report['evidence']['count']} 条 · 空态 {report['evidenceEmpty']['state']}")
    print(f"取消 {report['unpick']['removed']} → 剩 {report['unpick']['trayIdsAfter']}")
    print(f"报错 {len(report['errors'])} · 横向 {report['scrollW']}/{report['vw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
