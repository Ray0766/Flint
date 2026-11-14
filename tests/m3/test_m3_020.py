"""M3-020 acceptance tests: freeze_ledger (aggregate + promote).

Acceptance (tasks.json M3-020):
  - aggregates claims across deliverable_ids -> ClaimPromoter -> new ledger
    version
  - refreezing the same input is idempotent (same version content)
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import pytest

from flint.compose.freeze import freeze_ledger
from flint.domain.models import Claim, FactsLedger
from flint.ledger.read import get_ledger
from flint.ledger.store import PgLedgerStore

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
                "DELETE FROM facts WHERE ledger_id IN "
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3020-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3020-%'"
            )
            await conn.execute("DELETE FROM claims WHERE claim_id LIKE 'm3020-%'")
        finally:
            await conn.close()

    run(wipe())


def store() -> PgLedgerStore:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3020-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id)


def claim(cid: str, deliverable_id: str, alignment: str = "supports") -> Claim:
    return Claim(
        claim_id=cid, deliverable_id=deliverable_id, block_id="b-1",
        text_span=f"结论 {cid}", confidence="cited",
        citation_ids=[f"cit-{cid}"], alignment=alignment,  # type: ignore[arg-type]
    )


async def _persist_claims(claims: list[Claim]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        await conn.executemany(
            "INSERT INTO claims (claim_id, deliverable_id, block_id, text_span, "
            "confidence, citation_ids, alignment, promoted_fact_id) VALUES "
            "($1, $2, $3, $4, $5, $6::jsonb, $7, $8)",
            [
                (c.claim_id, c.deliverable_id, c.block_id, c.text_span,
                 c.confidence, f'["cit-{c.claim_id}"]', c.alignment,
                 c.promoted_fact_id)
                for c in claims
            ],
        )
    finally:
        await conn.close()


def test_freeze_aggregates_promotes_and_versions() -> None:
    run(_persist_claims([
        claim("m3020-c1", "d-1"),
        claim("m3020-c2", "d-2"),
        claim("m3020-c3", "d-1", alignment="partial"),  # never promoted
    ]))
    ledger = run(
        freeze_ledger(
            DSN, store(), project_id="m3020-p1",
            deliverable_ids=["d-1", "d-2"], actor="u-1",
        )
    )
    assert isinstance(ledger, FactsLedger)
    assert ledger.version == 1
    assert ledger.derivation_reason == "initial"
    assert ledger.created_from == ["d-1", "d-2"]
    assert {f.source_claim_id for f in ledger.facts} == {"m3020-c1", "m3020-c2"}
    assert all(f.origin == "promoted_claim" for f in ledger.facts)

    async def promoted_backfill() -> list[str | None]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT promoted_fact_id FROM claims WHERE claim_id LIKE 'm3020-%' "
                "ORDER BY claim_id"
            )
            return [r["promoted_fact_id"] for r in rows]
        finally:
            await conn.close()

    backfilled = run(promoted_backfill())
    assert backfilled[0] is not None and backfilled[1] is not None
    assert backfilled[2] is None, "partial claim stays unpromoted in the DB"


def test_refreeze_same_input_idempotent_content() -> None:
    run(_persist_claims([claim("m3020-c9", "d-9")]))
    shared = store()
    first = run(
        freeze_ledger(DSN, shared, "m3020-p2", ["d-9"], actor="u-1")
    )
    second = run(
        freeze_ledger(DSN, shared, "m3020-p2", ["d-9"], actor="u-1")
    )
    assert second.version == 2, "refreeze derives a new version"
    assert [f.fact_id for f in second.facts] == [f.fact_id for f in first.facts], (
        "same input -> same fact ids (deterministic promotion)"
    )
    v1 = run(get_ledger(DSN, "m3020-p2", 1))
    assert [f.fact_id for f in v1.facts] == [f.fact_id for f in second.facts]
