"""M4-005 acceptance tests: S7 Verification Harness chapter.

Acceptance (tasks.json M4-005):
  - verify_cmd roll-up + global gate declaration + rework-loop rule rendered
  - tasks without verify_cmd: zero tolerance, chapter build rejects
"""
from __future__ import annotations

import pytest

from flint.domain.models import TaskSpec
from flint.spec.vibe_s7 import S7VerifyError, build_s7

pytestmark = pytest.mark.compose

GLOBAL_GATE = "ruff check . && mypy --strict pkg && pytest -q"


def ai_card(task_id: str, verify_cmd: str | None) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=["repo"], outputs=["mod"],
        acceptance=["a"], depends_on=[], milestone="M1",
        estimate_days=None, estimate_cycles=1.0, oneshot=True,
        verify_cmd=verify_cmd, context_refs=["S3"], review_gate=False,
    )


def test_chapter_rolls_up_cmds_gate_and_rework_rule() -> None:
    tasks = [ai_card("T-1", "pytest tests/a.py -q"), ai_card("T-2", "pytest tests/b.py -q")]
    md = build_s7(tasks, global_gate=GLOBAL_GATE)
    assert md.startswith("## S7 Verification Harness")
    assert "| T-1 | pytest tests/a.py -q |" in md
    assert "| T-2 | pytest tests/b.py -q |" in md
    assert GLOBAL_GATE in md, "global gate declared verbatim"
    assert "连续 2 次失败" in md and "S9" in md, "rework loop escalation rule"
    assert "先写失败测试" in md, "test-first order stated"


def test_missing_verify_cmd_zero_tolerance() -> None:
    with pytest.raises(S7VerifyError, match="T-2"):
        build_s7(
            [ai_card("T-1", "pytest x"), ai_card("T-2", None)],
            global_gate=GLOBAL_GATE,
        )
    with pytest.raises(S7VerifyError, match="T-3"):
        build_s7([ai_card("T-3", "")], global_gate=GLOBAL_GATE)
