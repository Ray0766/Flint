"""M3-031 acceptance tests: vibe_pack S5 task cards (structured output).

Acceptance (tasks.json M3-031):
  - TaskSpec full discriminated field set via structured output
    (estimate_cycles / verify_cmd / context_refs / review_gate)
  - exhaustion degrades like section class (chapter gap, tasks never
    guessed); cards pass DagValidator shape checks
"""
from __future__ import annotations

from flint.compose.vibe_tasks import (
    TASK_CARD_SCHEMA,
    S5Extraction,
    extract_task_cards,
    shape_check,
)
from flint.domain.models import JSON, TaskSpec
from flint.llm.structured import validate_schema

GOOD_PAYLOAD: JSON = {
    "tasks": [
        {
            "task_id": "T-001", "title": "建仓与门禁",
            "inputs": ["repo-skeleton"], "outputs": ["ci-gate"],
            "acceptance": ["ruff+mypy+pytest 全绿"], "depends_on": [],
            "milestone": "M1", "estimate_cycles": 1, "oneshot": True,
            "verify_cmd": "pytest tests/t001.py -q",
            "context_refs": ["S3#选型"], "review_gate": True,
        },
        {
            "task_id": "T-002", "title": "数据面",
            "inputs": ["ci-gate"], "outputs": ["schema"],
            "acceptance": ["迁移往返干净"], "depends_on": ["T-001"],
            "milestone": "M1", "estimate_cycles": 2, "oneshot": False,
            "verify_cmd": "pytest tests/t002.py -q",
            "context_refs": ["S3#存储"], "review_gate": False,
        },
    ]
}


class ScriptedProvider:
    def __init__(self, payload: JSON | None) -> None:
        self.payload = payload

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        if self.payload is None:
            from flint.llm.structured import StructuredOutputExhausted

            raise StructuredOutputExhausted(3, ["bad"])
        return self.payload


def test_schema_valid_and_payload_passes() -> None:
    assert validate_schema(TASK_CARD_SCHEMA, GOOD_PAYLOAD) == []


def test_extraction_yields_frozen_task_specs() -> None:
    result = extract_task_cards(
        ScriptedProvider(GOOD_PAYLOAD), section_source="……S5 素材……",  # type: ignore[arg-type]
    )
    assert isinstance(result, S5Extraction)
    assert result.degraded is False
    assert len(result.tasks) == 2
    first = result.tasks[0]
    assert isinstance(first, TaskSpec)
    assert first.estimate_cycles == 1 and first.oneshot is True
    assert first.verify_cmd and first.context_refs and first.review_gate is True
    assert first.estimate_days is None, "ai path never fills human unit"


def test_exhaustion_degrades_never_guesses_tasks() -> None:
    result = extract_task_cards(ScriptedProvider(None), section_source="x")  # type: ignore[arg-type]
    assert result.degraded is True
    assert result.tasks == []
    assert result.gap is not None and result.gap.cause == "missing_data"


def test_shape_check_enforces_dual_unit_rules() -> None:
    good = extract_task_cards(
        ScriptedProvider(GOOD_PAYLOAD), section_source="x",  # type: ignore[arg-type]
    ).tasks
    assert shape_check(good) == []

    bad_cycles = [
        TaskSpec(
            task_id="T-BAD", title="超限", inputs=[], outputs=["x"],
            acceptance=["a"], depends_on=[], milestone="M1",
            estimate_cycles=3, oneshot=False,
            verify_cmd="pytest x", context_refs=["S3"], review_gate=False,
        )
    ]
    assert any("estimate_cycles" in v for v in shape_check(bad_cycles))

    no_verify = [
        TaskSpec(
            task_id="T-NV", title="无验收", inputs=[], outputs=["x"],
            acceptance=["a"], depends_on=[], milestone="M1",
            estimate_cycles=1, oneshot=True,
            verify_cmd=None, context_refs=["S3"], review_gate=False,
        )
    ]
    assert any("verify_cmd" in v for v in shape_check(no_verify))

    dangling = [
        TaskSpec(
            task_id="T-D", title="悬空依赖", inputs=[], outputs=["x"],
            acceptance=["a"], depends_on=["T-GHOST"], milestone="M1",
            estimate_cycles=1, oneshot=True,
            verify_cmd="pytest x", context_refs=["S3"], review_gate=False,
        )
    ]
    assert any("T-GHOST" in v for v in shape_check(dangling))
