"""EYE-03：前端 e2e 冒烟——起真栈、逐屏取证、把数字留下。

用法（要浏览器，故用隔离环境的解释器；前后端先用 `start-demo.ps1` 起好）：
    C:\\pwenv\\Scripts\\python.exe harness/fe_smoke.py                 # 两主题逐屏
    C:\\pwenv\\Scripts\\python.exe harness/fe_smoke.py --theme dark
退出码 0 = 每屏 200、零控制台报错、无横向溢出；1 = 有屏不达标；3 = 栈没起（**不是**不达标）。
产物：`.ui-probe/{屏名}-{主题}.png` + `.ui-probe/fe_smoke.json`（逐屏真实数字）。

## 为什么冒烟要逐屏给数字

「冒烟通过」这四个字什么都没说。**这份报告里每一屏都必须带五个数字**：
HTTP 状态、控制台报错数、页高、横向溢出、截图名。缺任何一个即判无效
（`validate_row`）——一句「通过」盖住的可能是「三张屏里只跑了一张」。

## 屏清点从磁盘来，不从记忆来

`web/app/**/page.tsx` 有几个文件就有几张屏。**动态段（`[id]`）用显式声明的样例 id 填**
（`SAMPLE_IDS`），没声明的**报出来而不是跳过**——悄悄跳过的那一屏在报告里根本不存在，
而报告看起来是全绿的。现编一个 id 更糟：那一屏会恒 404，而 404 会被读成「这屏坏了」，
真相是探针给错了地址。

## 栈没起 ≠ 冒烟不过

两者的修法完全不同（起服务 vs 改代码），所以退出码不同（3 vs 1），
报告里也分成两个字段（`stack_down` vs `counts`）。这条与 `scripts/ui_probe.py`（EYE-01）
的三种红同源。

## 只读

不点按钮、不填表单、不提交、不写数据库——沿用 `scripts/ui_probe.py` 的既有边界。
一旦开始点，冒烟就会改数据；改了数据的冒烟下一次跑出来的东西不一样，
那时候没人分得清是回归还是上一次自己留下的痕迹。
"""
from __future__ import annotations

import argparse
import json
import re
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
WEB_ROOT = REPO / "web"
OUT_DIR = REPO / ".ui-probe"
REPORT_PATH = OUT_DIR / "fe_smoke.json"

SCHEMA = "fe-smoke/1"
FRONTEND = ("前端 :3000", "127.0.0.1", 3000)
BACKEND = ("后端 :8000", "127.0.0.1", 8000)
BASE_URL = "http://localhost:3000"
THEMES = ("dark", "light")
# FIX-06：**移动视口进常规取证**。
#
# 改前这份冒烟只跑 1440——十三屏在 390px 下**从来没有人量过**。
# `LOCALE-FORM-OVERFLOWS-ON-MOBILE` 那条溢出因此是「新被看见的」而不是新坏的，
# 而看见它靠的是有人手工单独跑了一次 `ui_probe`。
# 靠偶然发现的东西，下一次就会靠偶然错过。
VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("desktop", 1440, 900),
    ("mobile", 390, 844),      # iPhone 14 Pro 逻辑分辨率，与 ui_probe 同一个数
)

EXIT_OK = 0
EXIT_SCREEN_FAILED = 1
EXIT_NO_PLAYWRIGHT = 2
EXIT_STACK_DOWN = 3

# 动态路由的样例 id：**显式声明**，与 demo 数据对齐（start-demo.ps1 的演示日 2026-07-04）。
# 新增动态路由却不在这里登记 → `discover_screens` 会把它报成 problem，NEVER 跳过。
# 两个 id 都从 demo 库里**查出来**，不是编的（`select deliverable_id/job_id from …`，
# 见 docs/trace/EYE-03.md）。首版给 /jobs/[id] 编了个 `job-demo-fixture`，实跑当场现形：
# 页面 200 但控制台一条 404——正是本文件 docstring 警告的那种「探针给错地址」。
# 动态段：`[id]` / `[token]` / 任何参数名。
_PARAM_SEGMENT = re.compile(r"\[[^\]]+\]")

