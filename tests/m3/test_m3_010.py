"""M3-010 acceptance tests: deliverable versioning + GenerationRecord.

Acceptance (tasks.json M3-010):
  - regeneration bumps version+1 and the old version stays readable
  - GenerationRecord full-field persistence linked to deliverable/job
    (incl optin / alignment_rate intake slots)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import Deliverable, GenerationRecord

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
                "DELETE FROM generation_records WHERE record_id LIKE 'm3010-%'"
            )
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3010-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def record(record_id: str, deliverable_id: str) -> GenerationRecord:
    return GenerationRecord(
        record_id=record_id, deliverable_id=deliverable_id, job_id="j-1",
        prompt_version="gate1_verdict@3#abc", model="claude-sonnet-5",
        params={"seed": 1}, retrieval_snapshot_id="snap-1", ledger_version=2,
        pricebook_version="pb-1", user_evidence_verdict_optin=True,
        ts=NOW, cost=1.25, alignment_rate=0.97, structured_output_failures=1,
    )


def deliverable(deliverable_id: str, version: int,
                supersedes: str | None, record_id: str) -> Deliverable:
    return Deliverable(
        deliverable_id=deliverable_id, project_id="p-1", type="report",
        version=version, supersedes=supersedes, inputs=["d-0"],
        ledger_version=2, generation_record_id=record_id,
        stale_reasons=[], created_at=NOW,
    )


def test_generation_record_full_field_round_trip() -> None:
    store = PgDeliverableStore(dsn=DSN)
    rec = record("m3010-r1", "m3010-d1")
    run(store.save_generation_record(rec))
    loaded = run(store.load_generation_record("m3010-r1"))
    assert loaded == rec, "all fourteen fields incl optin + alignment_rate"


def test_regeneration_bumps_version_old_readable() -> None:
    store = PgDeliverableStore(dsn=DSN)
    run(store.save_generation_record(record("m3010-r1", "m3010-d1")))
    run(store.save_generation_record(record("m3010-r2", "m3010-d2")))
    v1 = deliverable("m3010-d1", 1, None, "m3010-r1")
    run(store.save_deliverable(v1))

    v2 = run(
        store.new_version(
            v1, new_deliverable_id="m3010-d2", generation_record_id="m3010-r2"
        )
    )
    assert v2.version == 2
    assert v2.supersedes == "m3010-d1"

    old = run(store.load_deliverable("m3010-d1"))
    assert old.version == 1, "old version stays readable"
    new = run(store.load_deliverable("m3010-d2"))
    assert new.generation_record_id == "m3010-r2"


def test_unknown_deliverable_raises() -> None:
    store = PgDeliverableStore(dsn=DSN)
    with pytest.raises(KeyError):
        run(store.load_deliverable("m3010-nope"))
