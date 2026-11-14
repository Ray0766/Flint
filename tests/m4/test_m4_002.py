"""M4-002 acceptance tests: human-path spec export.

Acceptance (tasks.json M4-002):
  - human_reader path yields a spec-class Deliverable plan; audience fork
    never mixes (ai_executor standalone spec rejected, ai-unit cards rejected)
  - exported entries annotate acceptance as test-assertion candidates
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import pytest

from flint.domain.models import TaskSpec
from flint.spec.export_human import (
    PgHumanSpecExporter,
    SpecExportForkError,
    build_entries,
    plan_spec_deliverable,
)
from flint.spec.store import PgSpecStore

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM task_specs WHERE spec_set_id LIKE 'm4002-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def human_card(task_id: str) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"human {task_id}",
        inputs=["素材"], outputs=["产物"],
        acceptance=["三条主流程可走通", "首屏加载 <2s"], depends_on=[],
        milestone="M1", estimate_days=0.5,
        estimate_cycles=None, oneshot=None, verify_cmd=None,
        context_refs=None, review_gate=None,
    )


def ai_card(task_id: str) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"ai {task_id}",
        inputs=["repo"], outputs=["mod"], acceptance=["a"], depends_on=[],
        milestone="M1", estimate_days=None, estimate_cycles=1.0,
        oneshot=True, verify_cmd="pytest x", context_refs=["S3"],
        review_gate=False,
    )


def test_spec_deliverable_is_human_only() -> None:
    assert plan_spec_deliverable("human_reader") == "spec"
    with pytest.raises(SpecExportForkError, match="vibe_pack"):
        plan_spec_deliverable("ai_executor")
    with pytest.raises(SpecExportForkError, match="audience"):
        plan_spec_deliverable(None)


def test_entries_annotate_acceptance_as_assertions() -> None:
    entries = build_entries([human_card("T-1")])
    assert len(entries) == 1
    entry = entries[0]
    assert entry.task.task_id == "T-1"
    assert len(entry.assertions) == 2, "one annotation per acceptance item"
    assert entry.assertions[0] == "断言候选 1/2：三条主流程可走通"
    assert entry.assertions[1] == "断言候选 2/2：首屏加载 <2s"


def test_ai_unit_cards_never_enter_human_spec() -> None:
    with pytest.raises(SpecExportForkError, match="ai_executor"):
        build_entries([human_card("T-1"), ai_card("T-2")])


def test_exporter_protocol_roundtrip_via_store() -> None:
    run(PgSpecStore(DSN).save_set("m4002-p1", [human_card("T-1"), human_card("T-2")]))
    exporter = PgHumanSpecExporter(DSN)
    tasks = exporter.export("m4002-p1")
    assert [t.task_id for t in tasks] == ["T-1", "T-2"]
    assert all(t.estimate_days is not None for t in tasks)
