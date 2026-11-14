"""M3-003 acceptance tests: PgLedgerStore.derive optimistic lock.

Acceptance (tasks.json M3-003):
  - expected_parent_version mismatch raises LedgerVersionConflict carrying
    current_version + current_facts
  - each of the four reasons derives version+1; concurrent double-derive
    has exactly one winner
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Fact, FactsLedger, LedgerVersionConflict
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
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3003-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3003-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def store(counter: list[int] | None = None) -> PgLedgerStore:
    ids = counter if counter is not None else [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3003-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def fact_add(fact_id: str) -> dict[str, Any]:
    return {
        "fact_id": fact_id, "statement": f"fact {fact_id}", "value": 1.0,
        "unit": "个", "citation_ids": ["cit-1"], "status": "frozen",
        "origin": "injected", "created_in_version": 0,
        "source_claim_id": None, "promoted_from": None,
    }


def test_initial_derive_creates_v1() -> None:
    ledger = run(
        store().derive(
            "m3003-p1", expected_parent_version=0, reason="initial",
            changes={"add": [fact_add("f-1")], "created_from": ["d-1"]},
        )
    )
    assert isinstance(ledger, FactsLedger)
    assert ledger.version == 1 and ledger.parent_version is None
    assert ledger.derivation_reason == "initial"
    assert [f.fact_id for f in ledger.facts] == ["f-1"]
    assert all(isinstance(f, Fact) for f in ledger.facts)
    assert ledger.created_from == ["d-1"]


def test_four_reasons_chain_version_plus_one() -> None:
    s = store()
    run(s.derive("m3003-p2", 0, "initial", {"add": [fact_add("f-1")]}))
    v2 = run(s.derive("m3003-p2", 1, "inject_evidence", {"add": [fact_add("f-2")]}))
    assert v2.version == 2 and v2.parent_version == 1
    assert {f.fact_id for f in v2.facts} == {"f-1", "f-2"}, "parent facts inherited"
    v3 = run(
        s.derive("m3003-p2", 2, "dispute", {"set_status": {"f-1": "disputed"}})
    )
    assert v3.version == 3
    assert {f.fact_id: f.status for f in v3.facts}["f-1"] == "disputed"
    v4 = run(s.derive("m3003-p2", 3, "revalidation", {"set_status": {"f-1": "retired"}}))
    assert v4.version == 4 and v4.derivation_reason == "revalidation"


def test_version_mismatch_raises_conflict_with_current_state() -> None:
    s = store()
    run(s.derive("m3003-p3", 0, "initial", {"add": [fact_add("f-1")]}))
    with pytest.raises(LedgerVersionConflict) as err:
        run(s.derive("m3003-p3", 0, "inject_evidence", {"add": [fact_add("f-2")]}))
    assert err.value.current_version == 1
    assert [f.fact_id for f in err.value.current_facts] == ["f-1"]


def test_concurrent_double_derive_single_winner() -> None:
    s = store()
    run(s.derive("m3003-p4", 0, "initial", {"add": [fact_add("f-1")]}))

    async def race() -> tuple[Any, Any]:
        a = s.derive("m3003-p4", 1, "inject_evidence", {"add": [fact_add("f-a")]})
        b = s.derive("m3003-p4", 1, "inject_evidence", {"add": [fact_add("f-b")]})
        return await asyncio.gather(a, b, return_exceptions=True)

    first, second = run(race())
    outcomes = [first, second]
    winners = [o for o in outcomes if isinstance(o, FactsLedger)]
    losers = [o for o in outcomes if isinstance(o, LedgerVersionConflict)]
    assert len(winners) == 1 and len(losers) == 1, outcomes
    assert winners[0].version == 2
    assert losers[0].current_version == 2, "loser sees the winner's state"
