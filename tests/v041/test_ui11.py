"""UI-11 · 项目总览屏（蓝本 P14）的结构判据。

交互判据在 vitest（11 条）。这里判源码结构与取证实况。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMPONENT = REPO / "web" / "components" / "project-overview" / "ProjectOverview.tsx"
PAGE = REPO / "web" / "app" / "projects" / "[id]" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/projects/[id]"


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、一次查齐，NEVER 退回三个请求拼


def test_the_page_never_stitches_three_requests() -> None:
    """蓝本那句「无专属端点：topics + jobs + deliverables 组合」**已经过时**：
    BE-01 把 `GET /projects/{id}` 建出来了，一次查齐。

    三次分别查回来的东西对应的是**三个时刻的库**，而屏上看起来像同一时刻的快照。

    ## 这条判据在 `NAV-05` 那天改过一次

    改前它判「源码里不许出现 `/topics`」。`NAV-05` 给这一屏加了三条**链接**
    （主题列表 / 发起分析 / 计划书受众——项目总览是这一族的枢纽），
    于是那个子串出现了，判据当场变红。

    **它拦下的不是「又拼了三个请求」，是「屏上多了一条链接」——两件事。**
    这与本仓栽过十二次的形状同类：判据把说明问题的那句话当成了问题本身。

    改后判的是**它真正要挡的那件事**：这一屏只发一次取数，且发的是那一条。
    导航不是取数（`check_fe_be_parity#_NAV` 那天记的是同一条口径）。
    """
    code = _code_only(PAGE)

    assert "fetch(" not in code, "这一屏自己拼请求了"
    # 数**调用点**（`useScreenData<`），不数标识符出现次数——
    # import 那一行自己就带两处（名字 + 路径），数它等于把判据挂在写法上。
    assert code.count("useScreenData<") == 1, (
        "取数点不止一处——三个时刻的库拼成一张快照，正是这条判据要挡的")
    assert 'useScreenData<unknown>(`/projects/${id}`)' in code, "取的不是那条一次查齐的端点"

    # 三个子串仍然只许出现在**导航**里，NEVER 出现在别的位置。
    #
    # 导航有两种写法：`href=`，与提交成功后的 `window.location.assign(`。
    # 后一种是 `CHAIN-UI-01-a` 加的——从一条跑完的分析去成文，提交回 `{job_id}` 之后进作业屏
    # （与发起分析那一屏同一个写法）。改前这里只认 `href=`，那条跳转当场被判成「拼请求」。
    # 它要挡的那件事没有变：这三个路径 NEVER 出现在取数里（上面那句 `fetch(` 守着）。
    for path in ("/topics", "/jobs", "/deliverables"):
        for line in code.splitlines():
            if path in line:
                assert "href=" in line or "window.location.assign(" in line, (
                    f"{path} 出现在了一个不是导航的地方：{line.strip()}")


def test_the_component_takes_one_object_not_three_lists() -> None:
    """入参是**一份总览**，不是三个独立列表——三个独立入参就等于允许三次取数。"""
    code = _code_only(COMPONENT)

    assert "overview: ProjectOverviewView | null" in code
    assert "topics:" in code and "jobs:" in code and "deliverables:" in code


# ───────────────────────── 二、三个列表恒存在


def test_empty_lists_render_an_empty_state_not_an_error() -> None:
    """BE-01：「没有内容时是空数组，不是缺这个键、更不是 404」。"""
    code = _code_only(COMPONENT)

    assert "rows.length === 0" in code
    assert "overview__empty" in code
    assert "Error" not in code


def test_each_section_has_its_own_empty_sentence() -> None:
    """三段的空态各说各的话，不是同一句「暂无数据」。

    同一句话会让用户以为这三样是同一件事——而「还没有主题」与
    「还没有交付物」隔着整条主链路。
    """
    code = _code_only(COMPONENT)

    for key in ("overview.topics.empty", "overview.jobs.empty",
                "overview.deliverables.empty"):
        assert key in code, key


def test_each_section_reports_its_own_count() -> None:
    code = _code_only(COMPONENT)

    assert "data-overview-count" in code
    assert "String(rows.length)" in code


# ───────────────────────── 三、零计算


def test_the_component_never_sorts_or_aggregates() -> None:
    code = _code_only(COMPONENT)

    assert ".sort(" not in code
    assert ".reduce(" not in code
    assert ".filter(" not in code
    assert "%" not in code


def test_a_row_without_a_state_renders_no_state_slot() -> None:
    """NEVER 编一个状态。"""
    code = _code_only(COMPONENT)

    assert "row.state ?" in code


# ───────────────────────── 四、token 纪律与 i18n


def test_no_hardcoded_token() -> None:
    code = _code_only(COMPONENT) + _code_only(PAGE)

    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", code)
    assert not re.search(r":\s*\d+px", code)


def test_every_string_shown_to_the_user_goes_through_i18n() -> None:
    for path in (COMPONENT, PAGE):
        for literal in re.findall(r"[\"'`]([^\"'`]*)[\"'`]", _code_only(path)):
            assert not re.search(r"[一-龥]", literal), \
                f"{path.name} 里有裸中文：{literal!r}"


def test_the_keys_exist_in_both_dictionaries() -> None:
    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))
    source = COMPONENT.read_text(encoding="utf-8") + PAGE.read_text(encoding="utf-8")
    used = set(re.findall(r't\("([^"]+)"', source))
    # 动态 key `overview.${name}` 的三个候选。
    used |= {"overview.topics", "overview.jobs", "overview.deliverables"}

    for key in used:
        assert key in zh, key
        assert key in en, key


def test_the_audit02_ruler_stays_green_on_this_component() -> None:
    done = subprocess.run(
        ["node", str(REPO / "tools" / "check_design_constraints.mjs"),
         str(REPO / "web"), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)
    report = json.loads(done.stdout)

    assert [f for f in report["findings"] if "project-overview" in f["file"]
            or "projects" in f["file"]] == []


# ───────────────────────── 五、取证实况


def _probe_rows() -> list[dict[str, object]]:
    if not PROBE.exists():
        pytest.skip("本机没跑过真栈冒烟：缺 .ui-probe/fe_smoke.json")
    report = json.loads(PROBE.read_text(encoding="utf-8"))
    if report.get("stack_down"):
        pytest.skip(f"上次实跑时栈没起：{report['stack_down']}")
    return [row for row in report["screens"] if row["route"] == ROUTE]


def test_the_new_screen_was_probed_in_both_themes() -> None:
    assert {str(row["theme"]) for row in _probe_rows()} == {"light", "dark"}


def test_the_new_screen_is_clean_on_the_real_stack() -> None:
    for row in _probe_rows():
        assert row["http_status"] == 200, row
        assert row["console_error_count"] == 0, row
        assert row["horizontal_overflow"] is False, row
        shot = REPO / ".ui-probe" / str(row["screenshot"])
        assert shot.exists() and shot.stat().st_size > 0, shot
