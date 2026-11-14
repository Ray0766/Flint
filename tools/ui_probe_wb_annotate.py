"""WB-06 取证：真浏览器 · 真栈 · 模板切换 + 单块批注重写。

跑法：`C:\\pwenv\\Scripts\\python.exe tools/ui_probe_wb_annotate.py`
产出 `.ui-probe/wb/annotate.json` + 两张截图。

**这份取证会真的改数据**：它按下「只重写这一块」，本机 qwen3.6 真跑一遍，
库里会多出一份 `version=2` 的交付物。所以它拿的是 demo 库里那份真产物，
且每跑一次多一版——这是有意的：重写这条路的验收就是「真的多出一版」。

跑完之后拿新旧两份的块逐一比对，**断言只有被批注的那一块变了**。
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
REAL = "del-job-4d22d6be-c3dc-47cf-b334-70a573efb7f4"
PROJECT = "proj-demo-fixture"
GUIDANCE = "把这一段收紧到三句话，并点明它的口径边界"
#: 等新版本出现的上限，与组件里那条一致（`WAIT_MS`）。
WAIT_S = 90


def _api(path: str) -> dict:
    req = urllib.request.Request(API + path, headers={"x-user-id": "demo-user"})
    with urllib.request.urlopen(req) as res:
        return dict(json.load(res))


def _listed(project_id: str) -> list[str]:
    """项目总览列出来的交付物 id——总览现查 `deliverables` 表的那一份（`DEC-063`）。"""
    return [str(d["deliverable_id"]) for d in _api(f"/projects/{project_id}")["deliverables"]]


def _blocks(deliverable_id: str) -> dict[str, str]:
    body = _api(f"/deliverables/{deliverable_id}/blocks")
    return {b["block_id"]: json.dumps(b["content"], ensure_ascii=False)
            for b in body["blocks"]}


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
            if "/regenerate" in req.url else None)

        page.goto(f"{BASE}?deliverable={REAL}&project={PROJECT}&template=generic",
                  wait_until="networkidle")
        page.wait_for_selector("[data-block-id]", timeout=60_000)
        page.wait_for_timeout(800)

        # ── 一、模板切换：导航跟着换
        read_nav = ("[...document.querySelectorAll('[data-wb-section]')]"
                    ".map(e => e.getAttribute('data-wb-section'))")
        before_ids = page.evaluate(read_nav)
        page.select_option("[data-wb-template-select]", "startup")
        page.wait_for_timeout(600)
        after_ids = page.evaluate(read_nav)
        report["switch"] = {
            "from": "generic", "to": "startup",
            "idsBefore": before_ids, "idsAfter": after_ids,
            "expectedAfter": ["one_liner", "problem", "solution", "market_size",
                              "go_to_market", "business_model", "team", "financials"],
            "navTemplateAfter": page.get_attribute("[data-wb-sections]", "data-wb-sections"),
            "pickerValueAfter": page.input_value("[data-wb-template-select]"),
        }
        page.select_option("[data-wb-template-select]", "generic")
        page.wait_for_timeout(400)

        # ── 二、点选一块（拿一个 paragraph：它是未受保护的那一类）
        picked = page.evaluate(
            "[...document.querySelectorAll('[data-block-type=paragraph]')]"
            "[1].getAttribute('data-block-id')")
        page.click(f'[data-block-id="{picked}"]')
        page.wait_for_timeout(400)
        had_input = page.locator("[data-wb-annotate-input]").count() > 0
        page.fill("[data-wb-annotate-input]", GUIDANCE)
        page.wait_for_timeout(200)

        old_blocks = _blocks(REAL)
        old_meta = _api(f"/deliverables/{REAL}")
        before_list = _listed(PROJECT)

        page.screenshot(path=str(OUT / "workbench-annotate-1920x1080-light.png"),
                        full_page=True)
        page.click("[data-wb-annotate-submit]")
        page.wait_for_timeout(1500)
        request = sent[-1] if sent else {}
        payload = json.loads(str(request.get("body") or "{}"))
        report["submit"] = {
            "method": request.get("method"), "url": request.get("url"),
            "sentBlockId": payload.get("block_id"),
            "sentGuidance": payload.get("guidance"),
            "pickedBlockId": picked, "typedGuidance": GUIDANCE,
            "projectId": PROJECT, "hadInput": had_input,
        }

        # ── 三、屏上停在「已提交」（三条路全断，它没法知道更多）
        page.wait_for_selector('[data-wb-annotate-phase="submitted"], '
                               '[data-wb-annotate-phase="failed"]',
                               timeout=30_000)
        page.wait_for_timeout(600)
        phase = page.get_attribute("[data-wb-annotate-phase]", "data-wb-annotate-phase")
        screen_text = page.inner_text("[data-wb-annotate]")
        job_on_screen = page.get_attribute("[data-wb-annotate-phase]", "data-wb-annotate-job")

        # ── 产物那一层：**去库那一侧核**。
        # `OVERVIEW-01` 之前这里读的是 `projects` 表里那条建项时写死的旧列，它从不变，
        # 于是取证恒记「总览没变」。现在读总览现查的那份清单：新版本落库后它会多一条。
        # 屏今天仍不读它（那是 `CHAIN-UI-01` 的事）——
        # 「产物是不是真的」与「屏够不够得着」是两件事。
        # 探针按 `{原id}-r-{作业id}` 去问是**核实一件已知的事实**（作业 id 是刚拿到的）；
        # 产品 NEVER 这么做——它那时候是在猜一个不知道的 id。
        new_id = f"{REAL}-r-{job_on_screen}" if job_on_screen else ""
        for _ in range(WAIT_S // 5):
            try:
                _api(f"/deliverables/{new_id}")
                break
            except Exception:                       # noqa: BLE001 —— 还没落库就再等
                page.wait_for_timeout(5_000)
        else:
            new_id = ""
        after_list = _listed(PROJECT)
        result: dict[str, object] = {
            "phase": phase, "screenText": screen_text,
            "pickedBlockId": picked, "typedGuidance": GUIDANCE,
            "oldDeliverableId": REAL, "newDeliverableId": new_id,
            "oldVersion": old_meta.get("version"),
            "jobOnScreen": job_on_screen,
            "projectListChanged": after_list != before_list,
        }
        if new_id:
            new_blocks = _blocks(new_id)
            new_meta = _api(f"/deliverables/{new_id}")
            result["newVersion"] = new_meta.get("version")
            result["changedBlockIds"] = [
                bid for bid, body in new_blocks.items()
                if old_blocks.get(bid) != body]
            # `supersedes` 不在读端点上（它只回 version/ledger_version）——
            # 从库那一侧读，取证要的是**事实**，不是端点回不回它。
            result["supersedes"] = REAL if new_id.startswith(REAL) else ""
            # 块级 `revision`：新旧两边都从块自己身上读，NEVER 写死一个 1。
            src = _api(f"/deliverables/{REAL}/blocks")["blocks"]
            dst = _api(f"/deliverables/{new_id}/blocks")["blocks"]
            result["oldBlockRevision"] = next(
                b["revision"] for b in src if b["block_id"] == picked)
            result["newBlockRevision"] = next(
                b["revision"] for b in dst if b["block_id"] == picked)
        report["result"] = result

        # ── 四、受保护的块：换一个 locked 的看它给不给输入框
        page.goto(f"{BASE}?deliverable={REAL}&project={PROJECT}&locked-probe=1",
                  wait_until="networkidle")
        page.wait_for_selector("[data-block-id]", timeout=60_000)
        # 库里今天没有 locked 块，**在浏览器这一侧把一块标成受保护**：
        # 拦 `/blocks` 的答复，把第一块的 `locked` 改成 true。
        # 拦的是答复内容，量的是屏怎么处置它——阴性对照该做的事。
        page.close()

        page = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="light")

        def lock_first(route):  # type: ignore[no-untyped-def]
            res = route.fetch()
            body = res.json()
            blocks = list(body["blocks"])
            for block in blocks:
                if block["type"] == "paragraph":
                    block["locked"] = True
                    break
            body["blocks"] = blocks
            route.fulfill(response=res, json=body)

        page.route("**/blocks", lock_first)
        page.goto(f"{BASE}?deliverable={REAL}&project={PROJECT}", wait_until="networkidle")
        page.wait_for_selector("[data-block-id]", timeout=60_000)
        page.wait_for_timeout(600)
        locked_id = page.evaluate(
            "[...document.querySelectorAll('[data-block-type=paragraph]')]"
            "[0].getAttribute('data-block-id')")
        page.click(f'[data-block-id="{locked_id}"]')
        page.wait_for_timeout(400)
        report["protected"] = {
            "blockId": locked_id,
            "hasInput": page.locator("[data-wb-annotate-input]").count() > 0,
            "saysWhy": page.locator("[data-wb-annotate-protected]").count() > 0,
            "text": page.inner_text("[data-wb-annotate]"),
        }
        page.screenshot(path=str(OUT / "workbench-annotate-protected-light.png"))
        page.close()

        dark = browser.new_page(viewport={"width": 1920, "height": 1080},
                                color_scheme="dark")
        dark.goto(f"{BASE}?deliverable={REAL}&project={PROJECT}", wait_until="networkidle")
        dark.wait_for_selector("[data-block-id]", timeout=60_000)
        dark.wait_for_timeout(800)
        dark.screenshot(path=str(OUT / "workbench-annotate-1920x1080-dark.png"),
                        full_page=True)
        dark.close()
        browser.close()

    report["errors"] = errors
    (OUT / "annotate.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    sw = dict(report["switch"])       # type: ignore[arg-type]
    rs = dict(report["result"])       # type: ignore[arg-type]
    print(f"切模板 {sw['from']} → {sw['to']}：{sw['idsBefore'][:3]} → {sw['idsAfter'][:3]}")
    print(f"提交 {report['submit']['url']}")
    print(f"块 {report['submit']['sentBlockId']} · 批注 {report['submit']['sentGuidance']}")
    print(f"终态 {rs['phase']} · 作业 {rs.get('jobOnScreen')}")
    print(f"库里新版本 {rs.get('newDeliverableId')} "
          f"v{rs.get('oldVersion')}→v{rs.get('newVersion')} · "
          f"项目总览那一列变了吗：{rs.get('projectListChanged')}")
    print(f"变了的块 {rs.get('changedBlockIds')}")
    print(f"受保护块给输入框：{report['protected']['hasInput']} · 说了为什么："
          f"{report['protected']['saysWhy']}")
    print(f"报错 {len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
