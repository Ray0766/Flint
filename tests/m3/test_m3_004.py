"""M3-004 acceptance tests: ledger version read + derivation chain.

Acceptance (tasks.json M3-004):
  - get(project_id, version) reads the exact version; unknown version raises
    KeyError
  - initial derivation builds from zero (parent_version None semantics)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import FactsLedger
from flint.ledger.read import get_ledger
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
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3004-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3004-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def store() -> PgLedgerStore:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3004-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def fact_add(fact_id: str) -> dict[str, Any]:
    return {
        "fact_id": fact_id, "statement": f"fact {fact_id}", "value": None,
        "unit": None, "citation_ids": [], "status": "frozen",
        "origin": "injected", "created_in_version": 0,
        "source_claim_id": None, "promoted_from": None,
    }


def test_get_exact_version_with_facts() -> None:
    s = store()
    run(s.derive("m3004-p1", 0, "initial", {"add": [fact_add("f-1")]}))
    run(s.derive("m3004-p1", 1, "inject_evidence", {"add": [fact_add("f-2")]}))

    v1 = run(get_ledger(DSN, "m3004-p1", 1))
    assert isinstance(v1, FactsLedger)
    assert v1.version == 1 and v1.parent_version is None
    assert [f.fact_id for f in v1.facts] == ["f-1"]

    v2 = run(get_ledger(DSN, "m3004-p1", 2))
    assert v2.version == 2 and v2.parent_version == 1
    assert [f.fact_id for f in v2.facts] == ["f-1", "f-2"]
    assert v2.derivation_reason == "inject_evidence"


def test_unknown_version_raises_key_error() -> None:
    s = store()
    run(s.derive("m3004-p2", 0, "initial", {"add": []}))
    with pytest.raises(KeyError):
        run(get_ledger(DSN, "m3004-p2", 9))
    with pytest.raises(KeyError):
        run(get_ledger(DSN, "m3004-nope", 1))


def test_initial_from_zero_semantics() -> None:
    s = store()
    ledger = run(s.derive("m3004-p3", 0, "initial", {"add": []}))
    assert ledger.version == 1
    assert ledger.parent_version is None, "initial has no parent"
    loaded = run(get_ledger(DSN, "m3004-p3", 1))
    assert loaded.parent_version is None
    assert loaded.facts == []