SAMPLE_IDS: dict[str, str] = {
    "/deliverables/[id]": "del-demo-fixture-report",
    # FIX-09（`DEC-037`）：原先填 `m1004-j`——那条作业的发起人是 `u-sys`，
    # 而探针那个身份是 `demo-user`。第 4 批接上鉴权之后端点回 **403**，
    # **那是正确行为**，红的是样例没跟着鉴权口径对齐。
    # `harness/demo_seed_probe_job.py` 种了一条属于探针自己的作业，这里改指它。
    # `m1004-j` **原样留着**：它是「不属于我的作业」的活样本，
    # 屏上该显示「无权查看」这件事将来要靠它来量
    # （`docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`）。
    "/jobs/[id]": "probe-owned-ingest",
    # UI-02 的两条新动态路由。**照本文件上面那条注释登记**——不登记的话
    # `discover_screens` 会把它们报成 problem 并跳过取证，而跳过的那两屏
    # 正是本轮新写的两屏。
    #
    # FIX-06：这条原来也填 `m1004-j`，而那个 job **没有 verdict 快照**——
    # 判定屏于是恒发一次 404（控制台报错 1），拍回来的是一张空态截图。
    # 本文件开头那句「现编一个 id 更糟：那一屏会恒 404，而 404 会被读成
    # 『这屏坏了』，真相是探针给错了地址」说的正是这一处。
    # `job-gate1-live-qwen` 是 demo 库里**唯一**有 `snap-…-verdict` 的 job，
    # 换成它之后这一屏取证的是真判定，而不是「没查到」。
    "/gate/[id]": "job-gate1-live-qwen",
    "/deliverables/[id]/export": "del-demo-fixture-report",
    # UI-03 的图谱工作台。**这个 id 不是从库里查出来的**，因为
    # `GET /workbenches` 未建、库里也没有 workbenches 表——这一屏此刻
    # 不拿 id 去问任何东西（它如实标「接口未提供」）。所以给一个稳定的
    # 占位串即可；等端点建好、这一屏真去取数那天，**这里 MUST 换成
    # 从库里查出来的真 id**，否则又会变成「探针给错地址」那一种假红。
    "/workbenches/[id]": "wb-placeholder",
    # UI-06 的外链页。同上：`GET /share/{token}` 未接通，这一屏不拿 token
    # 去问任何东西，所以给一个稳定占位串；端点挂上后 MUST 换成真 token。
    "/share/[token]": "share-placeholder",
    # UI-09 的质量卡屏。用与 `/deliverables/[id]` 同一个真 id。
    "/deliverables/[id]/quality": "del-demo-fixture-report",
    "/deliverables/[id]/pack": "del-demo-fixture-report",
    # UI-11 的项目总览。**`WIRE-03` 把这一屏接上了真端点**，占位串会让它恒 404
    # ——正是本文件 docstring 警告的「探针给错地址」那种假红。
    # 这个 id 从 demo 库里查出来（`select project_id from projects limit 1`）。
    "/projects/[id]": "proj-demo14bf9d94b0",
    # CHAIN-03 的主题两屏（蓝本 P4/P5）。列表那条复用上面同一个真 project id
    # ——它真去查 `GET /projects/{id}/topics`，占位串会让它恒 404。
    "/projects/[id]/topics": "proj-demo14bf9d94b0",
    # SEED-01（`DEC-041`）：占位串 `tp-placeholder` 退役。
    # 改前这里给的是稳定占位串，取证到的是**未知 id 的诚实态**（带 `code` 的 404）——
    # 那句「库里有主题那天 MUST 换成真 id」就是本卡执行的。
    #
    # 指的是**夹具**（`harness/demo_seed_topic.py`），不是那六条真主题
    # （`topic-demo14bf9d94b0-*`，模型产出，某次 demo 跑留下的）。理由是**可复现**：
    # 那六条没有任何脚本能重造，demo 库重建一次样例 id 又成死链——
    # 而那正是这条注释上一版踩过的坑。夹具由脚本写死、幂等、随时能撤。
    #
    # owner 若更希望取证屏上是真产出，把这里换成 `topic-demo14bf9d94b0-1` 即可，
    # 代价是它依赖一次没人复跑的历史运行。
    "/topics/[id]": "topic-demo-fixture-vecdb",
    # CHAIN-04 的发起分析屏。复用同一个真 project id——这一屏**不进屏取数**
    # （只有按下「发起分析」才发请求），所以 id 只影响提交时打到哪个项目。
    "/projects/[id]/analysis": "proj-demo14bf9d94b0",
    # CHAIN-05 的两屏。受众分叉屏进屏零请求，id 只影响提交打到哪个项目；
    # 干预页**进屏真取数**（`GET /deliverables/{id}/blocks`），所以用那个真交付物 id
    # ——占位串会让它恒 404，正是本文件 docstring 警告的「探针给错地址」。
    "/projects/[id]/proposal": "proj-demo14bf9d94b0",
    "/deliverables/[id]/interventions": "del-demo-fixture-report",
    # NAV-02 的热点分析屏。**进屏真取数**（`GET /clusters/{id}/evidence-cards`），
    # 所以这里要一个**库里真有证据卡**的簇——占位串会让证据概览恒空，
    # 而空与「这个热点没有证据卡」长得一模一样，取证就白拍了。
    # 这个 id 从 demo 库里查出来（按证据卡条数排第一的那个簇）。
    "/clusters/[id]": "c-20260629-088",
}


