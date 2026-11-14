"""前端视觉探针：给没有眼睛的执行者一双眼睛。

无头浏览器打开真实运行的前端，产出截图 + 客观量测（页高 / 横向溢出 / 控制台报错 /
主题 token 实际取值），让"它长什么样"从口头描述变成可复看的证据。

**边界（重要）**
- playwright **不是本项目依赖**，NEVER 写进 requirements.lock / pyproject.toml /
  package.json。它装在项目外的隔离环境 `C:\\pwenv`，只服务开发与复核。
- 本脚本**只读页面**：不点按钮、不提交表单、不写数据库。
- 截图产物写 `.ui-probe/`（已在 .gitignore 之外的临时目录语义，不入库）。

**前置**（缺失时本脚本会打印这两行并退出非零，NEVER 静默通过）
    python -m venv C:\\pwenv
    C:\\pwenv\\Scripts\\python.exe -m pip install playwright
    C:\\pwenv\\Scripts\\python.exe -m playwright install chromium

**跑法**（用隔离环境的解释器，不是项目 .venv）
    C:\\pwenv\\Scripts\\python.exe scripts/ui_probe.py                    # 默认两屏两主题
    C:\\pwenv\\Scripts\\python.exe scripts/ui_probe.py --url http://localhost:3001/plaza
    C:\\pwenv\\Scripts\\python.exe scripts/ui_probe.py --theme light --mobile-only
    C:\\pwenv\\Scripts\\python.exe scripts/ui_probe.py --tokens            # 附带 token 取值对照

看图：产物在 .ui-probe/ 下，用 Read 工具直接读 png 即可。

## EYE-01：从「给人看」到「给机器判」

原来这个脚本只能给人看——它把观测打印成人读的行，`problems` 计数混在里面。
当 verify_cmd 用需要三样东西，本次补齐：

    --json                     结构稳定的观测报告（schema 见 `SCHEMA`），断言消费方照着写
    --assert <判据>            可重复；任一不满足 → 退出码 1，并**逐条点名**是哪一条
    --selector <css>           把某个选择器的 boundingBox 也量进报告（F-09 那个占 0 像素的
                               空 span 就是这么现形的：DOM 里有、宽高是 0）

判据三种（`parse_criterion`）：

    no-console-errors          该屏控制台 error 数 == 0
    no-horizontal-overflow     该屏无横向溢出
    visible:<css 选择器>       该选择器存在**且宽高均 >0**

**判据对每一屏分别判**（主题 × 视口 × 页面），不是只判第一屏——横向溢出最容易出现在移动端。

## 三种红互不冒充（本脚本最要紧的一条约定）

    0  一切正常
    1  判据不满足 / 观测到问题（横向溢出、控制台 error）
    2  playwright 不在当前解释器里          → 修法：用 C:\\pwenv 的解释器跑
    3  **前端没起**（连接被拒）              → 修法：start-demo.bat

前端没起时判据当然全不满足，但那时候报「选择器不可见」会把人送去改一个并不存在的 bug。
**修法完全不同的两件事，退出码必须不同**，所以 3 的判定优先于 1。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".ui-probe"

DEFAULT_URLS = [
    ("home", "http://localhost:3001/"),
    ("report", "http://localhost:3001/deliverables/del-demo-fixture-report"),
]
VIEWPORTS = {"desktop": (1440, 900), "mobile": (390, 844)}

# 双主题下要盯的语义 token（转浅色后两套值必须真的不同，否则就是没翻转）
WATCH_TOKENS = [
    "--surface", "--ink", "--ink-2", "--ink-3", "--rule",
    "--spark", "--background", "--foreground", "--card", "--border",
]


SCHEMA = "ui-probe/1"

EXIT_OK = 0
EXIT_ASSERT_FAILED = 1
EXIT_NO_PLAYWRIGHT = 2
EXIT_FRONTEND_DOWN = 3

# 「连不上」的形态。playwright 的报错文本因平台而异，故按子串认。
# NEVER 把超时算进来：超时可能是页面自己卡住了，那是真 bug，不是「没起」。
_DOWN_MARKERS = ("ERR_CONNECTION_REFUSED", "ECONNREFUSED", "ERR_CONNECTION_RESET",
                 "ERR_EMPTY_RESPONSE", "ERR_ADDRESS_UNREACHABLE")


def looks_like_frontend_down(message: str) -> bool:
    """这条打不开是「前端没起」还是「页面自己坏了」——两者的修法完全不同。"""
    return any(marker in message for marker in _DOWN_MARKERS)


def parse_criterion(text: str) -> str:
    """判据文本归一。认不出的当场报错，NEVER 当成通过。

    默默跳过一条不认识的判据，等于让写判据的人以为自己守住了某件事——
    而他连拼错了都不会知道。
    """
    value = text.strip()
    if value in ("no-console-errors", "no-horizontal-overflow"):
        return value
    if value.startswith("visible:") and value[len("visible:"):].strip():
        return value
    raise ValueError(
        f"认不出的判据 {text!r}。可用：no-console-errors / no-horizontal-overflow / visible:<css>"
    )


def _page_label(page: dict[str, Any]) -> str:
    return f"{page['name']}/{page['theme']}/{page['viewport']}"


def _judge(page: dict[str, Any], criterion: str) -> tuple[bool, str]:
    if criterion == "no-console-errors":
        count = page["console_error_count"]
        return count == 0, f"控制台 error {count} 条"
    if criterion == "no-horizontal-overflow":
        if not page["horizontal_overflow"]:
            return True, f"scrollWidth {page['scroll_width']} ≤ 视口 {page['viewport_width']}"
        return False, (f"横向溢出：scrollWidth {page['scroll_width']} > "
                       f"视口 {page['viewport_width']}")
    selector = criterion[len("visible:"):].strip()
    seen = page["selectors"].get(selector)
    if seen is None or not seen["present"]:
        return False, f"找不到选择器 {selector}"
    if seen["width"] > 0 and seen["height"] > 0:
        return True, f"{selector} 宽高 {seen['width']}×{seen['height']}"
    return False, (f"{selector} 在 DOM 里但宽高 {seen['width']}×{seen['height']}——"
                   "用户看不见它")


def evaluate(pages: list[dict[str, Any]], criteria: list[str]) -> list[dict[str, Any]]:
    """每条判据 × 每一屏，逐个判。只判第一屏是这类工具最常见的偷懒方式。"""
    results: list[dict[str, Any]] = []
    for criterion in criteria:
        for page in pages:
            ok, detail = _judge(page, criterion)
            results.append({
                "criterion": criterion, "page": _page_label(page),
                "ok": ok, "detail": detail,
            })
    return results


def build_report(pages: list[dict[str, Any]], *, criteria: list[str],
                 frontend_down: bool = False) -> dict[str, Any]:
    """把观测与判定合成一份**结构稳定**的报告（键集即契约，改键就是破约）。"""
    assertions = evaluate(pages, criteria)
    problems = sum(
        page["console_error_count"] + (1 if page["horizontal_overflow"] else 0)
        for page in pages
    )
    return {
        "schema": SCHEMA,
        "pages": pages,
        "problems": problems,
        "assertions": assertions,
        "ok": not frontend_down and problems == 0 and all(a["ok"] for a in assertions),
        "frontend_down": frontend_down,
    }


def exit_code(report: dict[str, Any]) -> int:
    """前端没起的判定**优先**于判据结论（模块 docstring「三种红互不冒充」）。"""
    if report["frontend_down"]:
        return EXIT_FRONTEND_DOWN
    return EXIT_OK if report["ok"] else EXIT_ASSERT_FAILED


def _require_playwright() -> object:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print(
            "playwright 不在当前解释器里。请用隔离环境跑本脚本：\n"
            "    C:\\pwenv\\Scripts\\python.exe -m pip install playwright\n"
            "    C:\\pwenv\\Scripts\\python.exe -m playwright install chromium\n"
            "并用 C:\\pwenv\\Scripts\\python.exe 执行本文件（NEVER 装进项目 .venv）。",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    return sync_playwright


def probe(urls: list[tuple[str, str]], themes: list[str], viewports: list[str],
          dump_tokens: bool, selectors: list[str] | None = None,
          quiet: bool = False) -> tuple[list[dict[str, Any]], bool]:
    """跑一遍观测。返回 (每屏观测, 前端是否没起)。

    `quiet` 给 `--json` 用：人读的行会污染 JSON 输出，而 JSON 是给机器吃的。
    """
    sync_playwright = _require_playwright()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    watch = selectors or []
    pages_out: list[dict[str, Any]] = []
    frontend_down = False

    def say(line: str) -> None:
        if not quiet:
            print(line)

    with sync_playwright() as p:  # type: ignore[operator]
        browser = p.chromium.launch()
        for theme in themes:
            for vp in viewports:
                w, h = VIEWPORTS[vp]
                ctx = browser.new_context(
                    viewport={"width": w, "height": h},
                    color_scheme=theme,          # 驱动 prefers-color-scheme
                )
                # next-themes 惯例：localStorage.theme 决定手动覆盖
                ctx.add_init_script(
                    f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}")
                for name, url in urls:
                    page = ctx.new_page()
                    errs: list[str] = []
                    # 用默认参数把 errs 绑进闭包：它每轮循环都会被重新赋值，
                    # 直接捕获外层名字会让处理器写进后一轮的列表（ruff B023）。
                    page.on("console", lambda m, sink=errs: sink.append(
                        f"{m.type}: {m.text}") if m.type == "error" else None)
                    page.on("pageerror", lambda e, sink=errs: sink.append(f"pageerror: {e}"))
                    try:
                        page.goto(url, wait_until="networkidle", timeout=60000)
                    # playwright 的失败型别较杂（超时/协议/连接），探针只需如实记一笔并继续，
                    # 故这里刻意宽捕获。
                    except Exception as exc:  # noqa: BLE001
                        down = looks_like_frontend_down(str(exc))
                        frontend_down = frontend_down or down
                        say(f"[{theme}/{vp}] {name}: 打不开 {url} -> "
                            f"{type(exc).__name__}"
                            f"{'（前端没起）' if down else ''}")
                        page.close()
                        continue
                    page.wait_for_timeout(2500)      # 等客户端取数落定

                    shot = OUT_DIR / f"{name}-{theme}-{vp}.png"
                    page.screenshot(path=str(shot), full_page=True)

                    m = page.evaluate(
                        "() => ({h: document.body.scrollHeight,"
                        " w: document.body.scrollWidth,"
                        " ow: window.innerWidth,"
                        " cls: document.documentElement.className,"
                        " ds: document.documentElement.dataset.theme || ''})")
                    overflow = m["w"] > m["ow"] + 1
                    flag = "  <== 横向溢出" if overflow else ""
                    say(f"[{theme}/{vp}] {name}: {shot.name}  页高={m['h']}px"
                        f"  html.class={m['cls']!r} data-theme={m['ds']!r}{flag}")
                    for e in errs[:5]:
                        say(f"    控制台 {e[:120]}")

                    vals: dict[str, str] = {}
                    if dump_tokens:
                        vals = page.evaluate(
                            "(names) => { const s = getComputedStyle("
                            "document.documentElement);"
                            " return Object.fromEntries(names.map("
                            "n => [n, s.getPropertyValue(n).trim()])); }",
                            WATCH_TOKENS)
                        for k, v in vals.items():
                            say(f"    token {k:<14} = {v or '(未定义)'}")

                    boxes: dict[str, dict[str, Any]] = {}
                    for sel in watch:
                        # boundingBox() 对不可见元素返回 None——F-09 那个空 span 就落在这里：
                        # DOM 里查得到，量出来是 0×0，用户什么都看不见。
                        found = page.query_selector(sel)
                        box = found.bounding_box() if found is not None else None
                        boxes[sel] = {
                            "present": found is not None,
                            "width": float(box["width"]) if box else 0.0,
                            "height": float(box["height"]) if box else 0.0,
                            "visible": bool(box) and box["width"] > 0 and box["height"] > 0,
                        }
                        say(f"    选择器 {sel} -> {boxes[sel]}")

                    pages_out.append({
                        "name": name, "url": url, "theme": theme, "viewport": vp,
                        "screenshot": shot.name,
                        "page_height": m["h"], "scroll_width": m["w"],
                        "viewport_width": m["ow"], "horizontal_overflow": overflow,
                        "console_errors": errs, "console_error_count": len(errs),
                        "html_class": m["cls"], "data_theme": m["ds"],
                        "tokens": vals, "selectors": boxes,
                    })
                    page.close()
                ctx.close()
        browser.close()

    say(f"\n产物目录: {OUT_DIR}")
    return pages_out, frontend_down


def main() -> None:
    ap = argparse.ArgumentParser(description="前端视觉探针（只读）")
    ap.add_argument("--url", action="append", default=None,
                    help="要看的地址，可重复；缺省看首页与报告屏")
    ap.add_argument("--theme", choices=["light", "dark", "both"], default="both")
    ap.add_argument("--desktop-only", action="store_true")
    ap.add_argument("--mobile-only", action="store_true")
    ap.add_argument("--tokens", action="store_true",
                    help="附带打印 :root 上语义 token 的实际取值（查主题是否真翻转）")
    ap.add_argument("--json", action="store_true", dest="as_json",
                    help="输出结构稳定的观测报告（schema=ui-probe/1），供机器消费")
    ap.add_argument("--selector", action="append", default=None,
                    help="要量 boundingBox 的 css 选择器，可重复")
    ap.add_argument("--assert", action="append", default=None, dest="criteria",
                    help="判据，可重复：no-console-errors / no-horizontal-overflow / visible:<css>")
    a = ap.parse_args()

    try:
        criteria = [parse_criterion(c) for c in (a.criteria or [])]
    except ValueError as err:
        print(err, file=sys.stderr)
        raise SystemExit(EXIT_ASSERT_FAILED) from None
    # 判据里点名的选择器自动进观测面：写了判据却忘了 --selector 会让它恒判「找不到」，
    # 而那是一条**假红**——它说的是探针没量，不是页面没有。
    watch = list(a.selector or [])
    watch += [c[len("visible:"):].strip() for c in criteria if c.startswith("visible:")]

    urls = ([(f"url{i + 1}", u) for i, u in enumerate(a.url)]
            if a.url else DEFAULT_URLS)
    themes = ["light", "dark"] if a.theme == "both" else [a.theme]
    if a.desktop_only:
        vps = ["desktop"]
    elif a.mobile_only:
        vps = ["mobile"]
    else:
        vps = ["desktop", "mobile"]

    pages, frontend_down = probe(
        urls, themes, vps, a.tokens, selectors=sorted(set(watch)), quiet=a.as_json)
    report = build_report(pages, criteria=criteria, frontend_down=frontend_down)

    if a.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for row in report["assertions"]:
            print(f"  {'✓' if row['ok'] else '✗'} [{row['page']}] "
                  f"{row['criterion']} —— {row['detail']}")
        print(f"问题计数: {report['problems']}（横向溢出 / 控制台 error，各计一次）")

    code = exit_code(report)
    if code == EXIT_FRONTEND_DOWN:
        print(
            "前端未运行：连接被拒。**这不是判据不满足**——判据的红要改代码，"
            "这条红要起服务：\n    start-demo.bat   （后端 :8000 + 前端 :3000）",
            file=sys.stderr,
        )
    elif code == EXIT_ASSERT_FAILED:
        failed = [f"[{r['page']}] {r['criterion']}" for r in report["assertions"] if not r["ok"]]
        if failed:
            print(f"判据不满足 {len(failed)} 条：" + "、".join(failed), file=sys.stderr)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
