"""M4-020 acceptance tests: inputs provenance validation.

Acceptance (tasks.json M4-020):
  - every task's inputs must be a predecessor's outputs or a whitelisted
    external artifact
  - dangling inputs identified per card
"""
from __future__ import annotations

from flint.dag.inputs import validate_inputs
from flint.domain.models import TaskSpec


def task(task_id: str, inputs: list[str], outputs: list[str],
         depends_on: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=inputs, outputs=outputs,
        acceptance=["a"], depends_on=depends_on, milestone="M1",
        estimate_cycles=1, oneshot=True, verify_cmd="pytest x",
        context_refs=["S3"], review_gate=False,
    )


def test_predecessor_outputs_accepted() -> None:
    tasks = [
        task("T-1", ["repo-skeleton"], ["schema"], []),
        task("T-2", ["schema"], ["service"], ["T-1"]),
    ]
    assert validate_inputs(tasks, external={"repo-skeleton"}) == []


def test_dangling_input_identified_per_card() -> None:
    tasks = [
        task("T-1", [], ["schema"], []),
        task("T-2", ["phantom-artifact"], ["service"], ["T-1"]),
    ]
    violations = validate_inputs(tasks, external={"repo-skeleton"})
    assert len(violations) == 1
    assert "T-2" in violations[0] and "phantom-artifact" in violations[0]


def test_output_of_non_predecessor_rejected() -> None:
    """inputs 须来自**前置**任务的 outputs——旁支产物不许直取（溯源纪律）。"""
    tasks = [
        task("T-1", [], ["schema"], []),
        task("T-side", [], ["gadget"], []),
        task("T-2", ["gadget"], ["service"], ["T-1"]),  # gadget 非前置产物
    ]
    violations = validate_inputs(tasks, external=set())
    assert any("T-2" in v and "gadget" in v for v in violations)


def test_transitive_predecessors_count() -> None:
    tasks = [
        task("T-1", [], ["schema"], []),
        task("T-2", [], ["service"], ["T-1"]),
        task("T-3", ["schema"], ["ui"], ["T-2"]),  # 祖传产物：经 T-2 传递可达
    ]
    assert validate_inputs(tasks, external=set()) == []
