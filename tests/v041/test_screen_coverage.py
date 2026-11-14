"""GAUGE-13：蓝本 P 编号 ↔ 实仓路由**双向**对账，缺屏判红。

## 为什么要双向

单向只能发现一半：只查「蓝本有而实仓没有」，实仓多出来的屏没人管、蓝本慢慢过期；
只查「实仓有而蓝本没有」，**缺屏永远发现不了**——而本批开工时就缺六屏
（`P3` combo · `P4` 主题列表 · `P5` 主题详情 · `P6` 发起分析 ·
`P10` 干预页 · `P11` 受众分叉），用户当时**从广场走不到报告**。

## 这份验收的四条

| # | 判什么 |
|---|---|
| ① | 三类报告各自成一类（缺屏 / 两边都没登记 / 端点对不上）——修法完全不同 |
| ② | **开工时那六屏的名单已清空**，且判据钉着它 NEVER 回潮 |
| ③ | 机器守着不漂移：蓝本新增一条而实仓没有屏 → 当场红（阴性对照） |
| ④ | 接进全局门（`F-11`：不在门里的尺子等于没有） |
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "tools" / "check_screen_coverage.py"
TABLE = REPO / "docs" / "屏对照表-v041.md"

sys.path.insert(0, str(REPO / "tools"))

from check_screen_coverage import (
    ALIASES,
    APP,
    BLUEPRINT,
    DELIBERATELY_ABSENT,
    KNOWN_ENDPOINT_GAPS,
    V2_SCREENS,
    audit,
    blueprint_rows,
    normalise,
    repo_routes,
)

# 开工时缺的六屏（工单 §4 D 组逐条点名）。**这份名单是本卡的由来**。
THE_SIX = {
    "/combo/new": "P3 combo 入口",
    "/projects/[id]/topics": "P4 主题列表",
    "/topics/[id]": "P5 主题详情",
    "/projects/[id]/analysis/new": "P6 发起分析",
    "/deliverables/[id]/edit": "P10 干预页",
    "/projects/[id]/proposal/new": "P11 受众分叉",
}


def _report() -> dict[str, list[dict[str, str]]]:
    return audit(BLUEPRINT.read_text(encoding="utf-8"), repo_routes(APP))


# ───────────────────────── 一、缺屏为 0（本卡的出口判据）


def test_no_blueprint_screen_is_missing() -> None:
    """卡面 acceptance②：`CHAIN-03~05` 做掉后名单清空。"""
    missing = _report()["missing"]

    assert missing == [], f"这些蓝本屏实仓没有：{missing}"


def test_the_six_screens_are_all_there_now() -> None:
    """六屏**逐条点名**验，而不是只看总数为 0。

    只看总数的话，将来有人删掉一屏又加一屏，总数不变而那六屏里少了一个。
    """
    have = {normalise(r) for r in repo_routes(APP)}

    for blueprint_path, label in THE_SIX.items():
        route = normalise(ALIASES.get(blueprint_path, blueprint_path))
        assert route in have, f"{label} 又没了：{route}"


def test_no_endpoint_disagreement_outside_the_registered_list() -> None:
    gaps = _report()["endpoint_gap"]

    assert gaps == [], f"这些屏与蓝本对端点有分歧：{gaps}"


# ───────────────────────── 二、三类各自成一类


def test_the_three_kinds_are_reported_separately() -> None:
    """缺屏 → 去建屏；两边都没登记 → 去补文档；端点对不上 → 去核端点。

    合成一类的话，读的人不知道该做哪件事。
    """
    report = _report()

    assert set(report) == {"missing", "extra", "endpoint_gap"}


def test_every_exemption_carries_its_reason() -> None:
    """三份名单（别名 / 有意不做 / 已登记的端点缺口）**逐条带理由**。

    没有理由的豁免与「忘了做」长得一模一样。
    """
    for path, reason in DELIBERATELY_ABSENT.items():
        assert len(reason) > 10, f"{path} 的「有意不做」没写理由"
    for key, reason in KNOWN_ENDPOINT_GAPS.items():
        assert len(reason) > 10, f"{key} 的端点缺口没写理由"
    for route, why in V2_SCREENS.items():
        assert why, f"{route} 没写它在 v2 总表的哪一条"


def test_the_aliases_are_explicit_not_fuzzy() -> None:
    """别名是**显式映射**。模糊匹配会在某天把两个不同的屏认成同一个，

    而那时缺屏会静静地消失在报告里。
    """
    source = CHECKER.read_text(encoding="utf-8")

    assert "ALIASES" in source
    for tell in ("startswith(", "difflib", "SequenceMatcher", "fuzzy"):
        assert tell not in source, f"对账用上了模糊匹配：{tell}"


# ───────────────────────── 三、阴性对照：尺子认得出新缺口


def test_a_new_blueprint_row_without_a_screen_is_reported() -> None:
    """卡面 acceptance③：**新增蓝本条目而没有屏则判红，NEVER 靠人记。**"""
    text = BLUEPRINT.read_text(encoding="utf-8")
    injected = text + (
        "\n| /nowhere/[id] | P99 还没建的屏 | GET /nowhere/{id} |\n")

    report = audit(injected, repo_routes(APP))

    assert any(row["blueprint"] == "/nowhere/[id]" for row in report["missing"]), (
        "蓝本多了一条没有屏的，尺子没报出来"
    )


def test_removing_a_screen_is_reported() -> None:
    """反向：屏没了也要红。**这是 acceptance② 的「NEVER 回潮」那一半。**"""
    routes = [r for r in repo_routes(APP) if r != "/combo"]

    report = audit(BLUEPRINT.read_text(encoding="utf-8"), routes)

    assert any(row["expected_route"] == "/combo" for row in report["missing"]), (
        "把 combo 入口删掉，尺子居然没红"
    )


def test_a_screen_nobody_registered_is_reported() -> None:
    """两边都没登记的屏要说出来——**没人登记的屏没人维护**。"""
    routes = [*repo_routes(APP), "/brand-new-screen"]

    report = audit(BLUEPRINT.read_text(encoding="utf-8"), routes)

    assert any(row["route"] == "/brand-new-screen" for row in report["extra"])


# ───────────────────────── 四、对照表与脚本说的是同一件事


def test_the_table_agrees_with_the_checker() -> None:
    """`docs/屏对照表-v041.md` 是给人看的那一份，**它 NEVER 与脚本说两样话**。"""
    table = TABLE.read_text(encoding="utf-8")
    report = _report()

    assert f"缺屏 {len(report['missing'])}" in table, "表里的缺屏数与脚本对不上"
    for label in THE_SIX.values():
        assert label.split()[0] in table, f"表里没有 {label}"


def test_the_checker_exits_zero_today() -> None:
    done = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout
    assert "缺屏 0" in done.stdout


def test_the_checker_reports_json_for_machines() -> None:
    done = subprocess.run(
        [sys.executable, str(CHECKER), "--json"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert set(json.loads(done.stdout)) == {"missing", "extra", "endpoint_gap"}


# ───────────────────────── 五、接进全局门（F-11 的教训）


def test_this_ruler_runs_inside_pytest_q() -> None:
    """**不在门里的尺子等于没有**（`F-11`：两把尺子一红一绿，红的那把没人跑）。"""
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-k", "no_blueprint_screen_is_missing"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout[-400:]
    assert "test_no_blueprint_screen_is_missing" in done.stdout


def test_the_blueprint_table_is_still_parseable() -> None:
    """蓝本那张表哪天换了格式，解析会静静地回空表——**而空表下缺屏恒为 0**。

    所以钉住「解析得到 14 条」：格式变了就来这里确认解析器跟上了。
    """
    rows = blueprint_rows(BLUEPRINT.read_text(encoding="utf-8"))

    assert len(rows) == 14, f"蓝本表解析到 {len(rows)} 条，不是 P1~P14"
    assert all(row.label.startswith("P") for row in rows)
