"""HOTSPOT-06 验收：分析时效 stale 适配器（复用 Revalidator 通道，不新写比对）。

acceptance（tasks-v04.json#HOTSPOT-06）：
**适配器 import 自 contracts 通道（H1 断言）；无新比对实现**。

## 为什么这张卡的全部分量在「不新写」

系统里已经有一套判「东西变没变」的机制（`LedgerStore.diff` → `compute_diff` 三分类，
`removed→blocking / changed→advisory / disputed→advisory`）。再写一套的后果不是重复劳动，
而是**同一份分析在两个地方被判成不同的新旧**：收藏页说它陈旧、分析页说它是最新的，
用户不知道该信哪个。所以本卡的适配器只做三件事——取既有 diff、按既有严重度表映射、
只看这份分析真正引用过的事实（零污染，与既有 block 标记同一条规则）。
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from flint.analysis.stale_adapter import analysis_stale, stale_from_fact_changes
from flint.domain.models import FactDiff

REPO_ROOT = Path(__file__).resolve().parents[3]
ADAPTER_SRC = REPO_ROOT / "flint" / "analysis" / "stale_adapter.py"

CITED = ("f-1", "f-2")


# ───────────────────────── H1：复用断言（本卡 acceptance 唯一条）


def test_adapter_imports_the_contracts_channel() -> None:
    """比对与严重度都 import 自既有通道 `flint.ledger.diff`，NEVER 本地另起一套。"""
    tree = ast.parse(ADAPTER_SRC.read_text(encoding="utf-8"))
    sources = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "flint.ledger.diff" in sources
    assert "flint.domain.models" in sources  # FactDiff / ReviewSeverity 取自契约类型


def test_adapter_defines_no_diff_of_its_own() -> None:
    """H1 的「不新写」机器断言：本文件里没有任何 diff 实现。"""
    tree = ast.parse(ADAPTER_SRC.read_text(encoding="utf-8"))
    defined = [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    assert [n for n in defined if "diff" in n.lower()] == []


def test_repo_wide_diff_implementations_unchanged() -> None:
    """工单 §6-H1 的原句：`grep -R "def .*diff" flint/` 无新比对实现。

    只断自己那一个文件不够——「不新写」是仓库级承诺，本卡若在别处偷偷加了一个
    比对函数，单文件断言照样绿。故这里把仓库扫一遍，与既有清单逐项比对。
    """
    out = subprocess.run(
        [sys.executable, "-c", (
            "import pathlib,re,sys;"
            "hits=[f'{p}:{m}' for p in pathlib.Path('flint').rglob('*.py')"
            " for m in re.findall(r'def\\s+\\w*diff\\w*', p.read_text(encoding='utf-8'))];"
            "print('\\n'.join(sorted(hits)))"
        )],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    found = {line.split(":", 1)[0] for line in out.stdout.splitlines() if line}
    assert "flint\\analysis\\stale_adapter.py" not in found
    assert "flint/analysis/stale_adapter.py" not in found
    # 既有比对实现仍在原处（本卡零改动）
    assert any("ledger" in f and "diff" in f for f in found)


def test_severity_table_is_the_existing_one() -> None:
    """严重度不是本模块自己写死的一张表：与 `flint.ledger.diff` 的映射逐项相同。

    抄一份表最坏的形态不是抄错，而是**日后只改了一处**：审11 说严重度只升不降，
    两张表分叉时，同一次事实移除会在一个界面上是 blocking、另一个上是 advisory。
    """
    from flint.ledger.diff import _MARKS

    expected = {kind: (reason, severity) for kind, reason, severity in _MARKS}
    for kind, (reason, severity) in expected.items():
        diff = FactDiff(**{
            "changed": [], "removed": [], "disputed": [], kind: ["f-1"],
        })
        verdict = stale_from_fact_changes(diff, cited_fact_ids=CITED)
        assert verdict.stale is True
        assert verdict.reason == reason
        assert verdict.severity == severity


# ───────────────────────── 语义：只看这份分析引用过的事实


def test_unrelated_fact_change_leaves_the_analysis_fresh() -> None:
    """别的事实变了不算这份分析陈旧（零污染，与既有 block 标记同一条规则）。

    否则账本一动，全站分析统统标陈旧，「陈旧」这个标记就不再有信息量。
    """
    diff = FactDiff(changed=["f-99"], removed=[], disputed=[])
    verdict = stale_from_fact_changes(diff, cited_fact_ids=CITED)

    assert verdict.stale is False
    assert verdict.severity is None
    assert verdict.fact_ids == ()


def test_removed_beats_changed_when_both_hit() -> None:
    """一份分析同时命中多类时取最强——审11：严重度只升不降。"""
    diff = FactDiff(changed=["f-1"], removed=["f-2"], disputed=[])
    verdict = stale_from_fact_changes(diff, cited_fact_ids=CITED)

    assert verdict.severity == "blocking"
    assert verdict.reason == "fact_removed"
    assert verdict.fact_ids == ("f-2",)


def test_empty_diff_is_not_stale() -> None:
    verdict = stale_from_fact_changes(
        FactDiff(changed=[], removed=[], disputed=[]), cited_fact_ids=CITED,
    )
    assert verdict.stale is False


# ───────────────────────── 与账本版本的接线


def test_same_version_never_calls_diff() -> None:
    """分析所依据的版本就是当前版本 → 不查、不判，直接不陈旧。

    白跑一次 diff 不只是浪费：它给了「同版本也可能判出陈旧」的可能性，
    而那只会是比对实现的 bug 被放行的入口。
    """
    calls: list[tuple[str, int, int]] = []

    def spy_diff(project_id: str, v_from: int, v_to: int) -> FactDiff:
        calls.append((project_id, v_from, v_to))
        return FactDiff(changed=["f-1"], removed=[], disputed=[])

    verdict = analysis_stale(
        spy_diff, project_id="p-1", analysed_at_version=7, current_version=7,
        cited_fact_ids=CITED,
    )

    assert calls == []
    assert verdict.stale is False


def test_advanced_version_asks_the_injected_channel() -> None:
    """版本前进 → 经注入的 `LedgerStore.diff` 通道查，参数逐字为 (project, 旧版, 新版)。"""
    calls: list[tuple[str, int, int]] = []

    def spy_diff(project_id: str, v_from: int, v_to: int) -> FactDiff:
        calls.append((project_id, v_from, v_to))
        return FactDiff(changed=["f-1"], removed=[], disputed=[])

    verdict = analysis_stale(
        spy_diff, project_id="p-1", analysed_at_version=7, current_version=9,
        cited_fact_ids=CITED,
    )

    assert calls == [("p-1", 7, 9)]
    assert verdict.stale is True
    assert verdict.severity == "advisory"


def test_version_going_backwards_is_rejected() -> None:
    """账本版本只前进：收到倒退的版本对就是接线错了，报错而不是当成不陈旧。"""
    def unused_diff(project_id: str, v_from: int, v_to: int) -> FactDiff:
        raise AssertionError("NEVER 该被调到")

    with pytest.raises(ValueError):
        analysis_stale(
            unused_diff, project_id="p-1", analysed_at_version=9, current_version=7,
            cited_fact_ids=CITED,
        )
