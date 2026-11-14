"""M4-021 acceptance tests: dual-unit mutual-exclusion validation.

Acceptance (tasks.json M4-021):
  - human_reader: estimate_days mandatory <=0.5 and cycles must be absent;
    ai_executor: cycles mandatory <=2 + verify_cmd mandatory and days absent
  - violations identified per card (v0.3.3 wording)
"""
from __future__ import annotations

from flint.dag.dual_unit import validate_dual_unit
from flint.domain.models import TaskSpec


def task(task_id: str, **overrides: object) -> TaskSpec:
    base: dict = {
        "task_id": task_id, "title": task_id, "inputs": [], "outputs": ["x"],
        "acceptance": ["a"], "depends_on": [], "milestone": "M1",
        "estimate_days": None, "estimate_cycles": None, "oneshot": None,
        "verify_cmd": None, "context_refs": ["S3"], "review_gate": None,
    }
    base.update(overrides)
    return TaskSpec(**base)  # type: ignore[arg-type]


def ai_task(task_id: str, **overrides: object) -> TaskSpec:
    defaults: dict = {
        "estimate_cycles": 1, "oneshot": True, "verify_cmd": "pytest x",
        "review_gate": False,
    }
    defaults.update(overrides)
    return task(task_id, **defaults)


def human_task(task_id: str, **overrides: object) -> TaskSpec:
    defaults: dict = {"estimate_days": 0.5}
    defaults.update(overrides)
    return task(task_id, **defaults)


def test_valid_both_audiences() -> None:
    assert validate_dual_unit([ai_task("T-ai")], audience="ai_executor") == []
    assert validate_dual_unit([human_task("T-h")], audience="human_reader") == []


def test_ai_violations_each_identified() -> None:
    missing_cycles = ai_task("T-1", estimate_cycles=None)
    over_cycles = ai_task("T-2", estimate_cycles=3)
    no_verify = ai_task("T-3", verify_cmd=None)
    days_leak = ai_task("T-4", estimate_days=0.25)
    violations = validate_dual_unit(
        [missing_cycles, over_cycles, no_verify, days_leak],
        audience="ai_executor",
    )
    assert any("T-1" in v and "estimate_cycles" in v for v in violations)
    assert any("T-2" in v and "2" in v for v in violations)
    assert any("T-3" in v and "verify_cmd" in v for v in violations)
    assert any("T-4" in v and "estimate_days" in v for v in violations)


def test_human_violations_each_identified() -> None:
    missing_days = human_task("T-1", estimate_days=None)
    over_days = human_task("T-2", estimate_days=1.0)
    cycles_leak = human_task("T-3", estimate_cycles=1)
    violations = validate_dual_unit(
        [missing_days, over_days, cycles_leak], audience="human_reader"
    )
    assert any("T-1" in v and "estimate_days" in v for v in violations)
    assert any("T-2" in v and "0.5" in v for v in violations)
    assert any("T-3" in v and "estimate_cycles" in v for v in violations)
