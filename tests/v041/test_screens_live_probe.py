"""WIRE-04 · 十三张屏逐屏真栈取证（明暗两主题）。

## 这张卡为什么不是「再跑一遍冒烟」

`WIRE-03` 把四张屏接上了真端点。**接线之前那几条渲染路径根本走不到**——
组件收 `null` 就直接返回「接口未提供」，下面的列表一行都不渲染。

本卡首跑当场抓到两处，都是只有真数据才看得见的：

1. **后端进程是旧的**。`/account` 等四条在 `:8000` 上 404，而直连
   `create_app` 是 200——跑着的是 2026-08-04 22:55 启动的进程，
   只有装配前的七族。取证忠实反映了它。重启后端后四屏转绿。
2. **`/projects/[id]` 控制台一条 React key 警告**。根因是 `WIRE-03` 给
   account/billing 写了适配层，却把项目总览的后端 JSON **直接喂给了组件**：
   后端给 `topic_id` 与整个领域对象，组件要 `{id, label, state}`，
   于是 `key={row.id}` 全是 `undefined`。已补 `toProjectOverviewView`。

两处都不是「样式没对齐」这一类。**它们是接线之后才存在的缺陷**，
而单测拿假数据喂组件永远碰不到。

## 判据判等值，不判「零报错」

盘上还有两屏带既有报错（`/deliverables/[id]` 10 条 · `/gate/[id]` 1 条），
各自挂着单子。判零会把别人的活算成本卡失败；不判会让新增的报错混进来。
所以判**等值**：数字一变就要有人回到这里确认是修好了还是又坏了。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROBE_DIR = REPO / ".ui-probe"
REPORT = PROBE_DIR / "fe_smoke.json"

# 盘上此刻带报错的屏，各自挂着单子。**判等值**：修好了会红（提醒来改这里），
# 又多了也会红。NEVER 判「零报错」——那会把别人的活算成本卡失败。
# `FIX-06` 全量取证时这份登记面**两处都变了**，两处都是好消息：
#
# - `/deliverables/[id]` 10 → **3**：`FIX-02` 把 `DEMO-REPORT-REFS-NOT-SEEDED`
#   那九个引用补种了六个（单子已关）；剩下三个是
#   `DEMO-REFS-NO-STORAGE-FACE`（chart / 质量卡 / gap hints **全库没有存储面**），
#   端点如实回 404——**当前行为是对的，NEVER 修绿**，所以换挂那张仍 open 的单；
# - `/gate/[id]` 1 → **0**：那条报错的根不是产品，是**探针给错了地址**——
#   样例 id 填的 `m1004-j` 没有 verdict 快照。`FIX-06` 换成
#   `job-gate1-live-qwen`（demo 库里唯一有判定的 job）之后，这一屏取证的是
#   真判定而不是「没查到」，报错随之归零。整行因此从登记面删掉。
#
# 第 5 批又变了两处，**两处都不是产品坏了**：
#
# - `/jobs/[id]` 0 → **1**：第 4 批接上鉴权之后，探针用的样例作业 `m1004-j`
#   **不属于探针那个用户**，端点正确地回 403，红的是取证样例没跟着鉴权口径对齐；
# - `/topics/[id]` 新增 **1**：`CHAIN-03` 新建的主题详情屏。demo 库当日一条主题都没有
#   （造主题属种子数据，是 owner 面），所以样例 id 是占位串，
#   后端正确地回带 `code` 的 404。屏上原样带出它的说明——**当前行为是对的**。
#
# 第 6 批又变了两处：
#
# - `/jobs/[id]` 1 → **0**：`FIX-09`（`DEC-037`）种了一条属于探针自己的作业
#   （`probe-owned-ingest`），样例改指它。**整行从登记面删掉**——
#   留着额度的话，将来这一屏真出一条报错时没人会发现。
#   **NEVER 把那条 403 加进容忍度**：那等于把鉴权正确工作的证据当成噪声吞掉。
#   （顺带纠正上一批写在这里的一句话：那时说「屏上的行为是对的（无权查看）」——
#   **屏上并没有那个态**，403 之后它停在加载骨架上。已立单
#   `docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`。）
# - `/topics/[id]` 的单号换了：原先引 `TOPIC-HAS-NO-NAME-TRIPLE`，
#   而那张单说的是「冻结件没有名称字段」，与「库里没有主题」是两件事；
#   `DEC-036` 把它关掉之后这一行指向了一张已关的单。
KNOWN_NOISY: dict[str, tuple[int, str]] = {
    "/deliverables/[id]": (3, "docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md"),
    # 下面两条是 `WB-01` 重跑全量取证时**现形**的，不是本批引入的。
    #
    # 它们一直在，只是这份报告改前是一份**旧照片**：三条判据都读
    # `.ui-probe/fe_smoke.json`，而那份文件是上一次跑冒烟时留下的。
    # 同一天在顶栏那条判据上，同样的「缓存不失效」让一次真实的 390 溢出
    # 被判绿了整整一批（`docs/blocked/NAV-BAR-OVERFLOWS-AT-390.md`）。
    #
    # 两条都是**端点如实回 404、屏上如实说**——NEVER 修绿：
    "/clusters/[id]": (1, (
        "docs/blocked/CLUSTER-SAMPLE-HAS-NO-VERDICT.md：GET /clusters/{id}/verdict "
        "对没有判定的簇回 404（实测样例 c-20260629-088：evidence-cards 200 而 "
        "verdict 404）——屏上如实显示「还没有判定」，NEVER 为了这条绿去猜一个判定")),
    "/workbenches/[id]": (1, (
        "docs/blocked/WORKBENCH-SAMPLE-ID-IS-A-PLACEHOLDER.md：取证样例 "
        "`wb-placeholder` 库里没有，GET /workbenches/{id} 如实回 404，"
        "屏上显示「没有这张工作台」")),
    # `/topics/[id]` 那条**第 7 批撤掉了**（`SEED-01` / `DEC-041`）：
    # `harness/demo_seed_topic.py` 种下一条夹具主题、取证样例指向它之后，
    # 那一屏拿到 200，**这条登记的理由没有了**。
    # NEVER 因为「反正它绿着」就留着——留着的话，这一屏哪天真退回 404，
    # 这张登记表不会响。
}
# `WIRE-03` 接了真端点的四张：它们**必须**零报错——
# 有报错就说明接线接坏了，而那正是本卡要抓的东西。
WIRED_BY_WIRE_03 = ("/account", "/billing", "/settings/locale", "/projects/[id]")
THEMES = ("dark", "light")


def _report() -> dict[str, object]:
    if not REPORT.exists():
        pytest.skip("本机没跑过真栈冒烟：缺 .ui-probe/fe_smoke.json")
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    if data.get("stack_down"):
        pytest.skip(f"上次实跑时栈没起：{data['stack_down']}")
    return data


def _rows() -> list[dict[str, object]]:
    return list(_report()["screens"])  # type: ignore[arg-type]


# ───────────────────────── acceptance①：逐屏取证


def test_every_screen_on_disk_was_probed_in_both_themes() -> None:
    """磁盘上有几张屏就取几张证，**两主题各一次**。

    「跳过一屏」在报告里长得像「那屏不存在」——所以这里判的是
    屏数 × 主题数，而不是「取到的都通过了」。
    """
    rows = _rows()
    by_route: dict[str, set[str]] = {}
    for row in rows:
        by_route.setdefault(str(row["route"]), set()).add(str(row["theme"]))

    pages = len(list((REPO / "web" / "app").glob("**/page.tsx")))
    assert len(by_route) == pages, f"磁盘 {pages} 张屏，取证覆盖 {len(by_route)} 张"
    for route, themes in by_route.items():
        assert themes == set(THEMES), f"{route} 只取了 {sorted(themes)}"
    # `FIX-06` 之后每屏每主题多量一个视口（desktop + mobile）。
    # **按报告里实际出现的视口数算，NEVER 写死 2**：再加一档视口时，
    # 写死的那个数会让这条判据红在一个没有错的地方。
    viewports = {str(row["viewport"]) for row in rows}
    assert viewports == {"desktop", "mobile"}, f"视口面变了：{sorted(viewports)}"
    assert len(rows) == pages * len(THEMES) * len(viewports)


def test_every_screen_answers_200_without_horizontal_overflow() -> None:
    for row in _rows():
        assert row["http_status"] == 200, row
        assert row["horizontal_overflow"] is False, row


def test_the_screens_wired_by_wire_03_are_console_clean() -> None:
    """`WIRE-03` 接了真端点的四张，**零控制台报错**。

    首跑时 `/projects/[id]` 有一条 React key 警告——根因是那一屏没走适配层，
    后端给 `topic_id`、组件要 `id`，`key` 全是 `undefined`。
    **传 `null` 时走不到那条渲染路径，所以接线前一直看不见。**
    """
    noisy = [
        (row["theme"], row["route"], row["console_error_count"])
        for row in _rows()
        if row["route"] in WIRED_BY_WIRE_03 and row["console_error_count"]
    ]

    assert noisy == [], f"接线后的屏有控制台报错：{noisy}"


def test_the_remaining_noise_is_exactly_the_registered_tickets() -> None:
    """**判等值**：还带报错的屏与登记面逐条对上，且单子在盘上。"""
    actual = {
        str(row["route"]): int(row["console_error_count"])  # type: ignore[arg-type]
        for row in _rows() if row["console_error_count"]
    }
    expected = {route: count for route, (count, _) in KNOWN_NOISY.items()}

    assert actual == expected, (
        f"控制台报错面变了。实测 {actual}，登记 {expected}——"
        f"少了说明修好了（来这里删一行），多了要停下登记"
    )
    for _, ticket in KNOWN_NOISY.values():
        # 登记项写成「单号：为什么」——取前半段当路径，与
        # `test_mobile_sweep.py#test_every_baselined_route_still_points_at_a_live_ticket`
        # 同一种取法。改前这里拿**整串**当路径，于是一条带解释的登记
        # 永远「单子不在盘上」，而单子就在那儿。
        #
        # 允许带解释是有意的：一个光秃秃的路径要读单子才知道那几条报错是什么，
        # 而**为什么允许**恰恰是这张表最该说清的一件事。
        path = ticket.split("：", 1)[0]
        assert (REPO / path).exists(), f"单子不在盘上：{path}"


# ───────────────────────── acceptance②：两主题真的不同


def test_the_two_themes_are_not_the_same_screenshot() -> None:
    """两主题量到同一组颜色即判红（`DARK-02` 建的前置判据，NEVER 关掉它）。

    截图字节相同 = 主题切换根本没生效，而两次「都通过了」看起来一模一样。
    """
    for row in _rows():
        if row["theme"] != "dark":
            continue
        # `FIX-06` 把视口写进了文件名（`plaza-dark-mobile.png`），
        # 原来的 `.replace("-dark.png", "-light.png")` **一个字符都匹配不上**，
        # 于是 light 与 dark 指向同一个文件、字节当然相同——
        # 判据红在一个没有错的地方。改成替换**主题那一段**。
        dark = PROBE_DIR / str(row["screenshot"])
        light = PROBE_DIR / str(row["screenshot"]).replace("-dark-", "-light-")

        assert light != dark, f"{row['screenshot']} 里找不到主题段：配对逻辑坏了"
        assert dark.exists() and light.exists(), f"{row['route']} 缺一张截图"
        assert dark.read_bytes() != light.read_bytes(), (
            f"{row['route']} 两主题截图逐字节相同：主题切换没生效"
        )


def test_the_theme_switch_gate_is_still_wired_in() -> None:
    """`DARK-02` 那条前置判据仍在全局门里——NEVER 关掉它。"""
    gate = REPO / "tests" / "v041" / "test_theme_really_switches.py"

    assert gate.exists(), "DARK-02 的前置判据不见了"
    source = gate.read_text(encoding="utf-8")
    # 那把尺子的核心：两主题量到同一组颜色就判红。改成「只要能切换」不算。
    assert "相同" in source or "same" in source.lower()


# ───────────────────────── acceptance③：阴性对照


def test_the_probe_would_go_red_if_a_screen_lost_its_styles(
        tmp_path: Path) -> None:
    """阴性对照：把一屏的取证数据改成「样式没加载」的样子，判据必须报红。

    做法是喂一份**改坏的报告**给同一套判据——比真去摘样式稳，
    且不必动仓库里的源码。
    """
    broken = json.loads(REPORT.read_text(encoding="utf-8")) if REPORT.exists() else None
    if broken is None:
        pytest.skip("缺取证报告")
    for row in broken["screens"]:
        if row["route"] == "/account":
            row["console_error_count"] = 3  # 样式没加载 → 一串 404
            row["horizontal_overflow"] = True

    noisy = [
        (r["theme"], r["route"])
        for r in broken["screens"]
        if r["route"] in WIRED_BY_WIRE_03 and r["console_error_count"]
    ]
    overflow = [r["route"] for r in broken["screens"] if r["horizontal_overflow"]]

    assert noisy, "改坏了却没被看出来——那两条判据是空的"
    assert overflow, "横向溢出没被看出来"


def test_the_probe_names_the_screenshot_for_every_row() -> None:
    """每一行都要指到一张真截图：没有截图的「通过」没法复核。"""
    for row in _rows():
        shot = PROBE_DIR / str(row["screenshot"])

        assert shot.exists() and shot.stat().st_size > 0, shot
        assert str(row["theme"]) in shot.name, f"{shot.name} 文件名里没有主题"


# ───────────────────────── acceptance④：探针地址不是编的


def test_no_dynamic_route_is_probed_with_a_stale_placeholder() -> None:
    """接了真端点的动态路由，样例 id **MUST 从库里查出来**。

    `fe_smoke.py` 自己的注释写过这条：首版给 `/jobs/[id]` 编了个
    `job-demo-fixture`，实跑当场现形（页面 200 但控制台一条 404）。
    `WIRE-03` 接上 `/projects/[id]` 之后，`p-placeholder` 会让它恒 404——
    同一个坑。本条盯着「已接线的动态路由不许用占位串」。
    """
    from harness.fe_smoke import SAMPLE_IDS

    wired_dynamic = {"/projects/[id]"}
    for route in wired_dynamic:
        sample = SAMPLE_IDS[route]

        assert "placeholder" not in sample, (
            f"{route} 已接真端点，样例 id 却还是占位串 {sample!r}——"
            f"那会让这屏恒 404，是一种假红"
        )


def test_a_parameter_named_something_other_than_id_is_substituted_too() -> None:
    """`/share/[token]` 这种非 `[id]` 参数也要替换掉。

    `WIRE-04` 实测：原先是 `route.replace("[id]", sample)`，
    `[token]` 替不掉，URL 里原样留着 `[token]`——于是 `SAMPLE_IDS` 里
    那一行是**死配置**，改它没有任何效果，而报告看起来一切正常。
    """
    from harness.fe_smoke import discover_screens

    screens = {s.route: s.url for s in discover_screens(REPO / "web")}

    assert "[" not in screens["/share/[token]"], screens["/share/[token]"]
    assert "share-placeholder" in screens["/share/[token]"]
