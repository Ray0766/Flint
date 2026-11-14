"""NAV-03：「入台」按成功之后要把人带过去。

## 改前的实况（本卡复核过）

三个动作按钮**真的在调后端**——`cardActions` 的三条，实测答复各不相同：

| 动作 | 端点 | 实测 |
|---|---|---|
| 收藏 | `POST /favorites` | `{"status":"not_provided",…}` |
| 分享 | `POST /shares` | `422 {"allowed":[…]}` |
| 入台 | `POST /workbenches` | **框架的 404**（没有 `code`）= 路由未挂 |

而三条**按完都停在原地**。owner 裁决 `DEC-042` ②：
**「入台」才是进图谱工作台的那条路。**

## 这条路今天走不通，而前端已经接完

`POST /workbenches` 没挂，入台永远拿不到 `ok`，所以真栈上跳不过去。
`NAV-01` 的尺子为此有**第三格**：`blocked_screens`——
算成可达是一句假话（屏上点不到），算成孤岛则掩盖了「前端已经接完了」。

## 呈现行为归 vitest 守

`web/__tests__/app/nav03.test.tsx`（本文件用 subprocess 把它拉进全局门）：
成功导航 · 失败不导航 · 收藏分享不导航 · 三种回执各说各的。
这里守 vitest 够不着的三件：**去哪一个由服务端说**、
**第三格在图上记着**、以及**这条边在源码里量得到**。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
CARDS = WEB / "components" / "plaza" / "PlazaCards.tsx"
ACTIONS_TS = WEB / "components" / "plaza" / "cardActions.ts"
ACTIONS = WEB / "components" / "hotspot-card-actions" / "HotspotCardActions.tsx"
SPEC = WEB / "__tests__" / "app" / "nav03.test.tsx"
GRAPH = REPO / "assets" / "screen_graph.json"
ZH = WEB / "messages" / "zh.json"
EN = WEB / "messages" / "en.json"


def _npx() -> str:
    """npx 的绝对路径。

    原先写的是 `subprocess.run(["npx", ...], shell=True)`：Windows 上靠 shell 找到 `npx.cmd`，
    而 POSIX 上 `shell=True` 配参数列表只执行第一个词——`npx` 空跑、退出码 0、
    vitest 一条都没跑。只判退出码的判据在那里是假绿。
    """
    npx = shutil.which("npx")
    assert npx is not None, "找不到 npx：这条量不了，NEVER 当它通过"
    return npx


def _code_only(path: Path) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", path.read_text(encoding="utf-8"))
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )


# ───────────────────────── 一、去哪一个工作台由服务端说


def test_the_target_comes_from_the_server_not_from_the_cluster_id() -> None:
    """`NEVER 前端自己跳到一个编出来的工作台 id`（`addToWorkbench` 文件头的原话）。

    拼一个跳过去，用户会落进一个**不存在的图谱**，并以为是自己的数据丢了。
    """
    code = _code_only(CARDS)

    assert "workbenchTarget(outcome)" in code, "去哪一个不是从服务端答复里读的"
    # 拼一个的形状：把 cluster id 塞进工作台路径。
    assert "workbenches/${clusterId}" not in code
    assert not re.search(r"`/workbenches/\$\{[^}]*cluster", code)


def test_only_one_name_is_accepted_for_the_target_id() -> None:
    """`graph_id` 是冻结件里的名字，也是既有路由 `POST /workbenches/{graph_id}/edges` 用的。

    认第二个别名的话，服务端哪天改口，前端会**安静地跳到另一处**，
    而两边都以为自己对。
    """
    code = _code_only(ACTIONS_TS)

    assert 'detail["graph_id"]' in code
    assert "workbench_id" not in code, "认了第二个别名"


def test_an_ok_without_a_target_stays_put_and_says_so() -> None:
    """「成了、却不知道去哪一个」与「失败」是**两件事**，NEVER 合并。

    前者用户的东西已经存下了，后者没有。把前者说成失败，用户会再按一次；
    把它说成成功而什么都不做，用户会以为按键坏了。
    """
    code = _code_only(CARDS)

    assert "setNavMissing(clusterId)" in code
    assert "card.action.workbench_no_target" in code


# ───────────────────────── 二、只有入台导航


def test_favorite_and_share_never_navigate() -> None:
    """它们是**动作**，不是去处。

    把人带走的话，他刚点的那张卡就没了，而他多半还想接着看别的。
    """
    code = _code_only(CARDS)
    hop = re.search(r"void call\(API_BASE[\s\S]*?\n  \};", code)

    assert hop, "找不到三动作的回调"
    assert 'if (of !== "workbench") return;' in hop.group(0)


def test_a_failed_post_never_navigates() -> None:
    """**阴性对照的源码半边**：失败时留在原地。

    运行时那一半在 vitest 里（让 POST 回 500 / 404，断言没跳走且屏上出现原因）。
    """
    code = _code_only(CARDS)

    assert 'if (outcome.kind !== "ok") return;' in code, "失败也会跳走"
    # 顺序要紧：判 kind 必须在 assign 之前。
    assert code.index('outcome.kind !== "ok"') < code.index("location.assign")


def test_the_refusal_sentence_still_comes_from_the_server() -> None:
    """`NEVER 用一句「操作失败」盖住后端说的话`。

    三种「不成」是三件事（`cardActions` 文件头那张表），混成一句，
    用户与下一个读代码的人都无从知道该做什么。
    """
    code = _code_only(ACTIONS)

    assert "outcome.message" in code, "后端自己的说明没被带出来"
    for kind in ("not_provided", "unsupported", "failed"):
        assert kind in code, f"{kind} 这一种没有自己的话"


def test_the_note_is_a_second_line_not_a_replacement() -> None:
    """那句补充与结果**同时**出现：结果说「已完成」，补充说「没能带你过去」。

    塞进 `outcome` 会让「成了」变成「没成」——那是一句假话。
    """
    code = _code_only(ACTIONS)

    assert 'data-testid="action-note"' in code
    assert code.index('data-testid="action-outcome"') < code.index('data-testid="action-note"')


# ───────────────────────── 三、这条边在图上、在尺子里


def test_the_edge_is_declared_and_walks_through_now() -> None:
    """路接上了，而且那条路**今天走得通**了。

    这条判据原来断言的是第三格「接上了、走不通」：`NAV-03` 接完了前端，
    而 `POST /workbenches` 回的是框架 404（表没建），入台永远拿不到 `ok`。
    `PERSIST-02` 建齐 `workbenches` / `graph_nodes` / `graph_edges` 三张表、
    让那条端点落库、并新建 `GET /workbenches/{id}`——**挡着的那件事被做掉了**。

    翻面之后仍然要盯住两头：这条边**还在**（NEVER 因为通了就不声明），
    且那一屏**真的进了可达集**（NEVER 停在「不算孤岛」这种半绿状态）。
    第三格本身没有取消——`test_reachability.py` 那边仍然量它分不分得开。
    """
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    plaza = next(s for s in graph["screens"] if s["route"] == "/plaza")
    edge = next(e for e in plaza["goes_to"] if e["to"] == "/workbenches/[id]")

    assert "blocked" not in edge, "这条边还标着走不通——PERSIST-02 之后它通了"
    assert "PERSIST-02" in edge.get("when", ""), "没写清是什么让它通的"

    from tools.check_reachability import check

    report = check()
    assert not any(row.startswith("/workbenches/[id]")
                   for row in report.blocked_screens)
    assert "/workbenches/[id]" not in report.islands
    assert "/workbenches/[id]" in report.reachable


def test_the_navigation_is_a_literal_the_rulers_can_see() -> None:
    """两把尺子都要量得到这条边，**而它们要的东西正好相反**。

    - `NAV-01` 可达性尺子：把它算成一条**边**；
    - `check_fe_be_parity`：**NEVER** 把它算成一次 API 调用（导航不是调用）。

    第二条在本卡当场红过一次：对账表把 `/clusters/{}` 与 `/workbenches/{}`
    报成「前端要而后端没有」，两条都是假的——那把尺子只排 `href`，
    而 `NAV-02/03` 用的是 `location.assign`。见 `tools/check_fe_be_parity.py#_NAV`。
    """
    from tools.check_fe_be_parity import parity
    from tools.check_reachability import _alias, app_routes, code_edges

    routes = set(app_routes())
    edges = {(src, _alias(dst, routes)) for src, dst in code_edges()}
    assert ("components/plaza/PlazaCards.tsx", "/workbenches/[id]") in edges

    subjects = {f.subject for f in parity(REPO)}
    for navigation in ("/workbenches/{}", "/clusters/{}"):
        assert navigation not in subjects, (
            f"对账表把一次跳转当成了 API 调用：{navigation}")


# ───────────────────────── 四、文案与 vitest 一起进全局门


def test_the_new_copy_is_keyed_in_both_languages() -> None:
    zh = json.loads(ZH.read_text(encoding="utf-8"))
    en = json.loads(EN.read_text(encoding="utf-8"))
    key = "card.action.workbench_no_target"

    assert key in zh and key in en
    assert zh[key] != en[key], "中英同文——有一侧没翻"


def test_no_hardcoded_chinese_in_the_touched_components() -> None:
    for path in (CARDS, ACTIONS, ACTIONS_TS):
        for literal in re.findall(r'"([^"]*)"', _code_only(path)):
            assert not re.search(r"[一-鿿]", literal), (
                f"{path.name} 里有裸中文：{literal!r}")


def test_the_front_end_spec_runs_green() -> None:
    """把 vitest 那一组拉进全局门——**NEVER 只在开发时手跑一次**。

    成功导航、失败不导航、`graph_id` 只认一个名字，全在那边。
    """
    done = subprocess.run(
        [_npx(), "vitest", "run", "__tests__/app/nav03.test.tsx"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=WEB, timeout=900, check=False)

    assert done.returncode == 0, (done.stdout or "")[-3000:] + (done.stderr or "")[-1500:]


def test_the_negative_control_is_in_the_spec() -> None:
    """卡上点名的阴性对照：**让 POST 返回失败，断言没跳走且屏上出现原因**。

    只测 happy path 的话，「失败也跳走」这个缺陷会一路绿灯——
    而它的后果是用户被带进一个空工作台，还以为自己成功了。
    """
    spec = SPEC.read_text(encoding="utf-8")

    assert "reply(500" in spec, "没有失败那一路"
    assert "reply(404" in spec, "没有「还没接」那一路"
    assert spec.count("expect(went).toEqual([])") >= 4, "没有逐条断言「没跳走」"
