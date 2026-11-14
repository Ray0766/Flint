"""WB-03-a 取证：真浏览器 · 真栈 · 中栏形状 + 真提交 + 真答复上屏。

跑法（playwright 恒在项目外的 `C:\\pwenv`）：

    C:\\pwenv\\Scripts\\python.exe tools/ui_probe_wb_generate.py

产出 `.ui-probe/wb/generate.json` + 两张截图。

## 这份取证量的是三件事

1. **形状**照蓝本：消息区 `flex:1` 自己滚、输入区钉在底下、托盘在两者之间；
2. **发出去的那一发请求**里的卡 id 与假设，与屏上列的、输入框里打的**逐字相同**；
3. **答复回来之后**屏上说的就是服务端说的那句话，且**没有任何一处还在转**。

第 2 条要拦真实请求（`page.on("request")`），不是看屏上写了什么——
屏上写「已提交」而请求发到别处去了，只看屏是看不出来的。
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
HYPOTHESIS = "这两条热点是否指向同一波注意力迁移，能不能支撑一份可执行的内容策划"

# 中栏三块的几何 + 消息区滚动那一层的 `overflow-y`。
READ_SHAPE = """() => {
  const px = (el) => el.getBoundingClientRect();
  const chat = document.querySelector('[data-wb-col=chat]');
  const messages = document.querySelector('[data-wb-scroll=chat]');
  const foot = document.querySelector('[data-wb-foot=chat]');
  const tray = document.querySelector('[data-wb-tray]');
  const input = document.querySelector('[data-wb-input]');
  return {
    chatHeight: px(chat).height,
    messagesHeight: px(messages).height,
    messagesBottom: px(messages).bottom,
    messagesOverflowY: getComputedStyle(messages).overflowY,
    footHeight: px(foot).height,
    footTop: px(foot).top,
    trayTop: px(tray).top,
    trayBottom: px(tray).bottom,
    inputTop: px(input).top,
  };
}"""

READ_CHAT = """() => {
  const box = document.querySelector('[data-wb-chat]');
  const rows = [...document.querySelectorAll('[data-wb-msg]')];
  const kindOf = (r) => r.getAttribute('data-wb-msg-kind');
  // **终态那一条 = 最后一条 receipt/failure**，不是最后一条消息。
  // 成了之后屏上还会跟一条 `notice`（「下一步还没接上」），
  // 拿最后一行当终态的话，读到的是那条告知——而它既不是成也不是败。
  const outcomes = rows.filter(r => ['receipt', 'failure'].includes(kindOf(r)));
  const outcome = outcomes.length ? outcomes[outcomes.length - 1] : null;
  const receipt = rows.find(r => kindOf(r) === 'receipt');
  return {
    pending: box.getAttribute('data-wb-chat-pending') === 'true',
    text: box.innerText,
    kinds: rows.map(kindOf),
    lastKind: rows.length ? kindOf(rows[rows.length - 1]) : null,
    outcomeKind: outcome ? kindOf(outcome) : null,
    outcomeStep: outcome ? outcome.getAttribute('data-wb-msg-step') : null,
    lastStep: rows.length ? rows[rows.length - 1].getAttribute('data-wb-msg-step') : null,
    receiptProject: receipt ? receipt.getAttribute('data-wb-msg-project') : '',
    receiptTopics: (receipt ? receipt.getAttribute('data-wb-msg-topics') || '' : '')
                     .split(' ').filter(Boolean),
    askCards: (rows.find(r => kindOf(r) === 'ask')
               ?.getAttribute('data-wb-msg-cards') || '').split(' ').filter(Boolean),
  };
}"""

# 最右元素的右缘（owner 2026-08-12 的口径）：`fixed` 元素跑到屏外**不会**
# 撑大文档 scrollWidth，于是「零横向溢出」对它恒绿——顶栏那次 390 溢出
# 被判绿了整整一批（docs/blocked/NAV-BAR-OVERFLOWS-AT-390.md）就是这么来的。
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


def main() -> int:
    report: dict[str, object] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="light")
        errors: list[str] = []
        page.on("console",
                lambda m, sink=errors: sink.append(m.text) if m.type == "error" else None)

        sent: list[dict[str, object]] = []
        page.on("request", lambda req, sink=sent: sink.append(
            {"url": req.url, "method": req.method, "body": req.post_data})
            if "/projects/combo" in req.url else None)
        answers: list[dict[str, object]] = []

        def on_response(res, sink=answers):  # type: ignore[no-untyped-def]
            if "/projects/combo" not in res.url:
                return
            try:
                body = res.json()
            except Exception:                       # noqa: BLE001 —— 非 JSON 也要留证
                body = {"_raw": res.text()[:400]}
            sink.append({"status": res.status, "body": body})

        page.on("response", on_response)

        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector("[data-wb-card]", timeout=60_000)
        page.wait_for_timeout(600)

        # 提交键三态：一张卡没选 → 禁用。
        button: dict[str, object] = {
            "nothingPicked": "disabled" if page.is_disabled("[data-wb-submit]") else "enabled",
        }

        # 选两张热点 → 它们的证据卡列出来。
        ids = page.eval_on_selector_all(
            "[data-wb-card]", "els => els.map(e => e.getAttribute('data-wb-card'))")
        picked = list(ids)[:2]
        for cluster_id in picked:
            page.click(f'[data-wb-pick="{cluster_id}"]')
            page.wait_for_timeout(200)
        page.wait_for_selector("[data-wb-evidence]", timeout=60_000)
        page.wait_for_timeout(800)
        evidence_on_screen = page.eval_on_selector_all(
            "[data-wb-evidence]",
            "els => els.map(e => e.getAttribute('data-wb-evidence'))")

        button["pickedNoHypothesis"] = (
            "disabled" if page.is_disabled("[data-wb-submit]") else "enabled")
        page.fill("[data-wb-input]", HYPOTHESIS)
        page.wait_for_timeout(200)
        button["both"] = "disabled" if page.is_disabled("[data-wb-submit]") else "enabled"
        report["button"] = button

        # 几何**一次量齐**：托盘装进两条热点之后它会长高、把输入区顶上去，
        # 于是消息区变矮。第一版分两个时刻各量一半，量出来「输入区在消息区上方」
        # ——红的是探针自己：拿两个时刻的数去比同一屏。
        shape = dict(page.evaluate(READ_SHAPE))
        page.eval_on_selector("[data-wb-scroll=chat]", "el => el.scrollTop = 400")
        page.wait_for_timeout(200)
        shape["footTopAfterScroll"] = page.evaluate(
            "document.querySelector('[data-wb-foot=chat]').getBoundingClientRect().top")
        report["shape"] = shape

        # ── 真提交
        # 「在等」那一态今天只活几十毫秒（服务端答 503 几乎是立刻的）。
        # **靠掐时间去量它，量到的是运气**：第一版隔 120ms 再问，问到的永远是 False，
        # 于是「屏上有没有在等的表示」这条判据实际上一次都没量到东西。
        # 改成在浏览器里挂一个观察者，**记下它有没有出现过**——与快慢无关。
        page.evaluate("""() => {
          const box = document.querySelector('[data-wb-chat]');
          window.__wbPendingSeen = box.getAttribute('data-wb-chat-pending') === 'true';
          new MutationObserver(() => {
            if (box.getAttribute('data-wb-chat-pending') === 'true') {
              window.__wbPendingSeen = true;
            }
          }).observe(box, {attributes: true, attributeFilter: ['data-wb-chat-pending']});
        }""")
        page.click("[data-wb-submit]")
        # 终态：等待记号消失（NEVER 只等固定秒数就断言，那量的是运气）。
        page.wait_for_function(
            "() => document.querySelector('[data-wb-chat]')"
            ".getAttribute('data-wb-chat-pending') === 'false'",
            timeout=180_000)
        page.wait_for_timeout(300)
        pending_while = page.evaluate("window.__wbPendingSeen === true")
        chat = page.evaluate(READ_CHAT)

        answer = answers[-1] if answers else {}
        body = dict(answer.get("body") or {})
        request = sent[-1] if sent else {}
        payload = json.loads(str(request.get("body") or "{}"))
        report["submit"] = {
            "method": request.get("method"),
            "url": request.get("url"),
            "sentCardIds": payload.get("card_ids", []),
            "sentHypothesis": payload.get("hypothesis", ""),
            "typedHypothesis": HYPOTHESIS,
            "evidenceOnScreen": evidence_on_screen,
            "status": answer.get("status"),
            "serverMessage": body.get("message") or body.get("detail") or "",
            # 成了那一路：服务端回的两样与屏上回执带的两样，判据逐字比。
            "serverProject": str(body.get("project_id") or ""),
            "serverTopics": [str(t) for t in (body.get("topic_ids") or [])],
            "receiptProject": chat["receiptProject"] or "",
            "receiptTopics": chat["receiptTopics"],
            "screenText": chat["text"],
            "pendingWhileWaiting": pending_while,
            "pendingAfterAnswer": chat["pending"],
            # `COMBO-WIRE-01` 之前这一格取的是**最后一条消息**的 kind。
            # 那时链的第一段恒 503，最后一条恒是 `failure`，于是两者恰好相等；
            # 接通之后最后一条是「下一步还没接上」那条 `notice`——
            # **它既不是成也不是败**，而终态判据要的是成或败。
            "terminalKind": chat["outcomeKind"] or chat["lastKind"],
            "terminalStep": chat["outcomeStep"] or "",
            "failedStep": (chat["outcomeStep"] or "") if chat["outcomeKind"] == "failure" else "",
            "askCards": chat["askCards"],
            "kinds": chat["kinds"],
        }

        page.screenshot(path=str(OUT / "workbench-generate-1920x1080-light.png"))

        # 浏览器会把服务端那一句 503 记成一条 console error。**它不是应用报错**——
        # 那正是我们刚刚在屏上如实转述的那个答复。分开两格：
        # `errors` 是应用自己的报错（判据要求它为空），
        # `answerNoise` 是「这一发答复留下的那条」，判据反过来断言**它说的就是那个状态码**——
        # 这样一条别的报错混进来的那天，它进不了这一格，会落在 `errors` 里响。
        status = answer.get("status")
        noise = [line for line in errors
                 if "Failed to load resource" in line and f"status of {status}" in line]
        report["errors"] = [line for line in errors if line not in noise]
        report["answerNoise"] = noise
        report["answerStatus"] = status
        report["scrollW"] = page.evaluate("document.documentElement.scrollWidth")
        report["vw"] = page.evaluate("innerWidth")
        rightmost = page.evaluate(READ_RIGHTMOST)
        report["rightmostEdge"] = rightmost["right"]
        report["rightmostSelector"] = rightmost["sel"]
        page.close()

        dark = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="dark")
        dark.goto(URL, wait_until="networkidle")
        dark.wait_for_selector("[data-wb-card]", timeout=60_000)
        dark.fill("[data-wb-input]", HYPOTHESIS)
        dark.wait_for_timeout(600)
        dark.screenshot(path=str(OUT / "workbench-generate-1920x1080-dark.png"))
        dark.close()
        browser.close()

    (OUT / "generate.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sub = dict(report["submit"])  # type: ignore[arg-type]
    print(f"形状 消息 {report['shape']['messagesHeight']} + 底 {report['shape']['footHeight']}"
          f" = 栏 {report['shape']['chatHeight']}")
    print(f"提交 {sub['method']} {sub['url']} → {sub['status']}")
    print(f"卡 {sub['sentCardIds']} · 屏上 {sub['evidenceOnScreen']}")
    print(f"终态 {sub['terminalKind']} · 等待中 {sub['pendingWhileWaiting']} → "
          f"答复后 {sub['pendingAfterAnswer']}")
    print(f"服务端说：{sub['serverMessage']}")
    print(f"报错 {len(report['errors'])} · 最右 {report['rightmostEdge']}/{report['vw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
