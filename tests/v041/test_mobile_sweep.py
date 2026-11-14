"""FIX-06 · 移动视口从来没有全量量过——逐屏补一遍。

## 「新被看见的」不是「新坏的」

`LOCALE-FORM-OVERFLOWS-ON-MOBILE` 那条 48px 溢出，是有人**手工单独**跑了一次
`ui_probe` 才看见的：常规冒烟（`harness/fe_smoke.py`）只跑 1440，
十三屏在 390px 下**从来没有人量过**。

靠偶然发现的东西，下一次就会靠偶然错过。所以本卡做的不是「再查一遍」，
而是**把移动视口接进常规取证**——此后每一次冒烟都自带这一半。

## 实测：屏不是十三张，是十六张

卡面写的是「十三张屏」。`discover_screens` 从磁盘数出来的是 **16**——
`web/app/**/page.tsx` 有几个文件就有几张屏。
**判据按磁盘数，NEVER 按卡面那个数**：写死 13 的话，新增一屏永远不会被量到，
而报告看起来是全绿的。

## 修完之后移动端零溢出，因为根因只有一处

`FIX-05` 修的 `.app-shell__body` 是**所有屏共用的容器**。
本卡全量量下来 `mobile_overflow == 0`——这既是本卡的结论，
也反过来印证了 `FIX-05` 找的那个根因是对的（若还有别的溢出源，这里会剩下几条）。

## 控制台报错：**判等值，不判零**

报告屏那 3 条 404 是 `DEMO-REFS-NO-STORAGE-FACE` 登记的**正确行为**
（chart / 质量卡 / gap hints 全库没有存储面，端点如实回 404）。
判零会把别人正确的行为算成本卡失败；顺手放行则会让下一条新增的报错混进来。
所以逐屏对一份**点名了单号**的基线。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from harness.fe_smoke import (
    VIEWPORTS,
    build_report,
    discover_screens,
    screenshot_name,
)

REPORT = REPO / ".ui-probe" / "fe_smoke.json"
SHOTS = REPO / ".ui-probe"
WEB = REPO / "web"
THEMES = ("dark", "light")

# 允许非零的控制台报错，**逐条点名单号**。空 = 该屏必须零报错。
CONSOLE_BASELINE: dict[str, tuple[int, str]] = {
    "/deliverables/[id]": (3, (
        "docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md：chart / 质量卡 / gap hints "
        "全库没有存储面，端点如实回 404——**当前行为是对的，NEVER 修绿**")),
    # 下面两条是 `WB-01` 重跑全量取证时**现形**的，不是本批引入的——
    # 改前三条判据读的都是同一份**旧照片**（`.ui-probe/fe_smoke.json`）。
    # 两条都是端点如实回 404、屏上如实说，**NEVER 修绿**：
    "/clusters/[id]": (1, (
        "docs/blocked/CLUSTER-SAMPLE-HAS-NO-VERDICT.md：GET /clusters/{id}/verdict "
        "对没有判定的簇回 404（实测样例 c-20260629-088：evidence-cards 200 而 "
        "verdict 404）——屏上如实显示「还没有判定」，NEVER 为了这条绿去猜一个判定")),
    "/workbenches/[id]": (1, (
        "docs/blocked/WORKBENCH-SAMPLE-ID-IS-A-PLACEHOLDER.md：取证样例 "
        "`wb-placeholder` 库里没有，端点如实回 404，屏上显示「没有这张工作台」")),
    # `/jobs/[id]` 那一行**第 6 批删掉了**（`FIX-09` / `DEC-037`）：
    # 样例换成了探针自己的那条作业，这一屏于是零报错。
    # 留着额度的话，将来真出一条报错时没人会发现。
    # **NEVER 把 403 加回来**——那等于把鉴权正确工作的证据当成噪声吞掉。
    # `/topics/[id]` 那一行**第 7 批撤掉了**（`SEED-01` / `DEC-041`）。
    #
    # 它当初是为「demo 库一条主题都没有、样例 id 是占位串」开的额度——
    # `harness/demo_seed_topic.py` 种下一条夹具主题、`fe_smoke` 的样例指向它之后，
    # 那一屏拿到 200，**额度的理由没有了**。
    #
    # **NEVER 因为「反正它绿着」就把额度留着**：额度还在的话，
    # 这一屏哪天真退回 404，判据不会响——而那正是额度存在的全部代价。
    #
    # 这一行在被撤掉之前，单号**换过一次**（第 6 批）。原先引的是
    # TOPIC-HAS-NO-NAME-TRIPLE，而那张单说的是「规格要名称三元组而冻结件没有那两个
    # 字段」——与「库里没有主题」是两件事。`DEC-036` 把它关掉之后这条判据当场红，
    # **那是一次有用的红**：它逼出了「基线的理由从一开始就写错了」。
}


def _report() -> dict:
    if not REPORT.exists():
        pytest.skip(
            "本机没跑过全量取证：缺 .ui-probe/fe_smoke.json——"
            "跑法 C:\\pwenv\\Scripts\\python.exe harness/fe_smoke.py")
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    if data.get("stack_down"):
        pytest.skip(f"上次实跑时栈没起：{data['stack_down']}")
    if not any(r.get("viewport") == "mobile" for r in data["screens"]):
        pytest.fail("取证里一条 mobile 行都没有——那就等于没量（重跑 fe_smoke）")
    return data


def _mobile() -> list[dict]:
    return [r for r in _report()["screens"] if r["viewport"] == "mobile"]


# ───────────────────────── acceptance②：移动视口进了常规取证


def test_the_regular_smoke_run_now_includes_a_mobile_viewport() -> None:
    """常规冒烟自带 390px 这一档——**不再靠有人想起来单独跑一次**。"""
    names = {name for name, _w, _h in VIEWPORTS}

    assert "mobile" in names and "desktop" in names, VIEWPORTS
    assert {n: w for n, w, _h in VIEWPORTS}["mobile"] == 390


def test_screenshot_names_carry_the_viewport() -> None:
    """截图名带视口。

    不带的话 mobile 会把 desktop 那张**覆盖掉**，而报告里两行指着同一个文件名——
    看图的人以为自己在看两份证据。
    """
    assert screenshot_name("plaza", "dark", "mobile") != screenshot_name(
        "plaza", "dark", "desktop")


# ───────────────────────── acceptance①：逐屏取证


def test_every_screen_on_disk_was_measured_on_mobile_in_both_themes() -> None:
    """**覆盖判据**：磁盘上有几屏，移动视口就要有几屏 × 两主题。

    卡面写的是「十三张屏」，实测 16——**按磁盘数，NEVER 按卡面那个数**。
    写死一个数的话，新增一屏永远不会被量到，而报告看起来是全绿的。
    """
    expected = {s.route for s in discover_screens(WEB) if s.url}
    got = {(r["route"], r["theme"]) for r in _mobile()}

    assert expected, "一屏都没扫到：扫描面塌了"
    missing = {(route, theme) for route in expected for theme in THEMES} - got
    assert missing == set(), f"这些屏没在 390px 下量过：{sorted(missing)}"


def test_no_screen_overflows_horizontally_on_a_390px_viewport() -> None:
    """**本卡的正题**：十六屏 × 两主题，横向溢出为零。

    `FIX-05` 修的 `.app-shell__body` 是所有屏共用的容器——
    这里若还剩下几条，说明溢出源不止那一处。
    """
    bad = [(r["route"], r["theme"], r["scroll_width"], r["viewport_width"])
           for r in _mobile() if r["horizontal_overflow"]]

    assert bad == [], f"这些屏在 390px 下横向溢出：{bad}"


def test_every_mobile_row_answered_two_hundred() -> None:
    bad = [(r["route"], r["theme"], r["http_status"])
           for r in _mobile() if r["http_status"] != 200]

    assert bad == [], f"这些屏不是 200：{bad}"


def test_every_mobile_row_has_a_screenshot_on_disk() -> None:
    """截图**真的存档了**——报告里写着文件名而磁盘上没有，等于没取证。"""
    missing = [r["screenshot"] for r in _mobile()
               if not (SHOTS / r["screenshot"]).exists()]

    assert missing == [], f"报告里有名字、磁盘上没有：{missing}"


# ───────────────────────── acceptance③：查出来的每一条都落实


def test_console_errors_match_a_baseline_that_names_its_ticket() -> None:
    """**判等值，不判零**。

    判零会把 `DEMO-REFS-NO-STORAGE-FACE` 登记的正确行为算成本卡失败；
    顺手放行又会让下一条新增的报错混进来。所以逐屏对一份点名了单号的基线——
    数字变了（修好了、或又多了）都要有人回到这里确认。
    """
    for row in _report()["screens"]:
        allowed, why = CONSOLE_BASELINE.get(row["route"], (0, ""))
        assert row["console_error_count"] == allowed, (
            f"{row['route']} [{row['theme']}/{row['viewport']}] "
            f"控制台报错 {row['console_error_count']}，基线 {allowed}"
            f"{'（' + why + '）' if why else ''}——"
            f"少了说明修好了、多了说明新增了，两种都来这里确认")


def test_every_baselined_route_still_points_at_a_live_ticket() -> None:
    """基线里每一条都要挂一张**盘上真在**的单，且那张单没被关掉。

    单子关掉了而基线还留着 3，就是拿一张过期的单为一处新缺陷背书。
    """
    for route, (allowed, why) in CONSOLE_BASELINE.items():
        assert allowed > 0, route
        ticket = REPO / why.split("：")[0]
        assert ticket.exists(), f"{route} 挂的单不在盘上：{ticket}"
        head = "\n".join(ticket.read_text(encoding="utf-8").splitlines()[:12])
        assert "**状态** open" in head, (
            f"{ticket.name} 已经关了，但基线还允许 {allowed} 条报错")


def test_the_gate_screen_probe_points_at_a_job_that_has_a_verdict() -> None:
    """判定屏的样例 id 指向**有判定的** job。

    改前填的是 `m1004-j`——那个 job 没有 verdict 快照，于是这一屏恒发一次 404，
    拍回来的是一张空态截图。`fe_smoke` 自己的开篇写着「现编一个 id 更糟：
    那一屏会恒 404，而 404 会被读成『这屏坏了』，真相是探针给错了地址」。
    """
    from harness.fe_smoke import SAMPLE_IDS

    assert SAMPLE_IDS["/gate/[id]"] == "job-gate1-live-qwen"
    rows = [r for r in _report()["screens"] if r["route"] == "/gate/[id]"]
    assert rows, "判定屏没取证"
    for row in rows:
        assert row["console_error_count"] == 0, row["console_errors"]


# ───────────────────────── 桌面不倒 + 阴性对照


def test_the_desktop_half_did_not_regress() -> None:
    desktop = [r for r in _report()["screens"] if r["viewport"] == "desktop"]

    assert len(desktop) == len(_mobile()), "两个视口的行数对不上"
    assert [r for r in desktop if r["horizontal_overflow"]] == []


def test_the_overflow_counter_still_bites() -> None:
    """**阴性对照**：喂一行真溢出的观测 → 必须被算进去并让报告不 ok。

    没有这条，上面那个「零溢出」与「计数器塌了」长得一模一样。
    """
    row = {
        "screen": "x", "route": "/x", "url": "u", "theme": "dark",
        "viewport": "mobile", "http_status": 200, "console_error_count": 0,
        "console_errors": [], "page_height": 800, "horizontal_overflow": True,
        "scroll_width": 438, "viewport_width": 390, "screenshot": "x.png",
    }
    report = build_report([row], stack_down=[])

    assert report["counts"]["overflow"] == 1
    assert report["counts"]["mobile_overflow"] == 1
    assert report["ok"] is False
