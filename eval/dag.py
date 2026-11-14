"""dag 评测（M4-026，技术方案 E9：构造违规全景）。

- 五类构造违规（环 / 孤儿 / 悬空依赖不可达 / 双单位串漏 / verify 覆盖
  率缺口）各一最小用例 + 一个干净 DAG——期望由构造处携带（生成器即
  真相判例）：违规用例给 expect_fragment，干净用例给 None。
- 断言面：违规全部检出（fragment 落在 errors 内）且干净 DAG 零误报。
"""
from __future__ import annotations

from dataclasses import dataclass

from flint.dag.validator import validate
from flint.domain.models import TaskSpec


def _card(
    task_id: str,
    depends_on: list[str],
    cycles: float | None = 1.0,
    verify_cmd: str | None = "pytest x -q",
    days: float | None = None,
) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=task_id, inputs=["repo-skeleton"],
        outputs=[f"mod.{task_id}"], acceptance=["a"], depends_on=depends_on,
        milestone="M1", estimate_days=days, estimate_cycles=cycles,
        oneshot=True, verify_cmd=verify_cmd,
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )


@dataclass(frozen=True)
class DagEvalCase:
    name: str
    tasks: list[TaskSpec]
    expect_fragment: str | None  # None = 期望零 errors


@dataclass(frozen=True)
class DagEvalRow:
    name: str
    expect_fragment: str | None
    hit: bool
    error_count: int


@dataclass(frozen=True)
class DagEvalReport:
    rows: list[DagEvalRow]
    detected: int
    expected_detections: int
    false_positives: int


def build_cases() -> list[DagEvalCase]:
    return [
        DagEvalCase(
            name="cycle",
            tasks=[_card("T-1", ["T-2"]), _card("T-2", ["T-1"])],
            expect_fragment="cycle",
        ),
        DagEvalCase(
            name="orphan",
            tasks=[
                _card("T-1", []),
                _card("T-exit", ["T-1"]),
                _card("T-orphan", ["T-1"]),
            ],
            expect_fragment="T-orphan",
        ),
        DagEvalCase(
            name="dangling-dep",
            tasks=[_card("T-1", ["T-ghost"])],
            expect_fragment="T-ghost",
        ),
        DagEvalCase(
            name="dual-unit-leak",
            tasks=[_card("T-1", [], days=0.25)],
            expect_fragment="estimate_days must be absent",
        ),
        DagEvalCase(
            name="verify-coverage-gap",
            tasks=[_card("T-1", [], verify_cmd=None)],
            expect_fragment="verify_cmd",
        ),
        DagEvalCase(
            name="clean",
            tasks=[_card("T-1", []), _card("T-2", ["T-1"])],
            expect_fragment=None,
        ),
    ]


def run_dag_eval() -> DagEvalReport:
    rows: list[DagEvalRow] = []
    detected = 0
    expected = 0
    false_positives = 0
    for case in build_cases():
        exit_ids = {case.tasks[-1].task_id} if case.expect_fragment != "T-orphan" else {"T-exit"}
        report = validate(
            case.tasks, external_inputs={"repo-skeleton"}, exit_ids=exit_ids
        )
        # 检出面 = 冻结 DagReport 全表面：orphans/unreachable 有独立字段，
        # 不在 errors 内重复
        findings = [*report.errors, *report.orphans, *report.unreachable]
        if case.expect_fragment is None:
            hit = not findings
            false_positives += len(findings)
        else:
            expected += 1
            hit = any(case.expect_fragment in item for item in findings)
            if hit:
                detected += 1
        rows.append(
            DagEvalRow(
                name=case.name,
                expect_fragment=case.expect_fragment,
                hit=hit,
                error_count=len(findings),
            )
        )
    return DagEvalReport(
        rows=rows,
        detected=detected,
        expected_detections=expected,
        false_positives=false_positives,
    )
