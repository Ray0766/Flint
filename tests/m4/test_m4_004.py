"""M4-004 acceptance tests: S6 Context Manifest chapter.

Acceptance (tasks.json M4-004):
  - per-task context_refs aggregate into S6 loading rules (always-on +
    on-demand + budget lines)
  - anchor existence validated: dangling refs rejected
"""
from __future__ import annotations

import pytest

from flint.dag.quality_gate import CONTEXT_BUDGET_TOKENS
from flint.domain.models import TaskSpec
from flint.spec.vibe_s6 import S6RefError, build_s6

pytestmark = pytest.mark.compose


def ai_card(task_id: str, refs: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=["repo"], outputs=["mod"],
        acceptance=["a"], depends_on=[], milestone="M1",
        estimate_days=None, estimate_cycles=1.0, oneshot=True,
        verify_cmd="pytest x", context_refs=refs, review_gate=False,
    )


ANCHORS = frozenset(
    {"contracts/models.py#TaskSpec", "tech.md#E5", "tech.md#E7"}
)


def test_chapter_renders_three_rule_groups() -> None:
    tasks = [
        ai_card("T-1", ["contracts/models.py#TaskSpec", "tech.md#E5"]),
        ai_card("T-2", ["tech.md#E5"]),
    ]
    md = build_s6(tasks, known_anchors=ANCHORS)
    assert md.startswith("## S6 Context Manifest")
    assert "恒装" in md and "按需" in md
    assert str(CONTEXT_BUDGET_TOKENS) in md, (
        "budget line cites the single shared constant"
    )
    assert "| T-1 | contracts/models.py#TaskSpec, tech.md#E5 |" in md
    assert "| T-2 | tech.md#E5 |" in md


def test_dangling_ref_rejected_with_task_pointer() -> None:
    tasks = [ai_card("T-9", ["tech.md#E99"])]
    with pytest.raises(S6RefError, match=r"T-9.*tech\.md#E99"):
        build_s6(tasks, known_anchors=ANCHORS)


def test_missing_refs_rejected() -> None:
    with pytest.raises(S6RefError, match="T-0"):
        build_s6([ai_card("T-0", [])], known_anchors=ANCHORS)
