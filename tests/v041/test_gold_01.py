"""GOLD-01：金标集采集脚手架（为 θ_rel / δ / hotness 标定备料，不含调参）。

θ_rel（0.6）/ δ（0.965）是 `CLAUDE.md#S4` 的 Open Question——调参是 owner 决策。
采集脚本内置阈值就等于让金标带上当前阈值的偏见，再拿它去调那个阈值 = 拿答案验算答案。
本测的核心两条：**采得出可标注条目**、**采集侧一个阈值都没有**。
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import os
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.jobs.gate1 import build_offline_deps, run_gate1
from harness import gold_collect
from harness.gold_collect import collect_gold_entries, to_jsonl

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
JOB_ID = "gold01-run"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── acceptance ②：采集侧 NEVER 内置阈值 ────────────────────────────────

def _numeric_literals(source: str) -> list[float]:
    return [
        node.value for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant)
        and isinstance(node.value, float)
        and not isinstance(node.value, bool)
    ]


def _threshold_names(source: str) -> set[str]:
    tree = ast.parse(source)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {
        a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
        for a in n.names
    }
    return {n for n in names if n in {"THETA_REL", "theta", "delta", "DELTA"}}


def test_collector_holds_no_threshold_constant() -> None:
    source = inspect.getsource(gold_collect)
    assert _numeric_literals(source) == [], (
        f"采集模块里有浮点常量（疑似阈值）：{_numeric_literals(source)}"
    )
    assert _threshold_names(source) == set(), (
        f"采集模块引用了阈值名：{_threshold_names(source)}"
    )
    # 字符串常量面也查一遍（阈值写成字符串同样是阈值），但**排除 docstring**：
    # 文档里写明「0.6 / 0.965 是 Open Question，所以这里不放」是应该的，那不是违规。
    tree = ast.parse(source)
    docstrings = {
        ast.get_docstring(node, clean=False)   # clean=True 会归一化缩进，对不上原常量
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef))
    }
    code_strings = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    ]
    for banned in ("0.6", "0.965", "THETA_REL"):
        offenders = [s for s in code_strings if banned in s]
        assert offenders == [], f"采集代码里出现了 {banned}：{offenders}"


def test_the_threshold_check_is_not_vacuous() -> None:
    """反例：同款检查在 `flint/jobs/gate1.py` 上必须认得出那里确实引用了阈值。"""
    gate_source = (REPO / "flint" / "jobs" / "gate1.py").read_text(encoding="utf-8")
    assert "THETA_REL" in _threshold_names(gate_source)


def test_collector_makes_no_judgement_call() -> None:
    """只采不判：模块里没有比较运算（判定的最小形态）。"""
    tree = ast.parse(inspect.getsource(gold_collect))
    comparisons = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and any(isinstance(op, (ast.Lt, ast.LtE, ast.Gt, ast.GtE))
                for op in node.ops)
    ]
    assert comparisons == [], "采集模块里出现了大小比较——那是判定，不是采集"


def test_annotation_slots_are_left_empty() -> None:
    """标注槽是留白：`label` 恒 None、`note` 恒空串，脚本 NEVER 预填猜测。"""
    fields = gold_collect.GoldEntry.__dataclass_fields__
    assert "label" in fields and "note" in fields
    source = inspect.getsource(gold_collect)
    assert "label=None" in source and 'note=""' in source


# ── 以下走真库 ─────────────────────────────────────────────────────────

async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def _wipe() -> None:
    run(_sql([
        f"DELETE FROM job_events WHERE job_id LIKE '{JOB_ID}%'",
        f"DELETE FROM job_steps WHERE job_id LIKE '{JOB_ID}%'",
        f"DELETE FROM jobs WHERE job_id LIKE '{JOB_ID}%'",
        f"DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-{JOB_ID}%'",
    ]))


def _real_run() -> None:
    """离线确定性 Gate① 真跑（`build_offline_deps`，零网络）。"""
    deps = build_offline_deps(dsn=DSN, repo_root=REPO)
    run(run_gate1(JOB_ID, ["检索增强生成"], "zh-CN", deps))


@pytest.mark.compose
def test_collects_annotatable_entries_from_a_real_run() -> None:
    _wipe()
    _real_run()
    entries = run(collect_gold_entries(DSN, JOB_ID))

    assert entries, "一次真跑什么也没采出来"
    kinds = {e.kind for e in entries}
    assert kinds == {"evidence", "claim", "verdict"}, (
        f"三类条目没齐（采到 {sorted(kinds)}）"
    )
    for entry in entries:
        assert entry.job_id == JOB_ID, "条目没带来源 job_id"
        assert entry.source_snapshot_id.startswith(f"snap-{JOB_ID}-")
        assert entry.label is None, "标注槽被预填了"
        assert entry.note == ""
        assert entry.payload is not None


@pytest.mark.compose
def test_each_entry_carries_the_real_utc_timestamp_of_its_source() -> None:
    _wipe()
    _real_run()
    entries = run(collect_gold_entries(DSN, JOB_ID))

    async def _created_at() -> dict[str, str]:
        from datetime import UTC

        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT snapshot_id, created_at FROM snapshots "
                f"WHERE snapshot_id LIKE 'snap-{JOB_ID}-%'"
            )
        finally:
            await conn.close()
        return {
            r["snapshot_id"]: r["created_at"].astimezone(UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            for r in rows
        }

    truth = run(_created_at())
    for entry in entries:
        assert entry.source_ts == truth[entry.source_snapshot_id], (
            f"{entry.entry_id} 的时间戳不是数据自身的落库时刻"
        )
        assert entry.source_ts.endswith("Z") and len(entry.source_ts) == 20


@pytest.mark.compose
def test_export_is_byte_identical_across_two_runs() -> None:
    _wipe()
    _real_run()
    first = to_jsonl(run(collect_gold_entries(DSN, JOB_ID)))
    second = to_jsonl(run(collect_gold_entries(DSN, JOB_ID)))
    assert first.encode("utf-8") == second.encode("utf-8"), "两次导出不逐字节一致"
    assert first.strip(), "导出是空的"
    assert all(line for line in first.splitlines()), "导出里有空行"


@pytest.mark.compose
def test_entry_ids_are_content_derived_and_stable() -> None:
    _wipe()
    _real_run()
    entries = run(collect_gold_entries(DSN, JOB_ID))
    ids = [e.entry_id for e in entries]
    assert len(ids) == len(set(ids)), f"条目 id 撞号：{ids}"
    assert all(i.startswith("gold-") for i in ids)
    again = [e.entry_id for e in run(collect_gold_entries(DSN, JOB_ID))]
    assert ids == again, "同一输入两次采集的 id 不一致"


@pytest.mark.compose
def test_missing_snapshots_are_skipped_not_faked() -> None:
    """没跑到那一步就没有那类条目——NEVER 造一条空的顶上。"""
    _wipe()
    entries = run(collect_gold_entries(DSN, "gold01-never-ran"))
    assert entries == []
