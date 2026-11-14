"""GAUGE-02 验收：acceptance ↔ 尺子清点器的正确性与落盘副本的时效。

acceptance（tasks-v041-b2.json#GAUGE-02）：
  ① 对 tasks-v04.json 全部 104 张卡的每条 acceptance 产出四元组
     （卡号 / acceptance 原文 / 对应尺子 / 在不在全局门）；
  ② 分三类落 `assets/gauge_map.json`，第三类逐条列进 `docs/尺子清点-v041.md`；
  ③ 归属机械推出（verify_cmd + outputs），推不出的一律进第三类；
  ④ 工具自证：三条已知答案的 acceptance 当阴阳对照。

## 自证为什么必须包含「GAUGE-01 之前」那一刻

`PRIN-01` acceptance② 的尺子是 `tools/check_principles_doc.py`。**今天**它在门内
（`tests/v041/test_doc_gates.py` 把它起起来了），但 F-11 发生的那一刻它不在——
而清点器的价值全在于能不能把「不在门内」这一格如实报出来。所以阴性对照不是构造一张
假卡，而是**构造那一刻的仓库索引**（`tool_invokers={}`）：同一张真卡、同一条真 acceptance，
换掉唯一变量，分类必须从 `in_gate` 翻成 `gauged_outside_gate`。

翻不过去 = 这把清点器只会说"都挺好"，那它就是它自己要防的那种东西。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.gauge_map import (
    CLASS_IN_GATE,
    CLASS_NO_GAUGE,
    CLASS_OUTSIDE_GATE,
    MAP_JSON,
    REPO_ROOT,
    REPORT_MD,
    TASKS,
    Repo,
    build_map,
    classify_card,
    identifiers_of,
    parse_gauges,
)

EXPECTED_CARDS = 104


@pytest.fixture(scope="module")
def repo() -> Repo:
    return Repo(REPO_ROOT)


@pytest.fixture(scope="module")
def data(repo: Repo) -> dict[str, Any]:
    return build_map(TASKS, repo)


@pytest.fixture(scope="module")
def tasks() -> list[dict[str, Any]]:
    return json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]


def card(tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any]:
    return next(t for t in tasks if t["id"] == task_id)


# ---------------------------------------------------------------- ① 四元组全覆盖


def test_every_acceptance_of_every_card_gets_a_quadruple(
    data: dict[str, Any], tasks: list[dict[str, Any]]
) -> None:
    """① 104 张卡、每条 acceptance 一个四元组，一条不漏、一条不多。"""
    assert data["cards"] == EXPECTED_CARDS
    expected = sum(len(t["acceptance"]) for t in tasks)
    assert data["acceptance_total"] == expected
    assert len(data["entries"]) == expected

    seen = {(e["task_id"], e["acceptance_index"]) for e in data["entries"]}
    assert len(seen) == expected, "有 (卡号, 序号) 重复 —— 说明清点漏配或多配"
    for task in tasks:
        for index, text in enumerate(task["acceptance"], start=1):
            hit = next(
                e for e in data["entries"]
                if e["task_id"] == task["id"] and e["acceptance_index"] == index
            )
            assert hit["acceptance"] == text, "acceptance 原文必须逐字，NEVER 摘要"
            assert isinstance(hit["gauges"], list)
            assert isinstance(hit["in_gate"], bool)


def test_three_classes_partition_the_entries(data: dict[str, Any]) -> None:
    """② 三类是一个划分：每条恰好属于一类，计数与条目对得上。"""
    classes = {CLASS_IN_GATE, CLASS_OUTSIDE_GATE, CLASS_NO_GAUGE}
    assert {e["class"] for e in data["entries"]} <= classes
    for name in classes:
        assert data["counts"][name] == sum(1 for e in data["entries"] if e["class"] == name)
    assert sum(data["counts"].values()) == data["acceptance_total"]


# ---------------------------------------------------------------- ④ 三条已知答案


def test_control_prin01_hash_acceptance_is_gauged_by_the_doc_checker(
    tasks: list[dict[str, Any]], repo: Repo
) -> None:
    """阳性对照 A（F-11 的卡）：尺子必须被认成 check_principles_doc.py。"""
    entries = classify_card(card(tasks, "PRIN-01"), repo)
    hash_entry = entries[1]                        # acceptance②「与工单 §3 正文逐字一致」
    assert "哈希" in hash_entry["acceptance"]
    tools_used = {t for g in hash_entry["gauges"] for t in g["files"]}
    assert tools_used == {"tools/check_principles_doc.py"}


def test_control_prin01_flips_to_outside_gate_at_the_moment_f11_happened(
    tasks: list[dict[str, Any]]
) -> None:
    """阴性对照（最要紧的一条）：把仓库索引换回「没有任何测试起这把工具」那一刻。

    唯一变量是 tool_invokers；同一张卡、同一条 acceptance 必须从「在门内」翻成
    「有尺子但不在门内」。翻不过去说明这把清点器根本量不出 F-11。
    """
    before = Repo(REPO_ROOT, tool_invokers={})
    after = Repo(REPO_ROOT)
    prin01 = card(tasks, "PRIN-01")

    assert classify_card(prin01, before)[1]["class"] == CLASS_OUTSIDE_GATE
    assert classify_card(prin01, after)[1]["class"] == CLASS_IN_GATE, (
        "GAUGE-01 已把六把文档尺接进 pytest -q，这里应报在门内"
    )


def test_control_graph06_frontend_acceptance_is_outside_the_gate(
    tasks: list[dict[str, Any]], repo: Repo
) -> None:
    """阳性对照 B（F-05 的卡）：vitest 那把尺子解析得到，但不在三条门命令里。

    GRAPH-06 的 verify_cmd 是 `cd web && npm test -- --run components/graph-roles &&
    pytest ...`，两把尺子都在。全卡因此落在门内——**但 vitest 那把本身 in_gate=False**，
    这一格必须如实报，否则「前端测试要单独跑」这件事在清点表里就消失了。
    """
    graph06 = card(tasks, "GRAPH-06")
    gauges = parse_gauges(graph06["verify_cmd"], repo)
    kinds = {g["kind"]: g for g in gauges}
    assert set(kinds) == {"vitest", "pytest"}
    assert kinds["vitest"]["resolved"] is True, "vitest 过滤器必须真解析到测试文件"
    assert kinds["vitest"]["in_gate"] is False
    assert kinds["pytest"]["in_gate"] is True
    assert classify_card(graph06, repo)[0]["class"] == CLASS_IN_GATE


def test_control_a_plain_card_lands_in_gate(tasks: list[dict[str, Any]], repo: Repo) -> None:
    """阳性对照 C（一条正常卡）：纯 pytest 卡，全部 acceptance 在门内。"""
    plain = card(tasks, "SCHEMA-00")
    assert plain["verify_cmd"].strip().startswith(("pytest", "python tools/check_frozen_additive"))
    for entry in classify_card(plain, repo):
        assert entry["class"] in {CLASS_IN_GATE, CLASS_OUTSIDE_GATE}


def test_control_unresolvable_gauge_lands_in_class_three() -> None:
    """③ 的阴性对照：尺子指向不存在的东西 → 第三类，NEVER 靠卡面声明蒙混。"""
    repo = Repo(REPO_ROOT)
    ghost = {
        "id": "GHOST-01",
        "verify_cmd": "pytest tests/v04/does-not-exist/test_nothing.py -q",
        "acceptance": ["随便一条"],
    }
    entry = classify_card(ghost, repo)[0]
    assert entry["class"] == CLASS_NO_GAUGE
    assert entry["in_gate"] is False
    assert entry["reason"]

    empty = {"id": "GHOST-02", "verify_cmd": "", "acceptance": ["随便一条"]}
    assert classify_card(empty, repo)[0]["class"] == CLASS_NO_GAUGE

    ghost_tool = {
        "id": "GHOST-03",
        "verify_cmd": "python tools/no_such_tool.py x",
        "acceptance": ["随便一条"],
    }
    assert classify_card(ghost_tool, repo)[0]["class"] == CLASS_NO_GAUGE

    ghost_vitest = {
        "id": "GHOST-04",
        "verify_cmd": "cd web && npm test -- --run components/no-such-component",
        "acceptance": ["随便一条"],
    }
    assert classify_card(ghost_vitest, repo)[0]["class"] == CLASS_NO_GAUGE


# ---------------------------------------------------------------- 弱关联那把独立的尺


def test_weak_link_is_orthogonal_and_not_vacuous(data: dict[str, Any]) -> None:
    """弱关联不参与三分类，且它真的能判真也能判假。"""
    assert identifiers_of("与工单 §3 正文逐字一致（哈希比对）") == []
    assert "GroundingOnTranslationError" in identifiers_of(
        "对派生槽调用接地入口 → 抛 `GroundingOnTranslationError`"
    )
    # 停用词与 <3 字符的 token 丢掉：留着的话任何文件都能命中，weak_link 就恒为 False
    assert identifiers_of("NEVER 用 id 标记") == []
    assert identifiers_of("web src 全量 run") == [], "路径与命令名不是 acceptance 的标识符"

    for entry in data["entries"]:
        if entry["class"] == CLASS_NO_GAUGE:
            assert entry["weak_link"] is False, "第三类不重复标弱关联"
        if entry["weak_link"]:
            assert entry["identifiers"] and not entry["identifier_hits"]


# ---------------------------------------------------------------- ② 落盘副本


def test_disk_copies_are_current() -> None:
    """落盘的 json 与报告必须是当前实况——过期即红（`--check` 就是这条的命令行形态）。"""
    from tools.gauge_map import _report, main

    fresh = build_map()
    assert MAP_JSON.exists(), "assets/gauge_map.json 未生成"
    assert REPORT_MD.exists(), "docs/尺子清点-v041.md 未生成"
    on_disk = json.loads(MAP_JSON.read_text(encoding="utf-8"))
    assert on_disk["entries"] == fresh["entries"], "落盘 json 过期：跑 python tools/gauge_map.py"
    assert REPORT_MD.read_text(encoding="utf-8") == _report(fresh), "报告过期"
    assert main(["gauge_map.py", "--check"]) == 0


def test_report_lists_class_three_line_by_line() -> None:
    """② 后半句：第三类逐条进报告——那是这张卡的产品。

    第三类为空时，报告 MUST 明说是阴性结论并指向证明它会落的构造用例，
    NEVER 只留一张空表让人以为"没查"。
    """
    text = REPORT_MD.read_text(encoding="utf-8")
    data = json.loads(MAP_JSON.read_text(encoding="utf-8"))
    no_gauge = [e for e in data["entries"] if e["class"] == CLASS_NO_GAUGE]
    assert "## 第三类逐条：查不到尺子" in text
    if no_gauge:
        for entry in no_gauge:
            assert f"`{entry['task_id']}`" in text
            assert entry["acceptance"][:20] in text
    else:
        assert "零条" in text and "阴性结论" in text
    assert "GAUGE-03" in text, "看不见的那一类（F-05）必须如实登记并指向承接方"
    assert Path(REPO_ROOT / "docs" / "尺子清点-v041.md").read_bytes()[:3] != b"\xef\xbb\xbf"
