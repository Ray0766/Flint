"""M3-044 acceptance tests: inject conflict auto-replay <=3.

Acceptance (tasks.json M3-044):
  - LedgerVersionConflict -> auto-replay <=3 (audit 4); 4th attempt never
    happens blindly, conflict re-raised
  - replay lands semantically equivalent on the new version
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import JSON, LedgerVersionConflict, Principal, UserEvidence
from flint.intervene.inject_retry import inject_with_replay
from flint.ledger.store import PgLedgerStore
from flint.scoring.scorer import DualScaleScorer, ScorerContext

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
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3044-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3044-%'"
            )
        finally:
            await conn.close()

    run(wipe())


class SupportsProvider:
    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        return {"alignment": "supports"}


def deps() -> dict[str, Any]:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3044-{ids[0]:03d}"

    return {
        "store": PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW),
        "scorer": DualScaleScorer(ScorerContext(today=NOW.date())),
        "aligner": LLMCitationAligner(provider=SupportsProvider()),  # type: ignore[arg-type]
        "ev": UserEvidence(
            evidence_id="ue-1", owner=Principal(kind="user", id="u-1"),
            kind="text", content_ref="内部实测", note="", created_at=NOW,
        ),
    }


def test_replay_wins_after_concurrent_bump() -> None:
    d = deps()
    store: PgLedgerStore = d["store"]
    run(store.derive("m3044-p1", 0, "initial", {"add": []}))

    calls = {"n": 0}
    original_derive = store.derive

    async def racing_derive(*args: Any, **kwargs: Any) -> Any:
        # 首次尝试前插入一次并发派生：制造真实版本冲突
        if calls["n"] == 0:
            calls["n"] += 1
            await original_derive(
                "m3044-p1", 1, "inject_evidence", {"add": []}
            )
        return await original_derive(*args, **kwargs)

    store.derive = racing_derive  # type: ignore[method-assign]
    result = run(inject_with_replay(
        store=store, project_id="m3044-p1", ev=d["ev"], scorer=d["scorer"],
        aligner=d["aligner"], claim_text="x", initial_expected_version=1,
    ))
    assert result.result.ledger.version == 3, "replayed on the new version"
    assert result.attempts == 2, "one conflict, one successful replay"
    assert result.result.fact_added is True


def test_persistent_conflict_gives_up_after_three_replays() -> None:
    d = deps()
    store: PgLedgerStore = d["store"]
    run(store.derive("m3044-p2", 0, "initial", {"add": []}))

    attempts = {"n": 0}

    async def always_conflict(*args: Any, **kwargs: Any) -> Any:
        attempts["n"] += 1
        raise_conflict = LedgerVersionConflict
        err = raise_conflict.__new__(raise_conflict)
        Exception.__init__(err, "forced conflict")
        err.current_version = 99  # type: ignore[attr-defined]
        err.current_facts = []  # type: ignore[attr-defined]
        raise err

    store.derive = always_conflict  # type: ignore[method-assign]
    with pytest.raises(LedgerVersionConflict):
        run(inject_with_replay(
            store=store, project_id="m3044-p2", ev=d["ev"], scorer=d["scorer"],
            aligner=d["aligner"], claim_text="x", initial_expected_version=1,
        ))
    assert attempts["n"] == 4, "1 initial + 3 replays, never a fifth"
