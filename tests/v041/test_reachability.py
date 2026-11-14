"""NAV-01：可达性尺子——**全仓三把尺子没有一把量路**。

## owner 是对的

owner 2026-08-09 亲自点过界面之后说「前端和后端还没有连接上」。
steward 上一条答「连上了」是错的：**那个回答量的是「端点回不回」，
owner 问的是「点不点得到」。**

实测（本卡复核过，与工单 §2 逐字吻合）：

```
22 屏 · 顶栏 2 项 · 站内链接目标 5 个 · 点得到 6 屏 · 孤岛 15 屏 + 豁免 1 屏
```

## 本卡只建图与尺子，**尺子先红着是对的**

接线归 `NAV-02~05`。所以 CLI 现在退出码是 1——**它红着才说明它在量**。
而本文件把当前的孤岛名单**钉成等值**：`NAV-02~05` 接一条线，这里就红一次，
逼人回来把名单改成实况。少一条要来删、多一条要停下登记（与既有基线同一套办法）。

## 三件事一起判，缺一件这把尺子就会说谎

1. **图遍历**，NEVER 用入度计数——`/projects/[id]/topics` 有一条真边指向它，
   而那条边的起点（`/combo`）自己走不到。按入度算它可达，按遍历算它不是。
   那种**二级孤岛**是最难被发现的一类。
2. **图与代码比对**：一份与代码对不上的图比没有图更坏，它会让人以为路查过了。
3. **两个方向自洽**：`/favorites` 有出口没入口——**只写出口的图查不出这一座**。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

GRAPH = REPO / "assets" / "screen_graph.json"
TOOL = REPO / "tools" / "check_reachability.py"
DOC = REPO / "docs" / "导航图-v041.md"

# 当前的孤岛名单。**判等值**：`NAV-02~05` 每接一条线这里就红一次，
# 逼人回来把名单改成实况。NEVER 改成「⊆」——那样接线接漏了也不会响。
# **空集**。ENTRY-05（2026-08-09）：最后六座一并拆掉，靠的是两张卡把功能做出来了——
# `ENTRY-04` 建了广场多选建组合（`/plaza -> /combo`，那条链的头），
# `PERSIST-02` 建了工作台三表与端点（入台那条边从「走不通」变成走得通）。
# 头一通，`/combo -> /projects/[id]/topics -> /projects/[id] -> analysis/proposal`
# 与 `/topics/[id]` **整条链跟着通**——那五屏自己一行都没改。
#
# 空集 NEVER 意味着「不再量」：这份名单判**等值**，凭空多一座当场红。
ISLANDS_TODAY: set[str] = set()
# 已经删掉的四行：`/account` `/favorites` `/design` `/settings/locale`
# ——`NAV-04` 把它们接进顶栏。**删这四行的动作，就是那四条线真接上了的签字。**
# `/billing` 也删掉了：`NAV-04` 决定它**从账户屏进**，不进顶栏。
# `NAV-05` 又拆下三座（报告的三个同族屏）。剩下这六座**内部已经连通**，
# 缺的是走进这一族的第一步——单据
# `docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md`。
# 15 → 14（NAV-03）→ 10（顶栏四项）→ 9（账户 → 账单）→ 6（NAV-05）。
# `NAV-03` 之后：`/workbenches/[id]` 从孤岛名单里出去了，**而它没进可达名单**——
# 它进的是第三格。前端已经接完（入台成功就跳过去），
# 而 `POST /workbenches` 那条端点没挂，所以那条路今天走不通。
# 三种状态各自成一态：把它算成可达是一句假话（屏上点不到），
# 把它留在孤岛里则掩盖了「前端已经接完了」。
# **空集**。`PERSIST-02` 建齐 `workbenches` / `graph_nodes` / `graph_edges` 三张表、
# 让 `POST /workbenches` 落库、并新建 `GET /workbenches/{id}`，
# 于是「路接上了而走不通」那一格今天没有住户。
# 第三格本身**没有取消**——下面那条判据仍然量它分不分得开。
BLOCKED_TODAY: set[str] = set()
# `NAV-02` 之后：广场 → `/clusters/[id]`（点卡片主体）。
# 这一行是**这条线真接上了的签字**——它是这把尺子第一次被人回来改。
REACHABLE_TODAY = {
    "/plaza", "/demo", "/gate/[id]", "/deliverables/[id]",
    "/deliverables/[id]/export", "/jobs/[id]", "/clusters/[id]",
    # NAV-04 的四条顶栏入口 + 账户屏里的账单入口。
    "/account", "/favorites", "/design", "/settings/locale", "/billing",
    # NAV-05：报告的三个同族屏（同一个交付物 id，链接无条件可点）。
    "/deliverables/[id]/quality", "/deliverables/[id]/pack",
    "/deliverables/[id]/interventions",
    # PERSIST-02：入台那条边走得通了。
    "/workbenches/[id]",
    # ENTRY-04 建了 `/plaza -> /combo`，整条项目链跟着通（ENTRY-05）。
    "/combo", "/projects/[id]/topics", "/projects/[id]",
    "/projects/[id]/analysis", "/projects/[id]/proposal", "/topics/[id]",
    # `WB-01` / `DEC-059`：计划书主工作台，顶栏第 7 项。
    # **它一进来就是可达的**——新增一屏而不是替换，入口与屏同一次落地；
    # 「先建屏、入口下一批再接」那种做法造出来的正是这把尺子在数的孤岛。
    "/workbench",
}
ENTRIES_TODAY = 7       # NAV-04 之前是 2；`WB-01` 新增「工作台」：6 → 7
SCREENS_TODAY = 24      # NAV-02 新建 `/clusters/[id]`：22 → 23；`WB-01` 新建 `/workbench`：23 → 24


def _check() -> object:
    from tools.check_reachability import check

    return check()


def _graph() -> dict[str, object]:
    return json.loads(GRAPH.read_text(encoding="utf-8"))


# ───────────────────────── 一、图与屏对得上


def test_every_screen_is_declared_in_the_graph() -> None:
    """22 屏**一屏不落**都在图里。

    漏一屏的话，它既不会被算成可达也不会被算成孤岛——**它会从这把尺子上消失**，
    而消失与「查过了没问题」在报告上长得一模一样。
    """
    report = _check()

    assert len(report.routes) == SCREENS_TODAY, f"屏数变了：{len(report.routes)}"
    assert report.undeclared_routes == [], f"这些屏没进图：{report.undeclared_routes}"
    assert report.stale_declarations == [], (
        f"图里这几条屏已经不存在了：{report.stale_declarations}")


def test_both_directions_are_written_for_every_edge() -> None:
    """每条 `goes_to` 在对面有一条对应的 `reached_by`。

    只写出口的话，`/favorites` 这种**有出口、没入口**的孤岛查不出来——
    它的出口指向广场，看起来很热闹，而没有任何一条边指向它。
    """
    report = _check()

    assert report.one_way_edges == [], f"这些边只写了一个方向：{report.one_way_edges}"


def test_the_graph_matches_the_code_both_ways() -> None:
    """图里有的边源码里要有；源码里有的边图里也要有。

    **一份与代码对不上的图比没有图更坏**——它会让人以为路已经查过了。
    """
    report = _check()

    assert report.edges_declared_not_in_code == [], (
        f"图里有、源码里没有：{report.edges_declared_not_in_code}")
    assert report.edges_in_code_not_declared == [], (
        f"源码里有、图里没声明：{report.edges_in_code_not_declared}")


# ───────────────────────── 二、当前实况（判等值，NAV-02~05 会让它红）


def test_the_islands_are_exactly_the_ones_on_record() -> None:
    """**本卡的实况判据**：孤岛名单逐条对得上。

    `NAV-01` 只建图与尺子。这份名单是 `NAV-02~05` 的工作清单，
    它每少一条就该有人回来删一行——**删那一行的动作，就是「这条线真接上了」的签字**。
    """
    report = _check()
    found = set(report.islands)

    assert found == ISLANDS_TODAY, (
        f"多出 {sorted(found - ISLANDS_TODAY)}，少了 {sorted(ISLANDS_TODAY - found)}")


def test_only_these_screens_are_reachable_today() -> None:
    """点得到的屏——owner 说的那件事，这里是它的机器形态。

    `NAV-01` 建这条判据时是 **6 屏**：`NAV-02` 接上卡片主体 → 7，
    `NAV-04` 补上四条顶栏入口 + 账户屏里的账单入口 → 12，
    `NAV-05` 接上报告的三个同族屏 → 15。
    **这个数每涨一格，都要有人回来改这一行。**
    """
    report = _check()

    assert set(report.reachable) == REACHABLE_TODAY, (
        f"可达集变了：{sorted(set(report.reachable) ^ REACHABLE_TODAY)}")
    assert len(report.entries) == ENTRIES_TODAY


def test_the_entries_match_the_top_bar_both_ways() -> None:
    """图里写的入口与顶栏 `NAV_ITEMS` 逐条对得上。

    图里凭空多一个入口，遍历就会**从一个屏上根本没有的地方出发**——
    于是一批孤岛被算成可达，而那正是这把尺子要治的那句假话。
    少一个也要报：顶栏上真有的入口没进图，图会低报可达面。

    顶栏的链接写成 `href={item.href}`（变量），边扫描器看不见它们，
    所以入口这一层**单独比对**。
    """
    from tools.check_reachability import nav_items

    report = _check()

    assert report.entry_mismatches == [], report.entry_mismatches
    assert sorted(nav_items()) == sorted(report.entries)


def test_there_are_six_link_targets_not_five() -> None:
    """**工单 §2 说 5 个，实测是 6 个**——少的那一个不是随便哪一个。

    工单列的 5 个全是 `href`：`/plaza` · `/gate/[id]` · `/deliverables/[id]`
    · `/deliverables/[id]/export` · `/jobs/[id]`。

    第 6 个是 `/combo` → `/projects/[id]/topics`，写法是提交回调里的
    `window.location.assign()`（`web/app/combo/page.tsx:50`）——**只扫 href 看不见它**。

    而它偏偏就是造出**二级孤岛**的那一条：正因为这条边真的存在，
    `/projects/[id]/topics` 的入度不为零；只有图遍历才能看出它照样点不到。
    **一把只扫 href 的尺子会同时漏掉这条边和这座孤岛。**
    """
    from tools.check_reachability import _alias, app_routes, code_edges

    routes = set(app_routes())
    targets = {_alias(dst, routes) for _, dst in code_edges()}

    assert targets == {
        "/plaza", "/gate/[id]", "/deliverables/[id]",
        "/deliverables/[id]/export", "/jobs/[id]",
        # `/combo -> /projects/[id]/topics`：工单少数的那第 6 条。
        # `NAV-05` 之后同一个目标又多了两条来路（项目总览、以及本行下面那批），
        # 而这里是**目标**的集合，所以它仍然只占一格。
        "/projects/[id]/topics",
        "/clusters/[id]",        # NAV-02 接上的那一条（同样是 location.assign）
        "/workbenches/[id]",     # NAV-03：入台成功之后
        # ENTRY-04 建的多选建组合：广场 → `/combo?clusters=`。
        # 它就是 ENTRY-05 拆掉最后六座孤岛的那条边——**那条链的头**。
        "/combo",
        "/billing",              # NAV-04：账户屏里的「查看额度与计费」（这条是 href）
        # NAV-05 接的那一批。它们在源码里都有，**而其中六个目标屏仍然是孤岛**：
        # 链接是真的，走进这一族的第一步还缺着（见上面的单据）。
        "/deliverables/[id]/quality", "/deliverables/[id]/pack",
        "/deliverables/[id]/interventions",
        "/projects/[id]", "/projects/[id]/analysis", "/projects/[id]/proposal",
        "/topics/[id]",
    }, f"站内链接目标变了：{sorted(targets)}"


def test_the_ruler_is_green_today_and_still_bites() -> None:
    """CLI 今天退出 0。**而它仍然咬得动**——两句话必须同时成立。

    这条判据原来断言的是「退出 1，它红着才说明它在量」（`NAV-01` 的原话：
    绿的尺子与不存在的尺子长得一模一样）。孤岛清零之后那句断言必须翻面，
    **而翻面最容易翻掉的正是那句话本身的意思**：
    一把永远绿的尺子与一把被人注释掉的尺子，从退出码上看一模一样。

    所以这里量两件事：今天真的是 0，**并且喂它一座人造孤岛时它当场变 1**。
    只留前一半的话，下一个人把 `check()` 改成 `return Report()` 也是绿的。
    """
    done = subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=REPO, timeout=300, check=False)

    assert done.returncode == 0, f"尺子还红着：{done.stdout[-400:]}"

    # 阴性对照：造一座孤岛喂给它，它必须红。
    graph = _graph()
    plaza = next(s for s in graph["screens"] if s["route"] == "/plaza")
    plaza["goes_to"] = [e for e in plaza["goes_to"] if e["to"] != "/combo"]
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "screen_graph.json"
        fake.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        from tools.check_reachability import check as _run

        assert _run(fake).islands, "拆掉那条边它还说没有孤岛——这把尺子已经不咬人了"


def test_a_wired_but_dead_path_is_its_own_state() -> None:
    """**第三格**：路接上了，而那条路今天走不通。

    `NAV-03` 把入台接到了 `/workbenches/[id]`。前端已经接完，
    而 `POST /workbenches` 那条端点**没挂**（实测框架 404 → `not_provided`），
    入台永远拿不到 `ok`，于是这条边今天走不通。

    三种状态 NEVER 合并（`DEC-032` 同口径）：

    | 状态 | 合并进去会说出的假话 |
    |---|---|
    | 算成可达 | 「这一屏点得到」——屏上点不到 |
    | 算成孤岛 | 掩盖「前端已经接完了」，下一个人会再接一遍 |

    尺子照样红：**走不通就是走不通**，第三格不是一张免罪符。
    """
    report = _check()

    assert {row.split("（")[0] for row in report.blocked_screens} == BLOCKED_TODAY
    assert set(report.blocked_screens) & set(report.islands) == set()
    assert BLOCKED_TODAY & set(report.reachable) == set(), (
        "走不通的屏被算进了可达——那正是这把尺子要治的那句假话")
    # 每一条都要写清**为什么**走不通，NEVER 只标一个 blocked 了事。
    for row in report.blocked_screens:
        assert "（" in row and len(row.split("（")[1]) > 10, f"没写清原因：{row}"


# ───────────────────────── 三、exempt 是给谁的


def test_exempt_is_for_screens_that_should_not_be_linked_from_inside() -> None:
    """豁免只给**本来就不该从站内点到**的屏，且每条写明理由。

    `NEVER 把「还没接线」写进 exempt 顶掉红`——待办就该红着。
    """
    graph = _graph()
    exempt = graph["exempt"]

    assert len(exempt) == 1, f"豁免不止一条了，逐条来确认：{exempt}"
    assert exempt[0]["route"] == "/share/[token]"
    assert "站外" in exempt[0]["why"], "没写清为什么站内不该有边指向它"
    assert "_never" in graph and "顶掉红" in graph["_never"]


def test_no_island_was_quietly_moved_into_exempt() -> None:
    """**阴性对照的一半**：孤岛名单与豁免名单**不许有交集**。

    把一条待接线的屏挪进 exempt，报告上会写「每一屏都走得到」——
    而那句话是假的。
    """
    report = _check()

    assert set(report.exempt) & ISLANDS_TODAY == set(), (
        "有孤岛被挪进了豁免名单")


# ───────────────────────── 四、阴性对照：摘掉一条链接，尺子必须报红并点名


def test_removing_one_link_turns_a_screen_into_an_island() -> None:
    """**本卡的核心阴性对照**：临时摘掉一条边，尺子 MUST 报红并指出哪一屏因此变成孤岛。

    没有这一条，「N 座孤岛」可能只是尺子把所有屏都算成孤岛——
    而那时它对真正的断链毫无感觉。

    ## 这条判据在 `NAV-05` 那天改过一次

    改前摘的是 `/plaza → /gate/[id]`，断言整条链掉下来。`NAV-05` 给
    `/jobs/[id]` 接上了「跑完了 → 查看判定」，于是判定屏**有了第二条路**
    （顶栏 → /demo → /jobs/[id] → /gate/[id]），摘一条不再让它掉下来。
    **它红的是自己的前提过期，不是尺子坏了**——而那正是本仓认得的第二种形状。

    改后摘 `/gate/[id] → /deliverables/[id]`：报告那一族只有这一条路进得去，
    摘掉它，报告与它的四个同族屏一起掉下来。**级联仍然量得到**，
    而判定屏自己因为有第二条路，照样在可达名单上——这一点比改前判得更细。
    """
    from tools.check_reachability import check

    graph = _graph()
    for screen in graph["screens"]:
        if screen["route"] == "/gate/[id]":
            screen["goes_to"] = []
        if screen["route"] == "/deliverables/[id]":
            screen["reached_by"] = [
                e for e in screen["reached_by"] if e["from"] != "/gate/[id]"
            ]

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "graph.json"
        path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        report = check(path)

    # 一刀切断的是一族：报告 + 导出 + 质量卡 + vibe_pack + 干预记录。
    for route in ("/deliverables/[id]", "/deliverables/[id]/export",
                  "/deliverables/[id]/quality", "/deliverables/[id]/pack",
                  "/deliverables/[id]/interventions"):
        assert route in report.islands, f"摘掉链接之后 {route} 没被报成孤岛"
    assert "/gate/[id]" in report.reachable, "判定屏自己有第二条路，不该受影响"
    assert "/plaza" in report.reachable, "入口自己不该受影响"


def test_an_edge_that_is_only_in_the_graph_is_reported() -> None:
    """**阴性对照②**：往图里加一条源码里没有的边，尺子必须报出来。

    没有这一条，任何人都能靠**在图里画一条线**把孤岛变成可达的——
    而屏上还是点不到。
    """
    from tools.check_reachability import check

    graph = _graph()
    for screen in graph["screens"]:
        if screen["route"] == "/plaza":
            screen["goes_to"].append({
                "to": "/favorites", "how": "编的", "where": "web/app/plaza/page.tsx",
            })
        if screen["route"] == "/favorites":
            screen["reached_by"].append({
                "from": "/plaza", "how": "编的", "where": "web/app/plaza/page.tsx",
            })

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "graph.json"
        path.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        report = check(path)

    assert any("/favorites" in row for row in report.edges_declared_not_in_code), (
        "在图里画一条线就能把孤岛变成可达的——尺子没有比对源码")


def test_a_second_level_island_is_not_counted_as_reachable() -> None:
    """**阴性对照③**：入度不为零、但起点走不到的屏**仍然是孤岛**。

    `/projects/[id]/topics` 曾经就是这一种：`/combo` 真的指向它，
    而 `/combo` 自己点不到。按入度算它可达，按遍历算它不是——
    **而按入度算的那把尺子，会把这一座永远藏起来**。

    ENTRY-05 之前这条判据指着一座**真的**二级孤岛（`/projects/[id]/topics`：
    `/combo` 真的指向它，而 `/combo` 自己点不到）。那座孤岛今天没了——
    `ENTRY-04` 把 `/plaza -> /combo` 接上了。

    **但这条判据要量的能力一点都不能少**：它量的是「遍历」与「数入度」的区别，
    而不是那一座具体的屏。所以改成喂一张**人造图**：
    真图里删掉那条头边，`/projects/[id]/topics` 立刻退回二级孤岛。
    照入度算它有来路，照遍历算它点不到——**尺子必须站在遍历这一边**。
    """
    graph = _graph()
    plaza = next(s for s in graph["screens"] if s["route"] == "/plaza")
    plaza["goes_to"] = [e for e in plaza["goes_to"] if e["to"] != "/combo"]

    incoming = next(
        s for s in graph["screens"] if s["route"] == "/projects/[id]/topics")
    assert incoming["reached_by"], "这条判据的前提没了：那条真边不在了"

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "screen_graph.json"
        fake.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
        from tools.check_reachability import check as _run

        islands = set(_run(fake).islands)
    assert "/projects/[id]/topics" in islands, "二级孤岛被算成了可达"
    # 真图里它是可达的——两句一起才说明尺子量的是**这张图**，不是一个写死的答案。
    assert "/projects/[id]/topics" not in set(_check().islands)


# ───────────────────────── 五、文档与全局门


def test_the_graph_is_written_up_for_humans() -> None:
    """导航图有一份人读的版本，且写明**三把旧尺子各自不量什么**。

    只有 JSON 的话，下一个人看不出「为什么需要第四把尺子」——
    而那正是这张卡存在的理由。
    """
    assert DOC.exists(), "没有人读的导航图"
    text = DOC.read_text(encoding="utf-8")

    for ruler in ("GAUGE-13", "GAUGE-12", "check_fe_be_parity"):
        assert ruler in text, f"没写清 {ruler} 不量什么"
    assert "16" in text or "15" in text, "没写清今天有多少座孤岛"


def test_the_ruler_is_wired_into_the_global_gate_list() -> None:
    """接进全局门——**NEVER 只跑一次就算**。

    这条判据是本批的地基：`NAV-02~05` 每接一条线都要它来量。
    只在本卡跑一次的话，第 9 批的人不会知道它存在。
    """
    text = DOC.read_text(encoding="utf-8")

    assert "check_reachability" in text
    assert "pytest" in text, "文档里没写它怎么被持续跑到"
