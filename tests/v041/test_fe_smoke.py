"""EYE-03：前端 e2e 冒烟的验收——起真栈、逐屏取证、**NEVER 只报一句「通过」**。

## 这份验收怎么分层

真栈冒烟要浏览器（playwright 恒在 `C:\\pwenv`）与在跑的前后端（:3000 / :8000），
项目 `.venv` 下的 `pytest` 两样都没有。所以这里分成三层，**没有一层是「跳过就算过」**：

1. **屏清点**（离线，恒跑）——`web/app/**/page.tsx` 有几张屏，冒烟就得覆盖几张。
   少一张就红：漏掉的那张正是最可能没人看过的那张。
2. **报告契约**（离线，恒跑）——每屏必须给出 HTTP 状态、控制台报错数、页高、横向溢出、
   截图名五个**真实数字**。缺任何一个即判无效，`NEVER 只报一句「通过」`就是在这一层落地的。
3. **实跑产物**（有则必验）——`.ui-probe/fe_smoke.json` 在就逐屏校验它；不在则 skip
   并说明「本机没跑过真栈」。**skip 的理由必须是这一句**，不是「测试不适用」。

第 3 层的 skip 是卡面 acceptance② 授权的（「前端未起时 skip 并说明」）；第 1、2 层
**恒跑**，所以这份验收不会退化成一条永远绿的空壳。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import fe_smoke

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"


def _row(**over: object) -> dict:
    base = {
        "screen": "demo", "route": "/demo", "url": "http://localhost:3000/demo",
        # FIX-06：移动视口进常规取证之后，每行多一个 `viewport`。
        "theme": "dark", "viewport": "desktop", "http_status": 200,
        "console_error_count": 0,
        "console_errors": [], "page_height": 1800, "horizontal_overflow": False,
        "scroll_width": 1440, "viewport_width": 1440, "screenshot": "demo-dark.png",
    }
    base.update(over)
    return base


# ───────────────────────── ① 屏清点：一张都不能漏


def test_every_page_file_in_the_app_router_becomes_a_screen() -> None:
    """磁盘上有几个 `page.tsx`，清点就得给出几张屏。

    漏掉的那张正是最可能没人看过的那张——冒烟的价值全在覆盖面上。
    """
    on_disk = sorted(p.relative_to(WEB).as_posix() for p in WEB.glob("app/**/page.tsx"))
    screens = fe_smoke.discover_screens(WEB)

    assert len(screens) == len(on_disk), f"磁盘 {on_disk}，清点出 {[s.route for s in screens]}"
    assert {s.source for s in screens} == set(on_disk)


def test_the_known_routes_are_all_there() -> None:
    """当前全部屏的路由形态钉住（含四条动态路由）。

    判**等值**是有意的：这份清单是「加了新屏就来这里确认探针盖到它」的绊线。
    改成包含的话，新屏可以悄悄进来而没人检查它有没有样例 id——
    那正是 `discover_screens` 会把它报成 problem 然后被跳过取证的形状。
    UI-02 加三屏时就是这么被拦下来确认的（两条新动态路由同时登记进 `SAMPLE_IDS`）。
    """
    routes = sorted(s.route for s in fe_smoke.discover_screens(WEB))

    assert routes == [
        "/account",
        "/billing",
        # NAV-02 的热点分析屏。进屏真取数，`SAMPLE_IDS` 里登记的是**库里真有证据卡**
        # 的那个簇——占位串会让证据概览恒空，而空与「这个热点没有证据卡」
        # 在截图上长得一模一样。
        "/clusters/[id]",
        # CHAIN-04 的 combo 入口（蓝本 P3）。静态路由，无需样例 id。
        "/combo",
        "/deliverables/[id]",
        "/deliverables/[id]/export",
        # CHAIN-05 的干预页（蓝本 P10）。已登记进 `SAMPLE_IDS`。
        "/deliverables/[id]/interventions",
        "/deliverables/[id]/pack",
        "/deliverables/[id]/quality",
        "/demo",
        "/design",
        "/favorites",
        "/gate/[id]",
        "/jobs/[id]",
        "/plaza",
        "/projects/[id]",
        # CHAIN-04 的发起分析屏（蓝本 P6）。已登记进 `SAMPLE_IDS`。
        "/projects/[id]/analysis",
        # CHAIN-05 的受众分叉屏（蓝本 P11）。
        "/projects/[id]/proposal",
        # CHAIN-03 的主题两屏（蓝本 P4/P5）。两条都已登记进 `SAMPLE_IDS`——
        # 这条判据就是那道绊线：新屏进来而没人给它样例 id 的话，
        # `discover_screens` 会把它报成 problem 然后跳过取证。
        "/projects/[id]/topics",
        "/settings/locale",
        "/share/[token]",
        "/topics/[id]",
        # WB-01 / DEC-059 的计划书主工作台。**静态路由，无需样例 id**。
        # 它与下面那条只差一个字母而**是两屏**：
        # `/workbench` 是计划书工作台（本批新增），
        # `/workbenches/[id]` 是热点图谱工作台（`UI-03`，一个字没动）。
        "/workbench",
        "/workbenches/[id]",
    ]


def test_a_dynamic_route_uses_a_declared_sample_id() -> None:
    """动态段用**显式声明**的样例 id 填，NEVER 现编一个。

    现编的 id 会让那一屏恒 404，而 404 会被读成「这屏坏了」——真相是探针给错了地址。
    """
    screens = {s.route: s for s in fe_smoke.discover_screens(WEB)}
    deliverable = screens["/deliverables/[id]"]

    assert "[id]" not in deliverable.url
    assert fe_smoke.SAMPLE_IDS["/deliverables/[id]"] in deliverable.url


def test_a_dynamic_route_without_a_sample_id_is_reported_not_dropped(tmp_path: Path) -> None:
    """没声明样例 id 的动态路由 → **报出来**，NEVER 悄悄跳过。

    悄悄跳过的那一屏在报告里根本不存在，而报告看起来是全绿的。
    """
    (tmp_path / "app" / "secret" / "[slug]").mkdir(parents=True)
    (tmp_path / "app" / "secret" / "[slug]" / "page.tsx").write_text("x", encoding="utf-8")

    screens = fe_smoke.discover_screens(tmp_path)

    assert len(screens) == 1
    assert screens[0].url == ""
    assert "没有声明样例 id" in screens[0].problem


# ───────────────────────── ② 报告契约：每屏都要有真实数字


def test_the_report_shape_is_the_documented_one() -> None:
    report = fe_smoke.build_report([_row()], stack_down=[])

    assert report["schema"] == fe_smoke.SCHEMA
    assert set(report) == {"schema", "screens", "stack_down", "ok", "counts"}
    assert set(report["screens"][0]) == {
        "screen", "route", "url", "theme", "viewport", "http_status",
        "console_error_count", "console_errors", "page_height",
        "horizontal_overflow", "scroll_width", "viewport_width", "screenshot",
    }


def test_a_row_missing_a_number_is_invalid() -> None:
    """缺任何一个数字即判无效——这就是「NEVER 只报一句通过」的落地点。"""
    complete = _row()
    # `viewport` 也在必填之列（FIX-06）：缺了它，两个视口的行在报告里分不开，
    # 而「十三屏桌面全绿」会被读成「十三屏全绿」。
    for field in ("http_status", "console_error_count", "page_height", "screenshot",
                  "viewport"):
        broken = {k: v for k, v in complete.items() if k != field}
        problems = fe_smoke.validate_row(broken)
        assert problems, f"缺了 {field} 却判有效"
        # 判**这一条在不在报出来的清单里**，NEVER 假定它排第一——
        # 排序取决于 REQUIRED_FIELDS 的顺序，那不是这条判据要钉的东西。
        assert any(field in problem for problem in problems), problems

    assert fe_smoke.validate_row(complete) == []


def test_a_non_200_screen_is_red() -> None:
    report = fe_smoke.build_report([_row(http_status=500)], stack_down=[])

    assert report["ok"] is False
    assert report["counts"]["bad_status"] == 1


def test_console_errors_and_overflow_are_counted_not_summarised() -> None:
    """报告里留的是**数字与原文**，不是「有一些报错」。"""
    report = fe_smoke.build_report(
        [_row(console_error_count=2, console_errors=["error: a", "error: b"],
              horizontal_overflow=True, scroll_width=1700)],
        stack_down=[],
    )

    assert report["counts"]["console_errors"] == 2
    assert report["counts"]["overflow"] == 1
    assert report["screens"][0]["console_errors"] == ["error: a", "error: b"]
    assert report["ok"] is False


def test_the_screenshot_name_carries_screen_and_theme() -> None:
    """截图文件名带屏名、主题**与视口**，供人工复看（acceptance③）。

    `FIX-06` 加了视口这一段：不带的话 mobile 那张会把 desktop 那张覆盖掉，
    而报告里两行指着同一个文件名——看图的人以为自己在看两份证据。
    """
    assert fe_smoke.screenshot_name("deliverables", "light", "desktop") == (
        "deliverables-light-desktop.png")
    assert fe_smoke.screenshot_name("demo", "dark", "mobile") == "demo-dark-mobile.png"
    assert fe_smoke.screenshot_name("demo", "dark", "mobile") != (
        fe_smoke.screenshot_name("demo", "dark", "desktop"))


def test_a_down_stack_is_never_reported_as_pass() -> None:
    """栈没起时 `ok` 恒假，且报告说得出**是哪一端没起**（acceptance②）。"""
    report = fe_smoke.build_report([], stack_down=["前端 :3000", "后端 :8000"])

    assert report["ok"] is False
    assert report["stack_down"] == ["前端 :3000", "后端 :8000"]
    assert fe_smoke.skip_reason(report) is not None
    assert "没起" in fe_smoke.skip_reason(report)


def test_a_live_stack_has_no_skip_reason() -> None:
    """栈起着时不给 skip 理由——skip 只为「跑不了」，NEVER 为「跑了没过」。"""
    assert fe_smoke.skip_reason(fe_smoke.build_report([_row()], stack_down=[])) is None


# ───────────────────────── ④ 只读边界


def test_the_harness_never_touches_the_page() -> None:
    """全程只读：源码里不出现任何交互调用（沿用 ui_probe 的既有边界）。

    冒烟一旦开始点按钮，它就会改数据；而改了数据的冒烟下一次跑出来的东西不一样，
    那时候没人分得清是回归还是上一次自己留下的痕迹。
    """
    source = (REPO / "harness" / "fe_smoke.py").read_text(encoding="utf-8")
    for forbidden in (".click(", ".fill(", ".press(", ".select_option(",
                      ".set_input_files(", ".check("):
        assert forbidden not in source, f"冒烟里出现了交互调用 {forbidden}"


# ───────────────────────── ③ 实跑产物：有则必验


def test_the_demo_start_script_gap_stays_registered_until_it_is_fixed() -> None:
    """实跑挖出的配置缺陷必须有人认领，且**问题单会自己退休**。

    `web/app/deliverables/[id]/page.tsx` 是服务器组件，读的是 `FLINT_API_BASE`；
    而 `start-demo.ps1` 只设了 `NEXT_PUBLIC_FLINT_API`（客户端那一份）。于是**按文档一键起栈，
    报告屏恒 500**（实测：不设 → HTTP 500 + `Failed to parse URL`；设了 → 六行全 200）。

    改 `start-demo.ps1` 不在本卡 outputs 内（工单 §2：改动面大于卡面 outputs → 走
    `docs/blocked/`），所以这里只钉「问题单在」。脚本一旦补上那个变量，本条自动放行——
    **一条永远要求问题单存在的断言，会逼着修好之后还留着一份过期文档**。
    """
    script = (REPO / "start-demo.ps1").read_text(encoding="utf-8")
    if "FLINT_API_BASE" in script:
        return                                    # 已修，问题单可以撤

    doc = REPO / "docs" / "blocked" / "FE-DEMO-ENV-FLINT-API-BASE.md"
    assert doc.exists(), "start-demo.ps1 仍缺 FLINT_API_BASE，问题单却不在"
    assert "FLINT_API_BASE" in doc.read_text(encoding="utf-8")


def test_the_recorded_run_covers_every_screen_with_real_numbers() -> None:
    """`.ui-probe/fe_smoke.json` 在就逐屏校验；不在就 skip 并说明**是什么没做**。"""
    artifact = REPO / ".ui-probe" / "fe_smoke.json"
    if not artifact.exists():
        pytest.skip("本机没跑过真栈冒烟：缺 .ui-probe/fe_smoke.json"
                    "（起栈用 start-demo.ps1，跑法见 harness/fe_smoke.py 用法行）")

    report = json.loads(artifact.read_text(encoding="utf-8"))
    assert report["schema"] == fe_smoke.SCHEMA

    if report["stack_down"]:
        pytest.skip(f"上次实跑时栈没起：{report['stack_down']}")

    screens = fe_smoke.discover_screens(WEB)
    covered = {row["route"] for row in report["screens"]}
    assert covered == {s.route for s in screens if s.url}, "实跑没覆盖全部屏"

    for row in report["screens"]:
        assert fe_smoke.validate_row(row) == [], f"{row['screen']} 少数字：{row}"
        assert row["http_status"] == 200, f"{row['screen']} 状态 {row['http_status']}"
