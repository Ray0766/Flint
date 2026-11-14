"""M1-041 acceptance tests: M1 exit report (checked against PDD v0.3.1 §7 M1 row).

Acceptance (tasks.json M1-041):
  - lineage >=90% evidence + drill logs + trace attachments bound into the report
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT = REPO_ROOT / "docs" / "M1-出口报告.md"


def report_text() -> str:
    assert REPORT.is_file(), "exit report missing"
    return REPORT.read_text(encoding="utf-8")


def test_both_exit_assertions_checked() -> None:
    text = report_text()
    assert "100%（50/50）" in text, "lineage accuracy evidence"
    assert "7/7" in text, "seven-day drill evidence"
    assert "§7" in text and "待 owner 人审" in text


def test_evidence_artifacts_exist_on_disk() -> None:
    assert (REPO_ROOT / "assets" / "labels.yaml").is_file()
    assert (REPO_ROOT / "docs" / "trace" / "drill7.md").is_file()
    replay_traces = list((REPO_ROOT / "docs" / "trace" / "replay30").glob("*.md"))
    assert len(replay_traces) == 30


def test_trace_roster_complete_for_all_41_tasks() -> None:
    for i in range(1, 42):
        path = REPO_ROOT / "docs" / "trace" / f"M1-{i:03d}.md"
        assert path.is_file(), f"trace missing for M1-{i:03d}"


def test_ledger_records_all_tasks_verified_and_gates_passed() -> None:
    lines = (
        (REPO_ROOT / "docs" / "progress.jsonl")
        .read_text(encoding="utf-8-sig")
        .splitlines()
    )
    events = [json.loads(line) for line in lines if line.strip()]
    verified = {e["task_id"] for e in events if e["event"] == "verified"}
    # M1-041 自身的 verified 按 S7 顺序在本测试通过之后落账，此处断言其 started
    for i in range(1, 41):
        assert f"M1-{i:03d}" in verified, f"M1-{i:03d} lacks verified event"
    started = {e["task_id"] for e in events if e["event"] == "started"}
    assert "M1-041" in started
    gates = {
        "M1-007", "M1-015", "M1-029", "M1-032", "M1-034",
        "M1-035", "M1-037", "M1-039", "M1-040",
    }
    passed = {e["task_id"] for e in events if e["event"] == "review_passed"}
    assert gates <= passed, f"gates missing review_passed: {gates - passed}"


def test_owner_decision_items_enumerated() -> None:
    text = report_text()
    for anchor in ("七要素", "lineage_id", "redis", "split/merge", "async def"):
        assert anchor in text, f"owner checklist must cover: {anchor}"
