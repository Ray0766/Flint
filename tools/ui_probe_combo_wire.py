"""COMBO-WIRE-01 取证：真浏览器 · 真栈 · owner 撞到的那条路走一遍。

跑法（playwright 恒在项目外的 `C:\\pwenv`）：

    C:\\pwenv\\Scripts\\python.exe tools/ui_probe_combo_wire.py

产出 `.ui-probe/combo_wire/e2e.json` + 六张截图（每一步一张）。

## 这一趟量的是六步

| 步 | 屏 | 量什么 |
|---|---|---|
| plaza | `/plaza` | 广场自己那条多选（≥2 张 + 一句假设 → 建项按钮可点） |
| picked | `/workbench` | 左栏选 3 张热点 → 中栏「本次组合」列的就是那 3 条 |
| typed | `/workbench` | 打一句假设 → 提交键从禁用变可点 |
| receipt | `/workbench` | **按下去**：真请求真答复，不再 503 |
| topics | `/projects/{id}/topics` | 回来的那几个主题**在库里查得到** |
| doc | `/workbench?deliverable=…` | 右栏渲染真 Block（块型落在冻结件那八枚里） |

## 两处 NEVER

- **右栏那一份不是本次 combo 的产物**，`e2e.json` 里如实写着这件事
  （`doc.note`）。链的后两段今天还断着（分析要真实网络 · `analysis_id`
  没有回路），两条各有单。**NEVER 把「渲染得出真 Block」写成「这条链通了」**；
- 卡 id / 主题 id 一律从**真请求真答复**里取，NEVER 从屏上的文字反推。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from playwright.sync_api import sync_playwright

OUT = pathlib.Path(".ui-probe/combo_wire")
OUT.mkdir(parents=True, exist_ok=True)
WEB = "http://localhost:3000"
API = "http://localhost:8000"
HYPOTHESIS = "这三条热点是否指向同一波注意力迁移，能不能支撑一份可执行的内容策划"
VIEW = {"width": 1920, "height": 1080}

#: 右栏拿来渲染的那一份：本机 demo 库里**此前真跑出来**的一份（30 块）。
#: NEVER 用 `del-demo-fixture-report`（那是启动脚本灌的夹具，
#: 拿它冒充「你的计划书」正是 `DEC-012` 判死过的那只手）。
REAL_DELIVERABLE = "del-job-e7f1b902-90bb-4547-9345-d02ed076af01"

#: combo 要真调本地 35b 出 6 个主题，分钟级。**NEVER 只等固定秒数就断言**
#: ——那量的是运气；这里等的是「等待记号消失」这件事本身。
SUBMIT_TIMEOUT_MS = 900_000

READ_CHAT = """() => {
  const box = document.querySelector('[data-wb-chat]');
  const rows = [...document.querySelectorAll('[data-wb-msg]')];
  const receipt = rows.find(r => r.getAttribute('data-wb-msg-kind') === 'receipt');
  return {
    pending: box.getAttribute('data-wb-chat-pending') === 'true',
    text: box.innerText,
    kinds: rows.map(r => r.getAttribute('data-wb-msg-kind')),
    receiptProject: receipt ? receipt.getAttribute('data-wb-msg-project') : '',
    receiptTopics: (receipt ? receipt.getAttribute('data-wb-msg-topics') || '' : '')
                     .split(' ').filter(Boolean),
  };
}"""


def main() -> int:
    report: dict[str, object] = {}
    errors: list[str] = []
    #: 每一发 4xx/5xx 都**点名**：浏览器那句 `Failed to load resource` 只说状态码，
    #: 一屏上有九条时它们看起来一模一样，而九条的归属可以是九张不同的单。
    refused: list[dict[str, object]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport=VIEW, color_scheme="light")
        page.on("console",
                lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("response", lambda res: refused.append(
            {"url": res.url, "status": res.status, "screen": page.url})
            if res.status >= 400 else None)

        # ── ① 广场：它自己那条多选（选 3 张 + 一句假设 → 建项按钮可点）
        page.goto(f"{WEB}/plaza", wait_until="networkidle")
        page.wait_for_selector('[data-testid="plaza-combo-bar"]', timeout=60_000)
        boxes = page.query_selector_all('[data-testid="plaza-card-checkbox"]')
        for box in boxes[:3]:
            box.click()
            page.wait_for_timeout(150)
        page.fill('[data-testid="plaza-combo-hypothesis"]', HYPOTHESIS)
        page.wait_for_timeout(200)
        report["plaza"] = {
            "cardsOnScreen": len(page.query_selector_all('[data-testid="hotspot-card"]')),
            "selectedCount": page.get_attribute(
                '[data-testid="plaza-combo-bar"]', "data-selected-count"),
            "comboState": page.get_attribute(
                '[data-testid="plaza-combo-hint"]', "data-combo-state"),
            "buildEnabled": not page.is_disabled('[data-testid="plaza-combo-build"]'),
        }
        page.screenshot(path=str(OUT / "combo-plaza-1920x1080-light.png"))

        # ── ②③ 工作台：左栏选 3 张 → 托盘 → 打一句假设
        sent: list[dict[str, object]] = []
        page.on("request", lambda req: sent.append(
            {"url": req.url, "method": req.method, "body": req.post_data})
            if "/projects/combo" in req.url else None)
        answers: list[dict[str, object]] = []

        def on_response(res) -> None:  # type: ignore[no-untyped-def]
            if "/projects/combo" not in res.url:
                return
            try:
                body = res.json()
            except Exception:                      # noqa: BLE001 —— 非 JSON 也要留证
                body = {"_raw": res.text()[:400]}
            answers.append({"status": res.status, "body": body})

        page.on("response", on_response)

        page.goto(f"{WEB}/workbench", wait_until="networkidle")
        page.wait_for_selector("[data-wb-card]", timeout=60_000)
        page.wait_for_timeout(600)
        button_before_pick = (
            "disabled" if page.is_disabled("[data-wb-submit]") else "enabled")
        ids = page.eval_on_selector_all(
            "[data-wb-card]", "els => els.map(e => e.getAttribute('data-wb-card'))")
        picked = list(ids)[:3]
        for cluster_id in picked:
            page.click(f'[data-wb-pick="{cluster_id}"]')
            page.wait_for_timeout(250)
        page.wait_for_selector("[data-wb-evidence]", timeout=60_000)
        page.wait_for_timeout(900)
        report["pick"] = {
            "picked": picked,
            "trayClusters": page.eval_on_selector_all(
                "[data-wb-tray-id]",
                "els => els.map(e => e.getAttribute('data-wb-tray-id'))"),
            "trayCount": page.get_attribute("[data-wb-tray]", "data-wb-tray-count"),
            "evidenceCards": page.eval_on_selector_all(
                "[data-wb-evidence]",
                "els => els.map(e => e.getAttribute('data-wb-evidence'))"),
        }
        page.screenshot(path=str(OUT / "combo-picked-1920x1080-light.png"))

        button_no_text = "disabled" if page.is_disabled("[data-wb-submit]") else "enabled"
        page.fill("[data-wb-input]", HYPOTHESIS)
        page.wait_for_timeout(250)
        report["typed"] = {
            "hypothesis": HYPOTHESIS,
            "buttonNothingPicked": button_before_pick,
            "buttonPickedNoHypothesis": button_no_text,
            "buttonBoth": "disabled" if page.is_disabled("[data-wb-submit]") else "enabled",
        }
        page.screenshot(path=str(OUT / "combo-typed-1920x1080-light.png"))

        # ── ④ 按下去。「在等」那一态靠掐时间量到的是运气 → 挂观察者。
        page.evaluate("""() => {
          const box = document.querySelector('[data-wb-chat]');
          window.__wbPendingSeen = box.getAttribute('data-wb-chat-pending') === 'true';
          new MutationObserver(() => {
            if (box.getAttribute('data-wb-chat-pending') === 'true') {
              window.__wbPendingSeen = true;
            }
          }).observe(box, {attributes: true, attributeFilter: ['data-wb-chat-pending']});
        }""")
        started = time.monotonic()
        page.click("[data-wb-submit]")
        page.wait_for_function(
            "() => document.querySelector('[data-wb-chat]')"
            ".getAttribute('data-wb-chat-pending') === 'false'",
            timeout=SUBMIT_TIMEOUT_MS)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        page.wait_for_timeout(400)
        chat = page.evaluate(READ_CHAT)
        answer = answers[-1] if answers else {}
        body = dict(answer.get("body") or {})
        request = sent[-1] if sent else {}
        payload = json.loads(str(request.get("body") or "{}"))
        topic_ids = [str(t) for t in (body.get("topic_ids") or [])]
        project_id = str(body.get("project_id") or "")
        report["submit"] = {
            "method": request.get("method"),
            "url": request.get("url"),
            "sentCardIds": payload.get("card_ids", []),
            "sentHypothesis": payload.get("hypothesis", ""),
            "status": answer.get("status"),
            "projectId": project_id,
            "topicIds": topic_ids,
            "degraded": body.get("degraded"),
            "serverMessage": body.get("message") or body.get("detail") or "",
            "screenText": chat["text"],
            "screenProject": chat["receiptProject"],
            "screenTopics": chat["receiptTopics"],
            "pendingWhileWaiting": page.evaluate("window.__wbPendingSeen === true"),
            "pendingAfterAnswer": chat["pending"],
            "kinds": chat["kinds"],
            "terminalKind": "receipt" if "receipt" in chat["kinds"] else (
                chat["kinds"][-1] if chat["kinds"] else None),
            "elapsedMs": elapsed_ms,
        }
        page.screenshot(path=str(OUT / "combo-receipt-1920x1080-light.png"))

        # ── ⑤ 主题：屏上列的 vs 端点（= 库）里真有的
        in_db: list[str] = []
        if project_id:
            page.goto(f"{WEB}/projects/{project_id}/topics", wait_until="networkidle")
            page.wait_for_timeout(1200)
            api = page.request.get(f"{API}/projects/{project_id}/topics",
                                   headers={"x-user-id": "demo-user"})
            served = api.json() if api.ok else {}
            in_db = [str(t.get("topic_id")) for t in (served.get("topics") or [])]
        report["topics"] = {
            "projectId": project_id,
            "screenTopicIds": page.eval_on_selector_all(
                "[data-topic-id]",
                "els => els.map(e => e.getAttribute('data-topic-id'))"),
            "inDatabase": len(in_db),
            "databaseTopicIds": in_db,
        }
        page.screenshot(path=str(OUT / "combo-topics-1920x1080-light.png"))

        # ── ⑥ 右栏：真 Block（**不是本次 combo 的产物**，见文件头）
        page.goto(f"{WEB}/workbench?deliverable={REAL_DELIVERABLE}",
                  wait_until="networkidle")
        page.wait_for_selector("[data-block-type]", timeout=60_000)
        page.wait_for_timeout(600)
        report["doc"] = {
            "deliverableId": page.get_attribute(
                "[data-wb-preview]", "data-wb-doc-state") and REAL_DELIVERABLE,
            "docState": page.get_attribute("[data-wb-preview]", "data-wb-doc-state"),
            "blockCount": len(page.query_selector_all("[data-block-type]")),
            "blockTypes": sorted(set(page.eval_on_selector_all(
                "[data-block-type]",
                "els => els.map(e => e.getAttribute('data-block-type'))"))),
            "isFixture": REAL_DELIVERABLE == "del-demo-fixture-report",
            "note": ("这一份是本机库里此前真跑出来的交付物，"
                     "**不是本次 combo 的产物**——链的后两段（分析 / 成文）今天还断着，"
                     "两条各有单。"),
        }
        page.screenshot(path=str(OUT / "combo-doc-1920x1080-light.png"))

        # 浏览器给每一发 4xx/5xx 记一条 `Failed to load resource`——**那不是应用报错**，
        # 它是「某个端点如实拒绝了」在控制台里的影子。两格分开：
        #   `errors`      = 应用自己的报错（判据要求它为空）；
        #   `refusedCalls`= 每一发被拒的请求，**带 URL 与状态码**，逐条可归属。
        # 只数个数的话，九条长得一模一样，而它们的归属可以是九张不同的单。
        report["errors"] = [line for line in errors
                            if "Failed to load resource" not in line]
        report["resourceNoiseCount"] = len(
            [line for line in errors if "Failed to load resource" in line])
        report["refusedCalls"] = refused
        page.close()
        browser.close()

    (OUT / "e2e.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sub = dict(report["submit"])  # type: ignore[arg-type]
    pick = dict(report["pick"])   # type: ignore[arg-type]
    print(f"广场 {report['plaza']}")
    print(f"选 {pick['picked']} → 托盘 {pick['trayClusters']}"
          f" · 证据 {len(pick['evidenceCards'])} 张")            # type: ignore[arg-type]
    print(f"提交 {sub['method']} {sub['url']} → {sub['status']}"
          f"（{sub['elapsedMs']} ms）")
    print(f"项目 {sub['projectId']} · 主题 {len(sub['topicIds'])} 条")  # type: ignore[arg-type]
    print(f"主题页 {report['topics']}")
    print(f"右栏 {report['doc']['blockCount']} 块 {report['doc']['blockTypes']}")
    print(f"应用报错 {len(report['errors'])}"                   # type: ignore[arg-type]
          f" · 被拒请求 {len(report['refusedCalls'])}")          # type: ignore[arg-type]
    for call in report["refusedCalls"]:                         # type: ignore[attr-defined]
        print(f"  {call['status']} {call['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
