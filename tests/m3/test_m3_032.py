"""M3-032 acceptance tests: audience fork entry.

Acceptance (tasks.json M3-032):
  - ProposalContext.audience mandatory with no default; ai_executor forces
    vibe_pack template, human templates rejected for it
  - dual-audience versions of one report pin the same ledger version and
    cross-link as siblings
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.compose.audience import (
    AudienceForkError,
    link_siblings,
    plan_proposal,
)
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import Deliverable

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3032-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def test_audience_mandatory_no_default() -> None:
    with pytest.raises(AudienceForkError, match="audience"):
        plan_proposal(audience=None, template_id="generic")


def test_ai_executor_forces_vibe_pack() -> None:
    plan = plan_proposal(audience="ai_executor", template_id=None)
    assert plan.template_id == "vibe_pack"
    assert plan.deliverable_type == "vibe_pack"

    with pytest.raises(AudienceForkError, match="vibe_pack"):
        plan_proposal(audience="ai_executor", template_id="startup")


def test_human_reader_needs_one_of_five() -> None:
    plan = plan_proposal(audience="human_reader", template_id="grant")
    assert plan.template_id == "grant"
    assert plan.deliverable_type == "proposal"
    with pytest.raises(AudienceForkError, match="human"):
        plan_proposal(audience="human_reader", template_id="vibe_pack")
    with pytest.raises(AudienceForkError, match="template"):
        plan_proposal(audience="human_reader", template_id=None)


def deliverable(deliverable_id: str, dtype: str, ledger_version: int) -> Deliverable:
    return Deliverable(
        deliverable_id=deliverable_id, project_id="p-1", type=dtype,  # type: ignore[arg-type]
        version=1, supersedes=None, inputs=["report-1"],
        ledger_version=ledger_version, generation_record_id="gr-1",
        stale_reasons=[], created_at=NOW,
    )


def test_siblings_pin_same_ledger_and_cross_link() -> None:
    store = PgDeliverableStore(dsn=DSN)
    human = deliverable("m3032-h", "proposal", ledger_version=4)
    pack = deliverable("m3032-a", "vibe_pack", ledger_version=4)
    run(store.save_deliverable(human))
    run(store.save_deliverable(pack))
    run(link_siblings(DSN, human, pack))

    async def metas() -> dict[str, Any]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT deliverable_id, meta FROM deliverables "
                "WHERE deliverable_id LIKE 'm3032-%' ORDER BY deliverable_id"
            )
            import json as j

            return {r["deliverable_id"]: j.loads(r["meta"]) for r in rows}
        finally:
            await conn.close()

    meta = run(metas())
    assert meta["m3032-h"]["sibling_deliverable_id"] == "m3032-a"
    assert meta["m3032-a"]["sibling_deliverable_id"] == "m3032-h"


def test_sibling_link_rejects_different_ledger_versions() -> None:
    store = PgDeliverableStore(dsn=DSN)
    human = deliverable("m3032-h2", "proposal", ledger_version=4)
    pack = deliverable("m3032-a2", "vibe_pack", ledger_version=5)
    run(store.save_deliverable(human))
    run(store.save_deliverable(pack))
    with pytest.raises(AudienceForkError, match="ledger"):
        run(link_siblings(DSN, human, pack))
