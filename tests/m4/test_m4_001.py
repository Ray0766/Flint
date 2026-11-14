"""M4-001 acceptance tests: spec data plane (TaskSpec persistence).

Acceptance (tasks.json M4-001):
  - TaskSpec all fields (dual-unit discriminated) survive JSONB round-trip
  - reads grouped by spec set return deterministic order
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import pytest

from flint.domain.models import TaskSpec
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
                "DELETE FROM task_specs WHERE spec_set_id LIKE 'm4001-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def human_card(task_id: str) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"human {task_id}",
        inputs=["需求清单"], outputs=["原型稿"],
        acceptance=["原型覆盖三条主流程"], depends_on=[],
        milestone="M1", estimate_days=0.5,
        estimate_cycles=None, oneshot=None, verify_cmd=None,
        context_refs=None, review_gate=None,
    )


def ai_card(task_id: str, depends_on: list[str]) -> TaskSpec:
    return TaskSpec(
        task_id=task_id, title=f"ai {task_id}",
        inputs=["repo-skeleton"], outputs=[f"module.{task_id}"],
        acceptance=["JSONB 往返无损", "确定序读取"], depends_on=depends_on,
        milestone="M1", estimate_days=None,
        estimate_cycles=1.0, oneshot=True,
        verify_cmd=f"pytest tests/test_{task_id}.py -q",
        context_refs=["contracts/models.py#TaskSpec"], review_gate=False,
    )


def test_dual_unit_roundtrip_lossless() -> None:
    store = PgSpecStore(DSN)
    cards = [human_card("T-h1"), ai_card("T-a1", []), ai_card("T-a2", ["T-a1"])]
    run(store.save_set("m4001-set-a", cards))
    loaded = run(store.load_set("m4001-set-a"))
    assert loaded == cards, "dataclass equality = every field round-trips"
    assert loaded[0].estimate_days == 0.5 and loaded[0].estimate_cycles is None
    assert loaded[1].estimate_cycles == 1.0 and loaded[1].estimate_days is None


def test_deterministic_order_and_set_isolation() -> None:
    store = PgSpecStore(DSN)
    ordered = [ai_card(f"T-{i:02d}", []) for i in (3, 1, 2)]
    run(store.save_set("m4001-set-b", ordered))
    run(store.save_set("m4001-set-c", [ai_card("T-other", [])]))
    for _ in range(3):
        loaded = run(store.load_set("m4001-set-b"))
        assert [t.task_id for t in loaded] == ["T-03", "T-01", "T-02"], (
            "insertion order preserved, not id order"
        )


def test_save_set_replaces_previous_content() -> None:
    store = PgSpecStore(DSN)
    run(store.save_set("m4001-set-d", [ai_card("T-old", [])]))
    run(store.save_set("m4001-set-d", [ai_card("T-new", [])]))
    loaded = run(store.load_set("m4001-set-d"))
    assert [t.task_id for t in loaded] == ["T-new"]


def test_missing_set_returns_empty() -> None:
    store = PgSpecStore(DSN)
    assert run(store.load_set("m4001-none")) == []
