"""M3-045 acceptance tests: dispute flow.

Acceptance (tasks.json M3-045):
  - accept -> fact disputed -> excluded from new generation + referencing
    blocks advisory
  - resolved_kept / resolved_replaced both derive a new version and clear
    disputed + related review
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Block, Dispute, HeadingContent
from flint.intervene.dispute import accept_dispute, resolve_dispute
from flint.ledger.disputed import usable_fact_pool
from flint.ledger.store import PgLedgerStore

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
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3045-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3045-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def store() -> PgLedgerStore:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3045-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def fact_add(fact_id: str) -> dict[str, Any]:
    return {
        "fact_id": fact_id, "statement": f"s-{fact_id}", "value": None,
        "unit": None, "citation_ids": [], "status": "frozen",
        "origin": "injected", "created_in_version": 0,
        "source_claim_id": None, "promoted_from": None,
    }


def dispute(target: str, status: str = "open") -> Dispute:
    return Dispute(
        dispute_id="dsp-1", deliverable_id="d-1", target_kind="fact",
        target_id=target, reason_text="数字与原文不符",
        status=status, created_by="u-1", created_at=NOW,  # type: ignore[arg-type]
    )


def block_citing(fact_id: str) -> Block:
    return Block(
        block_id="b-1", deliverable_id="d-1", section_id="s-1", order=0,
        type="heading", content=HeadingContent(kind="heading", level=1, text="t"),
        claim_ids=[], fact_ids=[fact_id], author="system", revision=1,
        locked=False,
    )


def test_accept_marks_disputed_excludes_and_advisories() -> None:
    s = store()
    run(s.derive("m3045-p1", 0, "initial", {"add": [fact_add("f-1")]}))
    outcome = run(accept_dispute(
        s, "m3045-p1", dispute("f-1"), expected_version=1,
        blocks=[block_citing("f-1")],
    ))
    assert outcome.ledger.version == 2
    assert outcome.ledger.derivation_reason == "dispute"
    fact = outcome.ledger.facts[0]
    assert fact.status == "disputed"
    assert usable_fact_pool(outcome.ledger.facts) == [], "excluded from generation"
    assert outcome.marked_blocks[0].review_reason == "fact_disputed"
    assert outcome.marked_blocks[0].review_severity == "advisory"


def test_resolve_kept_restores_and_clears_review() -> None:
    s = store()
    run(s.derive("m3045-p2", 0, "initial", {"add": [fact_add("f-1")]}))
    accepted = run(accept_dispute(
        s, "m3045-p2", dispute("f-1"), 1, blocks=[block_citing("f-1")],
    ))
    resolved = run(resolve_dispute(
        s, "m3045-p2", dispute("f-1", status="resolved_kept"),
        expected_version=2, blocks=accepted.marked_blocks,
    ))
    assert resolved.ledger.version == 3
    assert resolved.ledger.facts[0].status == "frozen", "kept -> restored"
    assert resolved.marked_blocks[0].needs_review is False, "review cleared"
    assert resolved.marked_blocks[0].review_reason is None


def test_resolve_replaced_retires() -> None:
    s = store()
    run(s.derive("m3045-p3", 0, "initial", {"add": [fact_add("f-1")]}))
    run(accept_dispute(s, "m3045-p3", dispute("f-1"), 1, blocks=[]))
    resolved = run(resolve_dispute(
        s, "m3045-p3", dispute("f-1", status="resolved_replaced"),
        expected_version=2, blocks=[],
    ))
    assert resolved.ledger.facts[0].status == "retired", "replaced -> retired"


def test_open_dispute_cannot_resolve() -> None:
    s = store()
    run(s.derive("m3045-p4", 0, "initial", {"add": [fact_add("f-1")]}))
    with pytest.raises(ValueError, match="open"):
        run(resolve_dispute(s, "m3045-p4", dispute("f-1", status="open"),
                            expected_version=1, blocks=[]))
