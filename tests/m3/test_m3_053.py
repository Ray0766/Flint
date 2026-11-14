"""M3-053 acceptance tests: accept -> ledger derivation + unified stale.

Acceptance (tasks.json M3-053):
  - accept goes through LedgerStore.derive(reason=revalidation)
  - blocks citing old facts get marked via the unified diff/stale mechanism
    (D8)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import (
    Block,
    HeadingContent,
    RevalidationReport,
    Staleness,
)
from flint.ledger.store import PgLedgerStore
from flint.revalidate.accept import accept_report

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
                "DELETE FROM facts WHERE ledger_id IN "
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3053-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3053-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def store() -> PgLedgerStore:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3053-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def fact_add(fact_id: str, statement: str = "s") -> dict[str, Any]:
    return {
        "fact_id": fact_id, "statement": statement, "value": None, "unit": None,
        "citation_ids": [], "status": "frozen", "origin": "injected",
        "created_in_version": 0, "source_claim_id": None, "promoted_from": None,
    }


def report() -> RevalidationReport:
    return RevalidationReport(
        report_id="rvr-1", deliverable_id="d-1", new_papers=["doc-n1"],
        new_competitors=[], heat_shift={}, verdict_shift=None,
        trigger="scheduled", generated_at=NOW, accepted=None,
    )


def block_citing(fact_id: str) -> Block:
    return Block(
        block_id=f"b-{fact_id}", deliverable_id="d-1", section_id="s-1", order=0,
        type="heading", content=HeadingContent(kind="heading", level=1, text="t"),
        claim_ids=[], fact_ids=[fact_id], author="system", revision=1,
        locked=False,
    )


def test_accept_derives_revalidation_and_marks_stale() -> None:
    s = store()
    run(s.derive("m3053-p1", 0, "initial",
                 {"add": [fact_add("f-1"), fact_add("f-2")]}))
    outcome = run(accept_report(
        store=s, project_id="m3053-p1", report=report(), expected_version=1,
        changes={
            "add": [fact_add("f-new", statement="复核新增")],
            "set_status": {"f-1": "retired"},
        },
        blocks=[block_citing("f-1"), block_citing("f-2")],
        now=NOW,
    ))
    assert outcome.ledger.version == 2
    assert outcome.ledger.derivation_reason == "revalidation"
    assert outcome.report.accepted is True

    marked = {b.block_id: b for b in outcome.marked_blocks}
    assert marked["b-f-1"].review_reason == "fact_removed"
    assert marked["b-f-1"].review_severity == "blocking"
    assert marked["b-f-2"].needs_review is False, "untouched fact zero pollution"

    stale = outcome.staleness
    assert isinstance(stale, Staleness)
    assert stale.reason == "ledger_changed"
    assert stale.revalidation_report_id == "rvr-1"
