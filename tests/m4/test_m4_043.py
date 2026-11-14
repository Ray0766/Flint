"""M4-043 acceptance tests: pre-exit reconciliation.

Acceptance (tasks.json M4-043):
  - §7 M4 row evidence bound (DAG 0 exceptions / registry 100% /
    oneshot rate vs Z)
  - M3 carried-condition redemption status honestly summarized
    (including the blocked case)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.dag import run_dag_eval
from eval.registry import run_registry_eval
from fixtures._generate_trial_specs import generate_all
from harness.spec_trial import run_trials

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC = (REPO_ROOT / "docs" / "M4-预出口.md").read_text(encoding="utf-8")
TRIALS = REPO_ROOT / "assets" / "trial_specs"


def test_cited_evidence_reproduces() -> None:
    dag = run_dag_eval()
    assert dag.detected == dag.expected_detections and dag.false_positives == 0
    registry = run_registry_eval()
    assert registry.all_ok
    generate_all()
    overall = run_trials(TRIALS)["overall"]
    assert overall.rate == 1.0  # type: ignore[union-attr]
    assert overall.verdict == "report_only"  # type: ignore[union-attr]
    assert "1.0" in DOC and "report_only" in DOC


def test_section7_rows_bound_with_states() -> None:
    assert "DAG 校验 0 例外" in DOC and "registry 校验 100%" in DOC
    assert "任务一次通过率对 Z" in DOC
    assert "Z 线初值待 owner" in DOC
    assert "NEVER 代 owner 画线" in DOC


def test_carried_conditions_honestly_blocked() -> None:
    assert DOC.count("blocked") >= 2, "both carried conditions marked blocked"
    assert "Q-004" in DOC
    assert "M4-044 出口报告「生产口径验证」节" in DOC, "single closing site"
    assert "NEVER 表述为「生产就绪」" in DOC, "wording ban carried forward"
    assert "度量器已落地并离线验证" in DOC, "readiness stated with instruments"


def test_snapshot_matches_ledger() -> None:
    ledger_lines = (
        (REPO_ROOT / "docs" / "progress.jsonl")
        .read_text(encoding="utf-8-sig").splitlines()
    )
    entries = [json.loads(line) for line in ledger_lines if line.strip()]
    m4_verified = {
        e["task_id"] for e in entries
        if str(e["task_id"]).startswith("M4-")
        and str(e["task_id"])[3:].isdigit()
        and e["event"] == "verified"
    }
    m4_blocked_latest = {"M4-040", "M4-041"}
    # 40 = 快照口径：blocked 双卡与对账/出口双卡（043/044）不计入——
    # 本卡自身的 verified 事件晚于成册，计入会自指漂移
    excluded = m4_blocked_latest | {"M4-043", "M4-044"}
    assert len(m4_verified - excluded) == 40, (
        f"doc claims 40 verified work cards, ledger has "
        f"{len(m4_verified - excluded)}"
    )
    for task_id in m4_blocked_latest:
        events = [e["event"] for e in entries if e["task_id"] == task_id]
        # 快照断言的是历史事实（append-only 台账里 blocked 事件在案），
        # 而非「最新态」——赎回重启（started/verified 追加）不改写历史
        assert "blocked" in events, f"{task_id} blocked event not on record"
