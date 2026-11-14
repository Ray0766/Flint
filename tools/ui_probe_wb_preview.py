"""WB-04 取证：真浏览器 · 真栈 · 右栏渲染真 Block。

跑法（playwright 恒在项目外的 `C:\\pwenv`）：

    C:\\pwenv\\Scripts\\python.exe tools/ui_probe_wb_preview.py

产出 `.ui-probe/wb/preview.json` + 两张截图。

## 拿哪两份产物

| 产物 | 从哪来 | 验什么 |
|---|---|---|
| `del-demo-fixture-report` | 夹具（库里真有的行） | **八种块各一** + 三通道 + 出处原文 |
| `del-job-4d22d6be-…` | 第 12 批那次真跑的 report 作业 | 链**真的产出的东西**画得出来 |

八种只有夹具那份齐全，这是实况不是取巧：真跑那次账本是空的
（唯一那条 claim `alignment=partial`，`S2-4` 禁止提升为 Fact），
组稿只出得了 heading / paragraph / gap_notice。

## 未知块型那条阴性对照怎么造

真端点造不出未知块型（后端按冻结件写）。所以**在浏览器这一侧改一次答复**：
拦下 `/blocks` 的响应，往里塞一个 `type: "hologram"` 的块。
拦的是答复内容，量的是屏怎么处置它——这正是阴性对照该做的事。
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(".ui-probe/wb")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:3000/workbench"
API = "http://127.0.0.1:8000"
FIXTURE = "del-demo-fixture-report"
REAL = "del-job-4d22d6be-c3dc-47cf-b334-70a573efb7f4"
REAL_JOB = "job-4d22d6be-c3dc-47cf-b334-70a573efb7f4"

READ_DOC = """() => {
  const box = document.querySelector('[data-wb-preview]');
  const blocks = [...document.querySelectorAll('[data-block-id]')];
  const byType = {};
  for (const el of blocks) {
    const r = el.getBoundingClientRect();
    byType[el.getAttribute('data-block-type')] = {
      w: r.width, h: r.height, text: (el.innerText || '').slice(0, 120),
    };
  }
  return {
    state: box.getAttribute('data-wb-doc-state'),
    blockCount: blocks.length,
    types: blocks.map(b => b.getAttribute('data-block-type')),
    ids: blocks.map(b => b.getAttribute('data-block-id')),
    byType,
    arrived: (box.querySelector('[data-wb-doc-arrived]')
              ?.getAttribute('data-wb-doc-arrived') || '').split(' ').filter(Boolean),
    progressOnScreen: !!box.querySelector('[data-wb-doc-progress]'),
    unknown: [...box.querySelectorAll('[data-wb-doc-unknown]')]
             .map(el => ({type: el.getAttribute('data-wb-doc-unknown'),
                          text: (el.innerText || '')})),
  };
}"""

# 三通道：每个带出处的格子**恰好**一个记号。带两个 = 这个数字有两个出处。
READ_CHANNELS = """() => {
  const cells = [...document.querySelectorAll(
    '[data-fact-id], [data-price-entry-id], [data-profile-path]')];
  const bad = [];
  const kinds = [];
  for (const el of cells) {
    const marks = ['data-fact-id', 'data-price-entry-id', 'data-profile-path']
      .filter(a => el.hasAttribute(a));
    if (marks.length !== 1) bad.push(el.outerHTML.slice(0, 80));
    kinds.push(marks[0] === 'data-fact-id' ? 'fact'
               : marks[0] === 'data-price-entry-id' ? 'price' : 'profile');
  }
  const fact = document.querySelector('[data-fact-id]');
  return {
    cells: cells.length,
    everyCellHasExactlyOneChannel: bad.length === 0,
    bad,
    kinds,
    factId: fact ? fact.getAttribute('data-fact-id') : null,
    screenValue: fact ? (fact.innerText || '').trim() : '',
  };
}"""

# 取不回来的出处：屏上 MUST 如实说「接口未提供」并留下原 id
# （`DerefValue` 的既有三态之一）。空白读起来是「这里本来就没东西」。
READ_UNAVAILABLE = """() => {
  const rows = [...document.querySelectorAll('[data-testid=deref-unavailable]')];
  return {
    count: rows.length,
    kinds: rows.map(r => r.getAttribute('data-deref-kind')),
    ids: rows.map(r => r.getAttribute('data-deref-id')),
    saysSo: rows.every(r => (r.innerText || '').trim().length > 0),
  };
}"""

READ_CITES = """() => {
  const rows = [...document.querySelectorAll('[data-wb-cite]')];
  const first = rows[0];
  const original = first
    ? first.querySelector('[data-testid=quote-original-only], [data-testid=quote-original]')
    : null;
  return {
    count: rows.length,
    firstId: first ? first.getAttribute('data-wb-cite') : null,
    originalOnScreen: original ? (original.innerText || '').trim() : '',
  };
}"""

READ_RIGHTMOST = """() => {
  let worst = {right: 0, sel: ''};
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (getComputedStyle(el).visibility === 'hidden') continue;
    if (r.right > worst.right) {
      worst = {right: r.right,
               sel: el.tagName.toLowerCase() + '.' + (el.className || '').toString().slice(0, 60)};
    }
  }
  return worst;
}"""


def _api(path: str) -> dict:
    req = urllib.request.Request(API + path, headers={"x-user-id": "demo-user"})
    with urllib.request.urlopen(req) as res:
        return dict(json.load(res))


def main() -> int:
    report: dict[str, object] = {}
    errors: list[str] = []
    # 浏览器给每一发 4xx 记一条 console error，而**那条消息里没有 URL**。
    # 只数条数的话，「28 条 404」说不出是哪一条链断了。所以同时收响应：
    # 判据据此正向断言「这些 404 各自是谁、为什么」，而不是把它们一笔勾销。
    bad: list[dict[str, object]] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        def new_page(**kw):  # type: ignore[no-untyped-def]
            page = browser.new_page(viewport={"width": 1920, "height": 1080}, **kw)
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("response", lambda res: bad.append(
                {"url": res.url, "status": res.status}) if res.status >= 400 else None)
            return page

        # ── 夹具那份：八种块 + 三通道 + 出处
        page = new_page(color_scheme="light")
        page.goto(f"{BASE}?deliverable={FIXTURE}", wait_until="networkidle")
        page.wait_for_selector("[data-block-id]", timeout=60_000)
        page.wait_for_timeout(1500)          # deref 三通道是各自去问的，给它们时间
        fixture = page.evaluate(READ_DOC)
        fixture["channels"] = page.evaluate(READ_CHANNELS)
        fixture["unavailable"] = page.evaluate(READ_UNAVAILABLE)
        cites = page.evaluate(READ_CITES)
        page.screenshot(path=str(OUT / "workbench-preview-1920x1080-light.png"),
                        full_page=True)

        # 屏上那一格 vs 后端那条通道回的东西。
        fact_id = fixture["channels"]["factId"]
        fact = _api(f"/facts/{fact_id}") if fact_id else {}
        fixture["channels"]["backendStatement"] = fact.get("statement", "")
        fixture["channels"]["backendValue"] = (
            "" if fact.get("value") is None else str(fact["value"]))
        report["fixture"] = fixture

        first_cite = cites["firstId"]
        cite = _api(f"/citations/{first_cite}") if first_cite else {}
        cites["backendQuoteSpan"] = cite.get("quote_span", "")
        report["citations"] = cites
        report["rightmostEdge"] = page.evaluate(READ_RIGHTMOST)["right"]
        report["rightmostSelector"] = page.evaluate(READ_RIGHTMOST)["sel"]
        report["vw"] = page.evaluate("innerWidth")
        page.close()

        # ── 真产物 + 它那条作业的事件流（块一块一块到）
        page = new_page(color_scheme="light")
        page.goto(f"{BASE}?deliverable={REAL}&job={REAL_JOB}", wait_until="networkidle")
        page.wait_for_selector("[data-block-id]", timeout=60_000)
        page.wait_for_timeout(2000)
        real = page.evaluate(READ_DOC)
        real["unavailable"] = page.evaluate(READ_UNAVAILABLE)
        report["real"] = real
        report["stream"] = {
            "arrived": len(real["arrived"]),
            "arrivedIds": real["arrived"],
            "deliverableBlockIds": real["ids"],
            "progressOnScreen": real["progressOnScreen"],
        }
        page.close()

        # ── 阴性对照：往答复里塞一个未知块型
        page = new_page(color_scheme="light")

        def inject_unknown(route):  # type: ignore[no-untyped-def]
            res = route.fetch()
            body = res.json()
            body["blocks"] = list(body["blocks"]) + [{
                "block_id": "b-probe-unknown", "deliverable_id": FIXTURE,
                "section_id": "probe", "order": 999, "type": "hologram",
                "content": {"kind": "hologram"}, "claim_ids": [], "fact_ids": [],
                "author": "system", "revision": 1, "locked": False,
                "user_modified": False, "needs_review": False,
                "review_reason": None, "review_severity": None,
            }]
            route.fulfill(response=res, json=body)

        page.route("**/blocks", inject_unknown)
        page.goto(f"{BASE}?deliverable={FIXTURE}", wait_until="networkidle")
        page.wait_for_selector("[data-block-id]", timeout=60_000)
        page.wait_for_timeout(800)
        doc = page.evaluate(READ_DOC)
        report["unknown"] = {
            "noticeCount": len(doc["unknown"]),
            "noticeText": doc["unknown"][0]["text"] if doc["unknown"] else "",
            "noticeNamesTheType": bool(
                doc["unknown"] and "hologram" in doc["unknown"][0]["text"]),
            "knownStillRendered": doc["blockCount"],
        }
        page.close()

        dark = new_page(color_scheme="dark")
        dark.goto(f"{BASE}?deliverable={FIXTURE}", wait_until="networkidle")
        dark.wait_for_selector("[data-block-id]", timeout=60_000)
        dark.wait_for_timeout(1200)
        dark.screenshot(path=str(OUT / "workbench-preview-1920x1080-dark.png"),
                        full_page=True)
        dark.close()
        browser.close()

    # 4xx 逐条归属：`GET /hints/`（**空 hints_ref**）是真产物里那 5 个
    # `gap_notice` 块问出来的——那块提示自己是空的，单
    # `docs/blocked/REAL-GAP-NOTICES-HAVE-NO-HINTS-REF.md`。
    report["badResponses"] = bad
    report["badPaths"] = sorted({
        str(row["url"]).split("127.0.0.1:8000")[-1].split("localhost:8000")[-1]
        for row in bad})
    report["errors"] = errors
    (OUT / "preview.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    fx = dict(report["fixture"])  # type: ignore[arg-type]
    print(f"夹具 {fx['blockCount']} 块 · 类型 {sorted(set(fx['types']))}")
    print(f"三通道 {fx['channels']['cells']} 格 · 各一 {fx['channels']['everyCellHasExactlyOneChannel']}")
    print(f"出处 {report['citations']['count']} 条 · 原文 {report['citations']['originalOnScreen'][:40]}")
    print(f"真产物 {report['real']['blockCount']} 块 · 类型 {sorted(set(report['real']['types']))}")
    print(f"事件流到达 {report['stream']['arrived']} 块 · 屏上有进度 {report['stream']['progressOnScreen']}")
    print(f"未知块 {report['unknown']['noticeCount']} 条 · 点名 {report['unknown']['noticeNamesTheType']}")
    print(f"报错 {len(errors)} · 最右 {report['rightmostEdge']}/{report['vw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