@dataclass(frozen=True)
class Screen:
    name: str
    route: str
    url: str
    source: str
    problem: str = ""


@dataclass
class Row:
    values: dict[str, Any] = field(default_factory=dict)


def discover_screens(web_root: Path) -> list[Screen]:
    """从 `app/**/page.tsx` 清点屏。磁盘是真相，NEVER 手抄一份清单。"""
    screens: list[Screen] = []
    for page in sorted(web_root.glob("app/**/page.tsx")):
        rel = page.relative_to(web_root).as_posix()
        segments = rel[len("app/"):-len("/page.tsx")] if rel != "app/page.tsx" else ""
        route = "/" + segments
        name = segments.replace("/", "-").replace("[", "").replace("]", "") or "root"
        if "[" in route:
            sample = SAMPLE_IDS.get(route)
            if sample is None:
                screens.append(Screen(
                    name=name, route=route, url="", source=rel,
                    problem=f"动态路由 {route} 没有声明样例 id（登记进 SAMPLE_IDS），"
                            "本轮无法取证——NEVER 现编一个，那会让这屏恒 404",
                ))
                continue
            # 通配任意参数名，NEVER 只认 `[id]`：`/share/[token]` 用 `[id]`
            # 替换替不掉，URL 里会原样留着 `[token]`——于是 SAMPLE_IDS 里那一行
            # 是**死配置**，改它没有任何效果，而报告看起来一切正常。
            # WIRE-04 实测发现（`_PARAM_SEGMENT` 见文件头）。
            url = BASE_URL + _PARAM_SEGMENT.sub(sample, route)
        else:
            url = BASE_URL + route
        screens.append(Screen(name=name, route=route, url=url, source=rel))
    return screens


def screenshot_name(screen: str, theme: str, viewport: str = "desktop") -> str:
    """截图名带视口。**不带的话 mobile 会把 desktop 那张覆盖掉**，
    而报告里两行都指着同一个文件名——看图的人以为自己在看两份证据。"""
    return f"{screen}-{theme}-{viewport}.png"


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def stack_down() -> list[str]:
    """哪一端没起。空列表 = 两端都在。"""
    return [label for label, host, port in (FRONTEND, BACKEND) if not _port_open(host, port)]


REQUIRED_FIELDS = (
    "screen", "route", "url", "theme", "viewport", "http_status",
    "console_error_count", "console_errors", "page_height", "horizontal_overflow",
    "scroll_width", "viewport_width", "screenshot",
)


def validate_row(row: dict[str, Any]) -> list[str]:
    """一屏的观测缺哪几个数字。空列表 = 齐全。

    这是「NEVER 只报一句通过」的落地点：一句「通过」盖住的可能是「三张屏里只跑了一张」。
    """
    return [f"缺 {name}" for name in REQUIRED_FIELDS if name not in row]


def build_report(rows: list[dict[str, Any]], *, stack_down: list[str]) -> dict[str, Any]:
    counts = {
        "screens": len(rows),
        # 移动视口那一半单独计数：混在总数里的话，「十三屏全绿」与
        # 「十三屏桌面全绿、移动一屏没跑」在报告上长得一模一样。
        "mobile_rows": sum(1 for r in rows if r.get("viewport") == "mobile"),
        "mobile_overflow": sum(
            1 for r in rows
            if r.get("viewport") == "mobile" and r.get("horizontal_overflow")),
        "bad_status": sum(1 for r in rows if r.get("http_status") != 200),
        "console_errors": sum(r.get("console_error_count", 0) for r in rows),
        "overflow": sum(1 for r in rows if r.get("horizontal_overflow")),
        "invalid_rows": sum(1 for r in rows if validate_row(r)),
    }
    ok = (
        not stack_down
        and bool(rows)
        and counts["bad_status"] == 0
        and counts["console_errors"] == 0
        and counts["overflow"] == 0
        and counts["invalid_rows"] == 0
    )
    return {"schema": SCHEMA, "screens": rows, "stack_down": stack_down,
            "ok": ok, "counts": counts}


