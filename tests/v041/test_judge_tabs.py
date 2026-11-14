"""JUDGE-TAB-01：判定台五件之间的**屏内互链带**（不是路由）。

## 改前实况

v4 把这五件做成一屏五个 tab（`主题列表 / Gate① 判定 / 作业进度 / 受众选择 / vibe_pack`）。
本仓这五件是**五条独立路由**，而它们**彼此之间今天一条互链都没有**——
只有项目总览那个枢纽屏各链一次。

`DEC-060` 第二条：29 条路由与 7 个导航入口一条不动，v4 的 5 tab
**只以互链带的形式吸收**。所以本卡加的是一条屏内导航条：
NEVER 新建 `/judge` 一类的合并屏、NEVER 碰 `NAV_ITEMS`。

## 五条路由要的 id 不是同一个

project / job / deliverable 各一种。拿不到某一个时，那一条走「未就绪」并
**说出它在等什么**——NEVER 拼一个 id 出来（`DEC-012`），
也 NEVER 静默灰掉（灰着不说与「这个功能没做」在屏上长得一样）。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
TABS = WEB / "components" / "judge-tabs" / "JudgeTabs.tsx"
TOPICS_SCREEN = WEB / "app" / "projects" / "[id]" / "topics" / "page.tsx"
SHELL = WEB / "components" / "shell" / "AppShell.tsx"
MESSAGES = WEB / "messages"
GRAPH = REPO / "assets" / "screen_graph.json"
FRONTEND = "http://localhost:3000"

#: 五条 tab 与它们指向的既有路由（卡面逐字）。
FIVE = {
    "topics": "/projects/{project}/topics",
    "gate": "/gate/{job}",
    "job": "/jobs/{job}",
    "audience": "/projects/{project}/proposal",
    "pack": "/deliverables/{deliverable}/pack",
}
#: 真栈实取用的样例 id（库里真有的那几个）。
SAMPLE = {"project": "proj-demo-fixture", "job": "job-4d22d6be-c3dc-47cf-b334-70a573efb7f4",
          "deliverable": "del-demo-fixture-report"}


def _code() -> str:
    return TABS.read_text(encoding="utf-8")


def _zh() -> dict[str, str]:
    return json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))


def _status(path: str) -> int:
    try:
        with urllib.request.urlopen(FRONTEND + path, timeout=30) as res:
            return int(res.status)
    except urllib.error.HTTPError as err:
        return int(err.code)
    except OSError:
        pytest.skip("前端没起（:3000）——这条判据要真去取一次")


# ═════════════════ 一、五条 tab 指的是既有路由，且都打得开


@pytest.mark.parametrize("key", sorted(FIVE))
def test_each_tab_points_at_the_existing_route(key: str) -> None:
    """五条 `href` 逐条断言——**它们指的都是既有路由**，不是新建的合并屏。"""
    code = _code()
    # `href` **在 JSX 的 `href={…}` 那一处就地拼**（三种 id 在那里都叫 `tab.id`）——
    # 先存进变量再传给 `href` 的话，前后端对账那把尺子会把 `/gate/{}`
    # 当成「前端在调而后端没有的一条 API」（实测：整批全跑时它红了两条）。
    # **导航不是调用**，而这条区分要写成尺子读得懂的形状。
    shape = (FIVE[key].replace("{project}", "${encodeURIComponent(tab.id)}")
             .replace("{job}", "${encodeURIComponent(tab.id)}")
             .replace("{deliverable}", "${encodeURIComponent(tab.id)}"))

    assert shape in code, f"{key} 那条指向的不是 {FIVE[key]}"


def test_the_hrefs_are_built_at_the_href_site_so_the_ruler_reads_them_as_navigation() -> None:
    """五条 `href` 就地拼——**这条判据钉的是「尺子读得懂」这件事**。

    `tools/check_fe_be_parity.py` 按 `href={…}` 的形状把导航与调用分开。
    把路径先存进变量，它就会把这五条页面路由当成 API 调用，
    于是 `/gate/{}` 变成「前端要而后端没有」——一条**由写法造成的假发现**。
    """
    code = _code()

    assert "href={" in code
    assert "href: `" not in code and 'href: "' not in code, (
        "路径又被先存进变量了——尺子会把它读成一次 API 调用")


@pytest.mark.parametrize("key", sorted(FIVE))
def test_every_route_the_bar_points_at_really_opens(key: str) -> None:
    """**真栈逐条取一次**：五条路由都不是 404。

    只判源码里那五个字符串的话，指向一条不存在的路由也会绿——
    而屏上那一条点下去就是一张 404。
    """
    path = FIVE[key].format(**SAMPLE)

    assert _status(path) != 404, f"{key} 指向的 {path} 是 404"


def test_the_current_tab_says_it_is_the_current_one() -> None:
    """当前那一条带 `aria-current`——读屏的人靠它知道自己在哪。"""
    code = _code()

    assert 'aria-current={tab.key === current ? "page" : undefined}' in code


# ═════════════════ 二、未就绪的那几条：**说得出在等什么**


def test_a_tab_without_its_id_is_listed_and_says_what_it_waits_for() -> None:
    """**阴性对照**：拿不到 id 时那一条仍然列出来，并印出它在等什么。

    藏起来 = 用户不知道这一步存在；灰着不说 = 他不知道要做什么才能走过去。
    两者在屏上都比「说出来」更糟。
    """
    code = _code()

    assert 'data-judge-tab-ready={tab.id ? "true" : "false"}' in code
    assert "data-judge-tab-waiting" in code, "未就绪那一条没有说明"
    for key in ("judge.tabs.waiting.job", "judge.tabs.waiting.pack"):
        assert key in code, f"少了 {key} 那句"
        assert _zh()[key].strip(), f"{key} 是空串"


def test_the_two_waiting_sentences_say_different_things() -> None:
    """等作业与等交付物是两件事——一句话包办的话，用户不知道自己该等哪一件。"""
    zh = _zh()

    assert zh["judge.tabs.waiting.job"] != zh["judge.tabs.waiting.pack"]


def test_no_id_is_ever_composed() -> None:
    """**NEVER 拼一个 id 出来**（`DEC-012` 同一条纪律）。

    三种 id 各有各的来源；拿不到就走未就绪那条路，而不是拼一个去问。
    """
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", _code(), flags=re.DOTALL)

    # 形态：把某个 id 与字面前缀拼起来（`del-` / `job-` / `proj-`）。
    for prefix in ("del-", "job-", "proj-"):
        assert f'"{prefix}' not in stripped and f"`{prefix}" not in stripped, (
            f"组件里拼了一个 {prefix}… 的 id")


# ═════════════════ 三、它是一条**带**，不是一条路由


def test_the_bar_added_no_route_and_touched_no_nav_entry() -> None:
    """`NAV_ITEMS` 七项一个字没动，且 `web/app` 下没有新建 `/judge` 一类的屏。"""
    shell = SHELL.read_text(encoding="utf-8")
    hrefs = re.findall(r'\{ href: "([^"]+)", key: "([^"]+)" \}', shell)

    assert len(hrefs) == 7, f"顶栏入口数变了：{[h for h, _ in hrefs]}"
    assert not (WEB / "app" / "judge").exists(), "新建了一个 /judge 合并屏"


def test_the_screen_graph_did_not_gain_a_route() -> None:
    """屏图里的路由条数不变——这条带是屏内的东西，不该出现在屏图上。"""
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    routes = [s.get("route") for s in graph.get("screens", [])]

    assert "/judge" not in routes
    assert len(routes) == len(set(routes)), "屏图里有重复路由"


def test_the_bar_is_mounted_on_at_least_one_of_the_five() -> None:
    """这条带**真的挂在屏上**了（主题列表那一屏）。

    只建组件不挂的话，它与「没做」在屏上长得一模一样——
    而那正是本仓 `F-09`（DOM 里有 ≠ 屏幕上有）记过的坑。
    """
    screen = TOPICS_SCREEN.read_text(encoding="utf-8")

    assert "JudgeTabs" in screen, "主题列表那一屏没挂这条带"
    assert 'current="topics"' in screen, "挂上了却没告诉它当前是哪一件"


# ═════════════════ 四、文案与配色


def test_every_label_goes_through_the_dictionary_in_both_locales() -> None:
    """五个 tab 名 + 两句「在等什么」+ 一个 aria 标签，zh/en 各一份。"""
    zh = _zh()
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    for key in (*(f"judge.tabs.{k}" for k in FIVE),
                "judge.tabs.waiting.job", "judge.tabs.waiting.pack", "judge.tabs.label"):
        assert key in zh and key in en, f"{key} 少了一份"


def test_no_bare_colour_in_the_component() -> None:
    """裸色值 0（`DEC-060` 的单一颜色来源）。"""
    stripped = re.sub(r"/\*.*?\*/|//[^\n]*", "", _code(), flags=re.DOTALL)

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", stripped)
