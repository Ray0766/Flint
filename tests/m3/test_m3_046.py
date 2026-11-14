"""M3-046 acceptance tests: dispute conflict -> user-confirm resubmit.

Acceptance (tasks.json M3-046):
  - version conflict is NOT auto-replayed: surfaced for user confirmation
    (audit-4 opposite of inject)
  - confirmed resubmit applies on the new version
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Dispute
from flint.intervene.dispute_retry import (
    DisputeConfirmationRequired,
    accept_with_confirmation,
    confirm_resubmit,
)
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
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3046-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3046-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def store() -> PgLedgerStore:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3046-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def fact_add(fact_id: str) -> dict[str, Any]:
    return {
        "fact_id": fact_id, "statement": "s", "value": None, "unit": None,
        "citation_ids": [], "status": "frozen", "origin": "injected",
        "created_in_version": 0, "source_claim_id": None, "promoted_from": None,
    }


def dispute() -> Dispute:
    return Dispute(
        dispute_id="dsp-1", deliverable_id="d-1", target_kind="fact",
        target_id="f-1", reason_text="有争议", status="open",
        created_by="u-1", created_at=NOW,
    )


def test_conflict_surfaces_for_confirmation_never_auto_replays() -> None:
    s = store()
    run(s.derive("m3046-p1", 0, "initial", {"add": [fact_add("f-1")]}))
    run(s.derive("m3046-p1", 1, "inject_evidence", {"add": []}))  # 并发前进到 v2

    derive_calls = {"n": 0}
    original = s.derive

    async def counting(*args: Any, **kwargs: Any) -> Any:
        derive_calls["n"] += 1
        return await original(*args, **kwargs)

    s.derive = counting  # type: ignore[method-assign]
    with pytest.raises(DisputeConfirmationRequired) as err:
        run(accept_with_confirmation(
            s, "m3046-p1", dispute(), expected_version=1, blocks=[],
        ))
    assert derive_calls["n"] == 1, "exactly one attempt, no silent replay"
    assert err.value.current_version == 2, "user sees the fresh state to confirm"


def test_confirmed_resubmit_applies_on_new_version() -> None:
    s = store()
    run(s.derive("m3046-p2", 0, "initial", {"add": [fact_add("f-1")]}))
    run(s.derive("m3046-p2", 1, "inject_evidence", {"add": []}))

    outcome = run(confirm_resubmit(
        s, "m3046-p2", dispute(), confirmed_version=2, blocks=[],
    ))
    assert outcome.ledger.version == 3
    assert outcome.ledger.facts[0].status == "disputed"