def skip_reason(report: dict[str, Any]) -> str | None:
    """栈没起 → 给一句 skip 理由；**跑了没过 NEVER 给理由**（那要红，不要跳）。"""
    if report["stack_down"]:
        return ("本机栈没起：" + "、".join(report["stack_down"])
                + "——起栈用 start-demo.ps1，这不是冒烟不过")
    return None


def _capture(page: Any, screen: Screen, theme: str, status: int,
             errors: list[str], viewport: str = "desktop") -> dict[str, Any]:
    shot = OUT_DIR / screenshot_name(screen.name, theme, viewport)
    page.screenshot(path=str(shot), full_page=True)
    m = page.evaluate(
        "() => ({h: document.body.scrollHeight, w: document.body.scrollWidth,"
        " ow: window.innerWidth})")
    return {
        "screen": screen.name, "route": screen.route, "url": screen.url, "theme": theme,
        "viewport": viewport,
        "http_status": status, "console_error_count": len(errors),
        "console_errors": errors[:10], "page_height": m["h"],
        "horizontal_overflow": m["w"] > m["ow"] + 1,
        "scroll_width": m["w"], "viewport_width": m["ow"], "screenshot": shot.name,
    }


def run_smoke(screens: list[Screen], themes: tuple[str, ...] = THEMES) -> dict[str, Any]:
    down = stack_down()
    if down:
        return build_report([], stack_down=down)

    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        print("playwright 不在当前解释器里：用 C:\\pwenv\\Scripts\\python.exe 跑本文件",
              file=sys.stderr)
        raise SystemExit(EXIT_NO_PLAYWRIGHT) from None

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for theme in themes:
            for name, width, height in VIEWPORTS:
                ctx = browser.new_context(
                    viewport={"width": width, "height": height}, color_scheme=theme)
                ctx.add_init_script(
                    f"try{{localStorage.setItem('theme','{theme}')}}catch(e){{}}")
                for screen in screens:
                    if not screen.url:
                        continue                  # problem 屏在 discover 时已报出
                    page = ctx.new_page()
                    errs: list[str] = []
                    page.on("console", lambda m, sink=errs: sink.append(
                        f"{m.type}: {m.text}") if m.type == "error" else None)
                    page.on("pageerror",
                            lambda e, sink=errs: sink.append(f"pageerror: {e}"))
                    response = page.goto(
                        screen.url, wait_until="networkidle", timeout=60000)
                    page.wait_for_timeout(2000)   # 等客户端取数落定
                    status = response.status if response is not None else 0
                    rows.append(_capture(page, screen, theme, status, errs, name))
                    page.close()
                ctx.close()
        browser.close()
    return build_report(rows, stack_down=[])


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="前端 e2e 冒烟（只读）")
    ap.add_argument("--theme", choices=["dark", "light", "both"], default="both")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)
    themes = THEMES if args.theme == "both" else (args.theme,)

    screens = discover_screens(WEB_ROOT)
    for screen in screens:
        if screen.problem:
            print(f"!! {screen.route}: {screen.problem}", file=sys.stderr)

    report = run_smoke(screens, themes)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for row in report["screens"]:
            print(f"  [{row['theme']}] {row['route']:<24} HTTP {row['http_status']}"
                  f"  控制台 error {row['console_error_count']}"
                  f"  页高 {row['page_height']}px"
                  f"  {'横向溢出' if row['horizontal_overflow'] else '无溢出'}"
                  f"  → {row['screenshot']}")
            for err in row["console_errors"][:3]:
                print(f"        {err[:140]}")
        print(f"报告：{REPORT_PATH}")

    reason = skip_reason(report)
    if reason is not None:
        print(reason, file=sys.stderr)
        return EXIT_STACK_DOWN
    return EXIT_OK if report["ok"] else EXIT_SCREEN_FAILED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
