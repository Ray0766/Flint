"""GAUGE-09 · 第 2 批 89 张卡的 acceptance ↔ 尺子专项清点。

## 用**同一把**尺子量两批，不是复制一份工具

复制出来的第二份从复制那一刻起就开始各走各的，而这张卡的全部价值在于
**两批的数能比**。所以 `tools/gauge_map.py` 加了 `--batch`，
两批共用同一套归属规则（只认 `verify_cmd` 与 `outputs`、目标必须在磁盘上真解析得到、
推不出的一律进第三类）。

## 实测

```
89 张卡 / 363 条 acceptance
  在门内            304
  有尺子但不在门内   55   ← 全部是 vitest（前端测试不在全局门那三条命令里）
  查不到尺子          4   ← 全部来自 NET-03
  弱关联             44
```

## 那 4 条「查不到尺子」不是缺口

**全部来自 `NET-03`**——那张卡按 `DEC-033①` 记了 `skipped_by_owner`
（真实源检索 owner 2026-07-31 payoff 已执行并录制），
它的测试文件**从来没写过**，所以 `verify_cmd` 里的尺子在磁盘上解析不出来。

这是清点器**如实报出的实况**，不是它漏了什么。
卡面 acceptance② 要的正是这个：「或逐条列名并说明为什么守不住——
**NEVER 用『已覆盖』一句话带过**」。
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

from tools.gauge_map import BATCHES, build_map

REPO = Path(__file__).resolve().parents[2]
MAP_JSON = REPO / "assets" / "gauge_map_b2.json"
REPORT_MD = REPO / "docs" / "尺子清点-v041-b2.md"
TASKS_B2 = REPO / "docs" / "steward" / "tasks-v041-b2.json"


def _data() -> dict[str, object]:
    return json.loads(MAP_JSON.read_text(encoding="utf-8"))


# ───────────────────────── acceptance①：照同一套办法，逐条回答


def test_the_same_tool_measures_both_batches() -> None:
    """**同一把尺子**量两批——NEVER 复制一份工具。

    复制出来的第二份从复制那一刻起就各走各的，而这张卡的价值在于两批的数能比。
    """
    assert set(BATCHES) == {"v04", "b2"}
    assert BATCHES["b2"]["tasks"] == TASKS_B2
    # 两批的输出各自落盘，NEVER 互相覆盖。
    assert BATCHES["v04"]["json"] != BATCHES["b2"]["json"]
    assert BATCHES["v04"]["md"] != BATCHES["b2"]["md"]


def test_every_card_and_every_acceptance_is_accounted_for() -> None:
    """89 张卡、每一条 acceptance 都有一行——**一条都不许漏**。

    漏掉的那条在报告里长得像「不存在」，而它可能正是没人守的那条。
    """
    tasks = json.loads(TASKS_B2.read_text(encoding="utf-8"))["tasks"]
    expected = sum(len(t.get("acceptance", [])) for t in tasks)
    data = _data()

    assert data["cards"] == len(tasks) == 89
    assert data["acceptance_total"] == expected
    assert len(data["entries"]) == expected

    by_card = Counter(e["task_id"] for e in data["entries"])
    for task in tasks:
        assert by_card[task["id"]] == len(task.get("acceptance", [])), task["id"]


def test_every_entry_points_at_a_named_gauge_or_says_why_not() -> None:
    """**产品是那份清单**：每条要么指到具体的测试函数名/工具名，要么写明为什么守不住。

    卡面 acceptance③ 点名了这条。
    """
    for entry in _data()["entries"]:
        if entry["class"] == "no_gauge":
            assert entry["reason"], f"{entry['task_id']} 没写为什么守不住"
            continue
        assert entry["gauges"], f"{entry['task_id']} 归了类却没有尺子"
        for gauge in entry["gauges"]:
            # 尺子要指到**具体的东西**：文件路径（pytest/vitest）或工具命令。
            assert gauge["kind"] in {"pytest", "vitest", "tool", "node"}, gauge
            assert gauge.get("files") or gauge.get("command"), gauge


def test_a_named_gauge_actually_exists_on_disk() -> None:
    """指到的文件**必须在磁盘上**——F-08 的形态是「过滤器谁都匹配不上却报绿」。"""
    missing: list[str] = []
    for entry in _data()["entries"]:
        for gauge in entry["gauges"]:
            for rel in gauge.get("files", []):
                if not (REPO / rel).exists():
                    missing.append(f"{entry['task_id']} → {rel}")

    assert missing == [], f"这些尺子文件不在盘上：{missing[:6]}"


# ───────────────────────── acceptance②：查不到尺子的逐条列名


def test_the_no_gauge_entries_are_exactly_the_ones_we_can_explain() -> None:
    """**判等值**：查不到尺子的 4 条全部来自 `NET-03`，且说得出为什么。

    `NET-03` 按 `DEC-033①` 记了 `skipped_by_owner`，它的测试文件**从没写过**，
    所以 `verify_cmd` 里的尺子在磁盘上解析不出来——
    这是清点器**如实报出的实况**，不是它漏了什么。

    多一条要有人来确认（那可能是真缺口），少一条说明 `NET-03` 被补了测试。
    """
    no_gauge = [e for e in _data()["entries"] if e["class"] == "no_gauge"]

    assert {e["task_id"] for e in no_gauge} == {"NET-03"}, (
        f"查不到尺子的不止 NET-03：{sorted({e['task_id'] for e in no_gauge})}——"
        f"多出来的那些是真缺口，逐条去看"
    )
    assert len(no_gauge) == 4, f"NET-03 有 {len(no_gauge)} 条，卡面 acceptance 是 4 条"
    for entry in no_gauge:
        assert "解析" in entry["reason"] or "尺子" in entry["reason"]


def test_the_report_names_them_instead_of_saying_covered() -> None:
    """清单里要**逐条列名**，NEVER 用「已覆盖」一句话带过（卡面原话）。"""
    text = REPORT_MD.read_text(encoding="utf-8")

    assert "NET-03" in text, "报告里没点名那 4 条"
    assert "已覆盖" not in text


# ───────────────────────── 门内外的分布：说清楚，不粉饰


def test_the_out_of_gate_entries_are_all_vitest() -> None:
    """有尺子但不在门内的 55 条**全部是 vitest**。

    全局门是 `ruff` / `mypy` / `pytest -q` 三条命令（`worker.md` §5 逐字），
    前端 `npm test` 要单独跑。**这不是贬低前端测试**——
    是陈述一个事实：合并时跑的那三条命令碰不到它们，忘了单独跑就没人会知道。
    """
    data = _data()
    outside = [e for e in data["entries"] if e["class"] == "gauged_outside_gate"]
    kinds = {g["kind"] for e in outside for g in e["gauges"]}

    assert data["counts"]["gauged_outside_gate"] == len(outside)
    assert kinds == {"vitest"}, f"门外还有别的种类：{kinds}"


def test_the_counts_add_up() -> None:
    """三类之和 == acceptance 总数。**分类不许有第四种落法**。"""
    data = _data()
    counts = data["counts"]

    assert sum(counts.values()) == data["acceptance_total"]
    assert set(counts) == {"in_gate", "gauged_outside_gate", "no_gauge"}


def test_the_weak_link_table_is_separate_from_the_three_way_split() -> None:
    """弱关联是**另一把独立的尺**，NEVER 混进三分类。

    三分类回答「有没有尺子、在不在门里」，回答不了「那把尺子真的在量这条吗」。
    混成一锅，机械判定与启发式判定就分不开了。
    """
    data = _data()
    weak = [e for e in data["entries"] if e["weak_link"]]

    assert data["weak_link_total"] == len(weak)
    # 弱关联的条目**照样有自己的三分类**——它是正交信号。
    assert {e["class"] for e in weak} <= {
        "in_gate", "gauged_outside_gate", "no_gauge"}
    assert any(e["class"] == "in_gate" for e in weak), (
        "弱关联全落在门外？那它就不是正交信号了"
    )


# ───────────────────────── 落盘副本不许过期


def test_the_disk_copies_match_a_fresh_run() -> None:
    """落盘的两份与现算的逐字一致——**手改会被这条抓红**。"""
    fresh = build_map(TASKS_B2)

    assert _data() == fresh, "落盘 json 过期：跑 python tools/gauge_map.py --batch b2"


def test_the_check_mode_exits_zero_when_current() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO / "tools" / "gauge_map.py"), "--check",
         "--batch", "b2"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", check=False)

    assert done.returncode == 0, done.stdout + done.stderr


def test_the_v04_copies_were_not_overwritten_by_this_batch() -> None:
    """**阴性对照**：跑 `--batch b2` 不许把 v04 那两份盖掉。

    写路径若写死成模块级常量，第 2 批的结果会盖到 v04 的文件上，
    **而两份报告的标题都写着自己是对的**——本卡实测差点这么干。
    """
    v04 = json.loads((REPO / "assets" / "gauge_map.json").read_text(encoding="utf-8"))

    assert v04["generated_from"] == "tasks-v04.json"
    assert v04["cards"] != 89, "v04 那份被第 2 批盖掉了"
    b2_report = REPORT_MD.read_text(encoding="utf-8")
    assert "tasks-v041-b2.json" in b2_report
    v04_report = (REPO / "docs" / "尺子清点-v041.md").read_text(encoding="utf-8")
    assert "tasks-v04.json" in v04_report
