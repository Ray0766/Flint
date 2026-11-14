"""WB-07：AI 设计工作台改名退居次要（`DESIGN-01~03` 的成果一点不丢）。

`DEC-059` 逐字：「新增主工作台，不替换现有『AI 设计工作台』——后者改名退居次要，
`DESIGN-01~03` 的端点/作业/固化流程一个字不改，成果一点不丢」。

于是这张卡只做两件事：**改名**与**排序**。判据分两半——
一半判改动**真的发生了**（名字换了、次序换了），
另一半判**该没动的一个都没动**（7 条端点、路由、可达性、豁免名单）。

后一半才是这张卡的重点：`DEC-059` 那段话说得很清楚——
替换掉那一屏，`DESIGN-01~03` 的成果会跟着一起消失，
而**消失之后，消失本身也看不见了**（新屏跑得好好的，没有人会回头去数少了什么）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
SHELL = WEB / "components" / "shell" / "AppShell.tsx"
MESSAGES = WEB / "messages"
DESIGN_SCREEN = WEB / "app" / "design" / "page.tsx"
GRAPH = REPO / "assets" / "screen_graph.json"

#: `/design` 那一族在 openapi 里的 7 条（2026-08-12 实测）。
DESIGN_ENDPOINTS = (
    "/design/explore/render",
    "/design/export-check",
    "/design/render",
    "/design/sessions/{job_id}/replay",
    "/design/stale-notices",
    "/design/templates",
    "/projects/{project_id}/design_generate",
)


def _nav_items() -> list[tuple[str, str]]:
    """顶栏那张表：`[(href, key), …]`，**按源码里的次序**。"""
    code = SHELL.read_text(encoding="utf-8")
    block = code[code.index("export const NAV_ITEMS"):]
    block = block[:block.index("];")]
    return re.findall(r'\{ href: "([^"]+)", key: "([^"]+)" \}', block)


# ═════════════════ 一、改动真的发生了


def test_the_design_entry_was_renamed_in_both_locales() -> None:
    """顶栏那一项改名为「模板工具」，两份词典各改一次。"""
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    assert zh["shell.nav.design"] == "模板工具"
    assert en["shell.nav.design"] == "Template tools"
    # 屏头也一起改：点进「模板工具」落到一张写着旧名字的屏，用户会以为点错了。
    assert zh["design.title"] == zh["shell.nav.design"]
    assert en["design.title"] == en["shell.nav.design"]


def test_the_workbench_comes_before_the_renamed_design_entry() -> None:
    """「退居次要」的可见形式就是**次序**：主工作台排在它前面。"""
    order = [href for href, _key in _nav_items()]

    assert order.index("/workbench") < order.index("/design"), order


# ═════════════════ 二、该没动的一个都没动


def test_the_design_entry_is_still_on_the_bar() -> None:
    """**NEVER 摘掉**：藏起来与删掉在屏上长得一模一样（`DEC-059` 原话）。"""
    items = dict(_nav_items())

    assert "/design" in items, "把它从导航上摘掉了"
    assert items["/design"] == "shell.nav.design", "换了文案键 = 换了那一项"


def test_the_bar_still_has_exactly_seven_entries() -> None:
    """七个入口一个不多一个不少（`WB-01` 加的第 7 个）。"""
    order = [href for href, _key in _nav_items()]

    assert len(order) == 7, order
    assert len(set(order)) == 7, f"有重复项：{order}"


def test_the_design_screen_itself_was_not_touched() -> None:
    """那一屏的实现里**没有本卡的痕迹**——改的是名字，不是那一屏。"""
    assert "WB-07" not in DESIGN_SCREEN.read_text(encoding="utf-8")


def test_all_seven_design_endpoints_are_still_declared() -> None:
    """`/design` 那一族 7 条端点仍在（**从后端源码里数**，不是从我记忆里数）。

    改名把端点带走的形态：有人顺手把那一族的装配也「清理」了。
    这条判据从 `flint/api/app.py` 的装配面与各 app 的路由声明上数。
    """
    api = (REPO / "flint" / "api").rglob("*.py")
    text = "\n".join(path.read_text(encoding="utf-8") for path in api)

    missing = [route for route in DESIGN_ENDPOINTS
               if route.replace("{job_id}", "{job_id}") not in text]
    assert missing == [], f"这几条 design 端点在后端源码里找不到了：{missing}"
    assert "create_design_app" in text, "design 那一族没装配"


def test_the_screen_graph_still_declares_the_design_route() -> None:
    """屏图里那一条仍在（可达性判据读的就是它）。"""
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    routes = {screen.get("route") for screen in graph.get("screens", [])}

    assert "/design" in routes
    assert "/workbench" in routes, "新一屏没进屏图，可达性就管不到它"


@pytest.mark.parametrize("locale", ("zh", "en"))
def test_the_two_catalogs_stay_symmetric_after_the_rename(locale: str) -> None:
    """改名之后两份词典仍然对称（改一份忘另一份是最常见的那种）。"""
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    assert set(zh) == set(en)
    assert (zh if locale == "zh" else en)["shell.nav.design"] != "AI 设计工作台" or locale == "en"
