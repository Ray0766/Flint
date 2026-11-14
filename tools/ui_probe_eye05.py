"""EYE-05 取证：工作台整屏 · 三视口 × 两主题 · 六张 + 一组流程图。

跑法：`C:\\pwenv\\Scripts\\python.exe tools/ui_probe_eye05.py`
产出 `.ui-probe/eye05/`（六张整屏 + 五张流程 + report.json）。

**截图与数一起落盘**：只有图的话，下一个人无从判断它当时算不算合格
（`EYE-04` 定的口径，一字不变）。

流程那一组按人真的会走的顺序拍：选卡 → 写假设 → 提交 → 出块（右栏真 Block）→
点一块提批注。每一步拍一张，**每张都带那一步的量**（不是只有图）。
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(".ui-probe/eye05")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:3000/workbench"
REAL = "del-job-4d22d6be-c3dc-47cf-b334-70a573efb7f4"
PROJECT = "proj-demo-fixture"
VIEWPORTS = ((1920, 1080), (1440, 900), (390, 844))
THEMES = ("light", "dark")

MEASURE = """() => {
  const box = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return {x: r.x, y: r.y, w: r.width, h: r.height};
  };
  let rightmost = {right: 0, sel: ''};
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (getComputedStyle(el).visibility === 'hidden') continue;
    if (r.right > rightmost.right) {
      rightmost = {right: r.right,
                   sel: el.tagName.toLowerCase() + '.' + (el.className || '').toString().slice(0, 40)};
    }
  }
  const blocks = [...document.querySelectorAll('[data-block-id]')];
  return {
    cards: box('[data-wb-col=cards]'),
    chat: box('[data-wb-col=chat]'),
    preview: box('[data-wb-col=preview]'),
    vw: innerWidth,
    scrollW: document.documentElement.scrollWidth,
    rightmost,
    blockCount: blocks.length,
    blockTypes: [...new Set(blocks.map(b => b.getAttribute('data-block-type')))],
    // 右栏渲染的是**真 Block** 还是占位文案：两者在截图上长得不一样，
    // 但只有数得出来才判得了。
    placeholderOnly: blocks.length === 0
                     && !!document.querySelector('.workbench__placeholder'),
  };
}"""


def main() -> int:
    report: dict[str, object] = {"screens": {}, "flow": {}}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for width, height in VIEWPORTS:
            for theme in THEMES:
                page = browser.new_page(viewport={"width": width, "height": height},
                                        color_scheme=theme)
                errors: list[str] = []
                bad: list[dict[str, object]] = []
                page.on("console",
                        lambda m, sink=errors: sink.append(m.text)
                        if m.type == "error" else None)
                page.on("response", lambda res, sink=bad: sink.append(
                    {"url": res.url, "status": res.status}) if res.status >= 400 else None)
                page.goto(f"{BASE}?deliverable={REAL}&project={PROJECT}",
                          wait_until="networkidle")
                page.wait_for_selector("[data-block-id]", timeout=60_000)
                page.wait_for_timeout(1200)
                got = page.evaluate(MEASURE)
                got["errors"] = errors
                got["badPaths"] = sorted({
                    str(row["url"]).split(":8000")[-1] for row in bad})
                name = f"workbench-{width}x{height}-{theme}.png"
                page.screenshot(path=str(OUT / name), full_page=False)
                got["shot"] = name
                report["screens"][f"{width}x{height}-{theme}"] = got  # type: ignore[index]
                page.close()

        # ── 流程图：按人真的会走的顺序，一步一张
        page = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="light")
        flow: dict[str, object] = {}

        # ① 空手进来
        page.goto(f"{BASE}?project={PROJECT}", wait_until="networkidle")
        page.wait_for_selector("[data-wb-card]", timeout=60_000)
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "flow-1-empty.png"))
        flow["1_empty"] = {
            "cards": page.locator("[data-wb-card]").count(),
            "docState": page.get_attribute("[data-wb-preview]", "data-wb-doc-state"),
        }

        # ② 选两张卡
        ids = page.eval_on_selector_all(
            "[data-wb-card]", "els => els.slice(0,2).map(e => e.getAttribute('data-wb-card'))")
        for cluster_id in ids:
            page.click(f'[data-wb-pick="{cluster_id}"]')
            page.wait_for_timeout(250)
        page.wait_for_selector("[data-wb-evidence]", timeout=60_000)
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / "flow-2-picked.png"))
        flow["2_picked"] = {
            "picked": ids,
            "tray": page.eval_on_selector_all(
                "[data-wb-tray-id]", "els => els.map(e => e.getAttribute('data-wb-tray-id'))"),
            "evidence": page.locator("[data-wb-evidence]").count(),
        }

        # ③ 写一句假设并提交（`COMBO-WIRE-01` 之后服务端答 200，屏上给回执；
        #    此前恒 503，屏上原样转述那句拒绝——两种都要量得到）
        page.fill("[data-wb-input]", "这两条热点能不能支撑一份可执行的内容策划")
        page.wait_for_timeout(200)
        page.click("[data-wb-submit]")
        page.wait_for_function(
            "() => document.querySelector('[data-wb-chat]')"
            ".getAttribute('data-wb-chat-pending') === 'false'", timeout=120_000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "flow-3-submitted.png"))
        flow["3_submitted"] = {
            "lastKind": page.evaluate(
                "[...document.querySelectorAll('[data-wb-msg]')].pop()"
                ".getAttribute('data-wb-msg-kind')"),
            # **终态 = 最后一条 receipt/failure**，不是最后一条消息：
            # 成了那一路后面还跟着一条「下一步还没接上」的 notice，
            # 拿最后一行当终态的话，读到的是那条告知——它既不是成也不是败。
            "outcomeKind": page.evaluate(
                "[...document.querySelectorAll('[data-wb-msg]')]"
                ".map(r => r.getAttribute('data-wb-msg-kind'))"
                ".filter(k => k === 'receipt' || k === 'failure').pop() || null"),
            "text": page.inner_text("[data-wb-chat]")[-160:],
        }

        # ④ 右栏出真 Block（今天走的是「打开一份已有产物」那条路）
        page.goto(f"{BASE}?deliverable={REAL}&project={PROJECT}", wait_until="networkidle")
        page.wait_for_selector("[data-block-id]", timeout=60_000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "flow-4-blocks.png"))
        flow["4_blocks"] = {
            "blocks": page.locator("[data-block-id]").count(),
            "sections": page.locator("[data-wb-section]").count(),
            "cites": page.locator("[data-wb-cite]").count(),
        }

        # ⑤ 点一块，提批注（**不提交**：提交会真跑一次模型，那是 WB-06 干的事）
        block_id = page.evaluate(
            "[...document.querySelectorAll('[data-block-type=paragraph]')]"
            "[1].getAttribute('data-block-id')")
        page.click(f'[data-block-id="{block_id}"]')
        page.wait_for_timeout(300)
        page.fill("[data-wb-annotate-input]", "把这一段收紧到三句话")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "flow-5-annotate.png"))
        flow["5_annotate"] = {
            "block": block_id,
            "canSubmit": not page.is_disabled("[data-wb-annotate-submit]"),
        }
        report["flow"] = flow
        page.close()
        browser.close()

    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for key, got in report["screens"].items():        # type: ignore[union-attr]
        print(f"{key}: 块 {got['blockCount']} · 最右 {got['rightmost']['right']:.0f}/{got['vw']}"
              f" · 报错 {len(got['errors'])}")
    print(f"流程：卡 {flow['2_picked']['tray']} → {flow['3_submitted']['lastKind']}"
          f" → 块 {flow['4_blocks']['blocks']} → 批注 {flow['5_annotate']['block']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
