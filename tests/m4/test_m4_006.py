"""M4-006 acceptance tests: S8/S9 chapters + CLAUDE.md isomorphism.

Acceptance (tasks.json M4-006):
  - S8 renders progress.jsonl convention + trace spec; S9 renders the
    six-stop list and the audit checklist
  - isomorphism asserted against this repo's own CLAUDE.md (double dogfood)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flint.spec.vibe_s89 import (
    HUMAN_NODES,
    LEDGER_EVENTS,
    REVIEW_CHECKLIST,
    STOP_CONDITIONS,
    build_s8,
    build_s9,
)

pytestmark = pytest.mark.compose

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAUDE_MD = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def test_s8_renders_ledger_convention_and_trace_spec() -> None:
    md = build_s8()
    assert md.startswith("## S8 Progress Ledger")
    assert "progress.jsonl" in md and "append-only" in md
    for event in LEDGER_EVENTS:
        assert event in md
    assert "docs/trace/{task_id}.md" in md
    assert "末 20 行" in md, "new-session boot rule"
    assert "NEVER 重做 event=verified" in md


def test_s9_renders_six_stops_and_checklist() -> None:
    md = build_s9()
    assert md.startswith("## S9 Escalation Rules")
    for i, cond in enumerate(STOP_CONDITIONS, start=1):
        assert f"{i}. {cond}；" in md
    assert len(STOP_CONDITIONS) == 6
    for mark in "①②③④⑤":
        assert mark in md
    assert len(REVIEW_CHECKLIST) == 5
    for node in HUMAN_NODES:
        assert node in md


def test_isomorphic_with_own_claude_md() -> None:
    for event in LEDGER_EVENTS:
        assert event in CLAUDE_MD, f"event {event} missing from own S8"
    for cond in STOP_CONDITIONS:
        assert cond.rstrip("；") in CLAUDE_MD, (
            f"stop condition not isomorphic with own S9: {cond}"
        )
    for fragment in (
        "测试真实覆盖 acceptance 语义",
        "无冻结件偏离",
        "trace 与 progress.jsonl 完整",
        "装载未超预算",
    ):
        assert fragment in CLAUDE_MD, f"checklist item drifted: {fragment}"
    for node in HUMAN_NODES:
        assert node in CLAUDE_MD, f"human node drifted: {node}"
    assert "末 20 行" in CLAUDE_MD and "末 20 行" in build_s8()
