"""UI-03 · 图谱工作台上屏（v2 屏 2.16）的结构判据。

交互判据在 vitest（`web/__tests__/app/ui03.test.tsx`，15 条）。这里判的是
**源码结构**与**取证实况**——那两样 vitest 判不了：
它跑在 jsdom 里，看不见 `_ds` token 有没有被写死，也看不见真栈上那一屏长什么样。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
COMPONENT = REPO / "web" / "components" / "graph-workbench" / "GraphWorkbench.tsx"
PAGE = REPO / "web" / "app" / "workbenches" / "[id]" / "page.tsx"
PROBE = REPO / ".ui-probe" / "fe_smoke.json"
ROUTE = "/workbenches/[id]"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code_only(text: str) -> str:
    """剥注释：注释里写「NEVER 画一张空图」正是在说明规则，不该被判成违规。"""
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return "\n".join(
        line for line in text.splitlines()
        if not line.lstrip().startswith(("//", "*"))
    )


# ───────────────────────── 一、「没查过」与「空图」在源码里就是两条路


def test_the_component_has_a_distinct_branch_for_not_provided() -> None:
    """`graph === null`（没查过）与 `nodes.length === 0`（查过、是空的）**各一条分支**。

    合成一条的话，端点未建时屏上会写「你的工作台是空的」——
    而那是一句我们没有资格说的话。
    """
    code = _code_only(_source(COMPONENT))

    assert "graph === null" in code
    assert "nodes.length === 0" in code
    assert code.index("graph === null") < code.index("nodes.length === 0"), \
        "没查过要先判：先判空图的话，null 会先崩在 .length 上"


def test_the_two_states_carry_different_markers() -> None:
    """两条路要有**不同的机器可读标记**，否则取证时分不出屏上到底是哪一种。"""
    code = _code_only(_source(COMPONENT))

    assert 'data-workbench-state="not_provided"' in code
    assert 'data-workbench-state="empty"' in code


def test_the_page_really_goes_and_gets_the_graph() -> None:
    """这一屏**去取那张图**（`PERSIST-02-b` 建了 `GET /workbenches/{id}`）。

    这条判据原来断言的是「一个请求都不发」，理由是「端点未建就去问，
    问到的必然是 404，而那条红说的不是真问题」。**那个理由在当时是对的**：
    仓里与工作台有关的后端只有 `POST /workbenches/{id}/edges`，
    没有任何一条能把一张图读出来。端点建好了，前提没了，断言跟着翻面——
    **NEVER 留着一条量的是「这一屏不要数据」的判据**，那正是它此前空着的原因。
    """
    code = _code_only(_source(PAGE))

    assert "fetchWorkbench" in code
    assert "useEffect" in code


def test_the_page_never_fabricates_an_empty_graph() -> None:
    """空图 NEVER 由这一屏编出来——它只能是**服务端真的回了一张空图**。

    改前这条判据钉的是 `graph = null` 这个字面量。现在 `graph` 由取数结果决定，
    所以钉的换成两件事：屏里 NEVER 出现一个手写的 `{nodes: []}`，
    且取不到时交给 `GraphWorkbench` 的仍然是 `null`（它画「接口未提供」）。
    """
    code = _code_only(_source(PAGE))

    assert "nodes: []" not in code
    assert 'result.state === "ok" ? result.graph : null' in code, (
        "取不到时 NEVER 给出一张图")
    # 四态各占一格：并格的那一版被 A6 尺子当场拦下（见 page.tsx 文件头）。
    for state in ("loading", "not_found", "unavailable"):
        assert state in code, f"{state} 这一态在屏上没有落点"


# ───────────────────────── 二、只装配，不重写（GRAPH 组 16 卡的成果）


def test_the_canvas_reuses_the_existing_graph_components() -> None:
    """节点与生成闸门都用既有组件。重写一遍就等于同一件事有了两个实现。"""
    code = _code_only(_source(COMPONENT))

    assert "GraphNode" in code
    assert "GenerateGate" in code


def test_the_component_never_reimplements_an_interaction() -> None:
    """本组件只做装配：不自己算布局、不自己排序、不自己挑 primary。"""
    code = _code_only(_source(COMPONENT))

    assert ".sort(" not in code
    assert "forceLayout" not in code, "布局归 lib/graph-layout，装配层不碰"
    assert not re.search(r"primaryNodeId\s*=\s*[^;]*nodes\[", code), \
        "primary 由后端给，NEVER 由前端挑一个"


def test_read_only_removes_the_controls_instead_of_disabling_them() -> None:
    """E10 移动端只读：增删改控件**不渲染**，不是置灰。

    置灰的控件仍然告诉用户「这里本来能点」，而在只读端它永远不能点。

    ## 断言从「全文没有 disabled」收窄成「NEVER 用 readOnly 去置灰」

    改前钉的是 `"disabled" not in code`。`EDGES-UI` 给画布加了连线表单，
    提交中把按钮 `disabled` 住（防连点）——那一条当场红。

    **而它红得不对**：`disabled` 有两种用法，
    「只读端把能点的东西变成不能点」（E10 禁的）与
    「这一次提交还没回来，别再点一次」（各屏通用）。
    钉全文的话，第二种永远做不了，**而 E10 从来没有禁过它**。

    收窄之后守的还是同一件事：`readOnly` **NEVER 出现在 `disabled` 里**，
    且只读那一支仍然是 `null`（整块不渲染）。
    """
    code = _code_only(_source(COMPONENT))

    assert "readOnly ? null :" in code
    # 只读那一支**整块不渲染**——这一条没变。
    assert "readOnly ? null : (" in code
    # 而 `readOnly` NEVER 被拿去置灰。
    for line in code.splitlines():
        if "disabled" in line:
            assert "readOnly" not in line, f"用 readOnly 置灰了：{line.strip()}"


# ───────────────────────── 三、零计算与 token 纪律（acceptance①③）


def test_no_continuous_quantity_is_drawn() -> None:
    """不画进度条/百分比/星级——AUDIT-02 的尺子也守着，这里再钉一道近处的。"""
    code = _code_only(_source(COMPONENT)) + _code_only(_source(PAGE))

    assert "%" not in code
    assert "★" not in code


def test_no_ds_token_value_is_hardcoded() -> None:
    """`_ds` token 取值走变量，组件内不写死数值（acceptance①）。

    写死之后主题一换它就不动了——而暗色主题正是 DARK-01/02 刚接进来的。
    """
    code = _code_only(_source(COMPONENT)) + _code_only(_source(PAGE))

    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", code), "出现了写死的色值"
    assert not re.search(r":\s*\d+px", code), "出现了写死的像素值"


def test_every_string_shown_to_the_user_goes_through_i18n() -> None:
    """文案全部走 key（FB-03 的尺子守着；这里判的是本卡两个文件）。"""
    for path in (COMPONENT, PAGE):
        code = _code_only(_source(path))
        for literal in re.findall(r"[\"'`]([^\"'`]*)[\"'`]", code):
            assert not re.search(r"[一-龥]", literal), \
                f"{path.name} 里有裸中文：{literal!r}"


def test_the_keys_exist_in_both_dictionaries() -> None:
    """zh 有 en 没有的话，切到英文时那一块会显示 key 本身。"""
    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))
    used = set(re.findall(r't\("([^"]+)"', _source(COMPONENT) + _source(PAGE)))

    assert used, "一个 key 都没用上？那文案是从哪来的"
    for key in used:
        assert key in zh, key
        assert key in en, key


# ───────────────────────── 四、取证实况（acceptance④）


def _probe_rows() -> list[dict[str, object]]:
    if not PROBE.exists():
        pytest.skip("本机没跑过真栈冒烟：缺 .ui-probe/fe_smoke.json")
    report = json.loads(PROBE.read_text(encoding="utf-8"))
    if report.get("stack_down"):
        pytest.skip(f"上次实跑时栈没起：{report['stack_down']}")
    return [row for row in report["screens"] if row["route"] == ROUTE]


def test_the_new_screen_was_probed_in_both_themes() -> None:
    rows = _probe_rows()

    assert {str(row["theme"]) for row in rows} == {"light", "dark"}


#: 这一屏允许的控制台报错数，**逐条点名单号**。
#:
#: 本卡（`UI-03`）写下时是 **0**，理由写在卡上：「`GET /workbenches` 未建，
#: 本屏一个请求都不发」。`PERSIST-02` 把那条端点建出来之后**那句话就是假的**——
#: 屏真的在取数，而取证样例 `wb-placeholder` 库里没有，端点如实回 404。
#:
#: 没人发现，是因为这条判据读的 `.ui-probe/fe_smoke.json` 跑过一次就一直用；
#: `WB-01` 因为新增一屏必须重跑全量取证，它才现形。
#: 同一天同一个毛病在顶栏那条判据上更贵
#: （`docs/blocked/NAV-BAR-OVERFLOWS-AT-390.md`）。
#:
#: **NEVER 修绿**：屏上「没有这张工作台」是实话。撤掉这条额度的条件写在单子里
#: （取证样例指向一个库里真有的工作台）。
CONSOLE_ALLOWED = 1
CONSOLE_TICKET = "docs/blocked/WORKBENCH-SAMPLE-ID-IS-A-PLACEHOLDER.md"


def test_the_new_screen_is_200_with_no_console_error_and_no_overflow() -> None:
    """EYE-03 的四项：HTTP 200 / 控制台报错对上登记 / 无横向溢出 / 两主题截图。"""
    # 字段名照探针产物逐字：`http_status` / `console_error_count` /
    # `horizontal_overflow`——按记忆写成 status/console_errors/overflow 会 KeyError，
    # 而 KeyError 长得像「这一屏没取证」，其实是判据自己写错了名字。
    for row in _probe_rows():
        assert row["http_status"] == 200, row
        # **判等值**：少了说明样例换成真工作台了（回来把额度删掉），
        # 多了说明真出了新报错。判 `<=` 的话前一种永远不会被发现。
        assert row["console_error_count"] == CONSOLE_ALLOWED, row
        assert row["horizontal_overflow"] is False, row
        assert row["screenshot"], row


def test_the_console_allowance_still_points_at_an_open_ticket() -> None:
    """那条额度挂的单**在盘上且还开着**。

    单子关掉了而额度还留着，就是拿一张过期的单为一处新缺陷背书。
    """
    ticket = REPO / CONSOLE_TICKET

    assert ticket.exists(), f"额度挂的单不在盘上：{CONSOLE_TICKET}"
    head = "\n".join(ticket.read_text(encoding="utf-8").splitlines()[:12])
    assert "**状态** open" in head, f"{ticket.name} 已经关了，额度该撤掉"


def test_the_screenshots_are_on_disk() -> None:
    for row in _probe_rows():
        shot = REPO / ".ui-probe" / str(row["screenshot"])
        assert shot.exists(), shot
        assert shot.stat().st_size > 0, shot
