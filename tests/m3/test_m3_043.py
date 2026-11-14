"""M3-043 acceptance tests: inject_evidence full pipeline.

Acceptance (tasks.json M3-043):
  - origin=user_provided / access=private; parse -> dual-scale scoring ->
    alignment, no step exempted
  - never supports verdict A alone by default (optin goes to
    GenerationRecord)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any

import asyncpg
import pytest

from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import JSON, Principal, UserEvidence
from flint.intervene.inject import inject_evidence
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
                "(SELECT ledger_id FROM facts_ledgers WHERE project_id LIKE 'm3043-%')"
            )
            await conn.execute(
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3043-%'"
            )
        finally:
            await conn.close()

    run(wipe())


class MarkerAligner:
    def __init__(self, alignment: str) -> None:
        self.alignment = alignment
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls += 1
        return {"alignment": self.alignment}


def evidence() -> UserEvidence:
    return UserEvidence(
        evidence_id="ue-1", owner=Principal(kind="user", id="u-1"),
        kind="text", content_ref="内部实测：转化率 8%", note="来自本团队 AB 实验",
        created_at=NOW,
    )


def store() -> PgLedgerStore:
    ids = [0]

    def next_id() -> str:
        ids[0] += 1
        return f"led-m3043-{ids[0]:03d}"

    return PgLedgerStore(dsn=DSN, id_factory=next_id, now=lambda: NOW)


def scorer() -> DualScaleScorer:
    return DualScaleScorer(ScorerContext(today=date(2026, 7, 29)))


def test_full_pipeline_supports_path() -> None:
    s = store()
    run(s.derive("m3043-p1", 0, "initial", {"add": []}))
    provider = MarkerAligner("supports")
    result = run(inject_evidence(
        store=s, project_id="m3043-p1", ev=evidence(),
        scorer=scorer(),
        aligner=LLMCitationAligner(provider=provider),  # type: ignore[arg-type]
        claim_text="该方向转化率可达 8%",
        expected_version=1,
    ))
    assert result.doc.origin == "user_provided" and result.doc.access == "private"
    assert result.doc.source_id == "user_upload"
    assert result.score.axis == "user_provided", "dual-scale not exempted"
    assert provider.calls == 1, "alignment not exempted"
    assert result.alignment == "supports"
    assert result.ledger.version == 2
    assert result.ledger.derivation_reason == "inject_evidence"
    added = [f for f in result.ledger.facts if f.origin == "injected"]
    assert len(added) == 1
    assert result.optin_recorded is False, "default never supports A alone"


def test_unsupported_path_no_ledger_bump() -> None:
    s = store()
    run(s.derive("m3043-p2", 0, "initial", {"add": []}))
    result = run(inject_evidence(
        store=s, project_id="m3043-p2", ev=evidence(),
        scorer=scorer(),
        aligner=LLMCitationAligner(provider=MarkerAligner("unsupported")),  # type: ignore[arg-type]
        claim_text="该方向转化率可达 8%",
        expected_version=1,
    ))
    assert result.alignment == "unsupported"
    assert result.ledger.version == 1, "no fact, no version bump"
    assert result.fact_added is False


def test_partial_never_becomes_fact() -> None:
    s = store()
    run(s.derive("m3043-p3", 0, "initial", {"add": []}))
    result = run(inject_evidence(
        store=s, project_id="m3043-p3", ev=evidence(),
        scorer=scorer(),
        aligner=LLMCitationAligner(provider=MarkerAligner("partial")),  # type: ignore[arg-type]
        claim_text="x", expected_version=1,
    ))
    assert result.fact_added is False, "partial never promoted (S2-4)"


def test_optin_flag_passthrough_for_generation_record() -> None:
    s = store()
    run(s.derive("m3043-p4", 0, "initial", {"add": []}))
    result = run(inject_evidence(
        store=s, project_id="m3043-p4", ev=evidence(),
        scorer=scorer(),
        aligner=LLMCitationAligner(provider=MarkerAligner("supports")),  # type: ignore[arg-type]
        claim_text="x", expected_version=1, user_evidence_optin=True,
    ))
    assert result.optin_recorded is True, "explicit optin recorded for the record"
