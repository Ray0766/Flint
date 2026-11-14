"""M3-048 acceptance tests: interventions API (four actions).

Acceptance (tasks.json M3-048):
  - lock/regenerate/inject/dispute endpoints + review-6 permissions
  - machine-readable error codes (LEDGER_CONFLICT family) and idempotency
    surface reuse from M2-042
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest

from flint.align.stage1 import LLMCitationAligner
from flint.api.interventions import InterventionApiDeps, create_interventions_app
from flint.compose.blocks import PgBlockStore
from flint.domain.models import JSON, Block, HeadingContent, Principal
from flint.intervene.edits import PgEditService
from flint.jobs.runner import PgJobRunner
from flint.ledger.store import PgLedgerStore
from flint.scoring.scorer import DualScaleScorer, ScorerContext

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)

ROLES = {("u-admin", "org-1"): "admin", ("u-member", "org-1"): "member"}


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for sql in (
                "DELETE FROM edit_events WHERE deliverable_id LIKE 'm3048-%'",
                "DELETE FROM blocks WHERE deliverable_id LIKE 'm3048-%'",
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3048-%'",
                (
                    "DELETE FROM facts WHERE ledger_id IN (SELECT ledger_id "
                    "FROM facts_ledgers WHERE project_id LIKE 'm3048-%')"
                ),
                "DELETE FROM facts_ledgers WHERE project_id LIKE 'm3048-%'",
                "DELETE FROM jobs WHERE job_id LIKE 'm3048-%'",
            ):
                await conn.execute(sql)
            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, "
                "version, supersedes, inputs, ledger_version, generation_record_id, "
                "stale_reasons, created_at, reproducible) VALUES ('m3048-d1', "
                "'m3048-p1', 'report', 1, NULL, '[]'::jsonb, NULL, 'gr-1', "
                "'[]'::jsonb, $1, true)",
                NOW,
            )
        finally:
            await conn.close()

    run(wipe())


class SupportsProvider:
    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        return {"alignment": "supports"}


def make_app() -> Any:
    ids = [0]

    def next_led() -> str:
        ids[0] += 1
        return f"led-m3048-{ids[0]:03d}"

    deps = InterventionApiDeps(
        dsn=DSN,
        runner=PgJobRunner(
            dsn=DSN,
            role_resolver=lambda user, org: ROLES.get((user, org)),
            id_factory=lambda: f"m3048-{uuid4().hex[:10]}",
        ),
        role_resolver=lambda user, org: ROLES.get((user, org)),
        owner_scope_for_project=lambda pid: Principal(kind="org", id="org-1"),
        ledger_store=PgLedgerStore(dsn=DSN, id_factory=next_led, now=lambda: NOW),
        scorer=DualScaleScorer(ScorerContext(today=NOW.date())),
        aligner=LLMCitationAligner(provider=SupportsProvider()),  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    return create_interventions_app(deps)


async def _client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


def seed_block() -> None:
    run(PgBlockStore(dsn=DSN).save_tree("m3048-d1", [
        Block(
            block_id="m3048-b1", deliverable_id="m3048-d1", section_id="s-1",
            order=0, type="heading",
            content=HeadingContent(kind="heading", level=1, text="t"),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        )
    ]))


def test_lock_endpoint_locks_and_records_edit_event() -> None:
    seed_block()
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            response = await client.post(
                "/interventions/lock",
                json={"target_id": "m3048-b1", "scope": "block",
                      "deliverable_id": "m3048-d1", "project_id": "m3048-p1"},
                headers={"X-User-Id": "u-admin"},
            )
            assert response.status_code == 204, response.text
        tree = await PgBlockStore(dsn=DSN).load_tree("m3048-d1")
        assert tree[0].locked is True
        events = await PgEditService(dsn=DSN).events_for("m3048-d1")
        assert [e.action for e in events] == ["lock"]

    run(scenario())


def test_permission_matrix_denies_member_and_outsider() -> None:
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            for user in ("u-member", "u-outsider"):
                response = await client.post(
                    "/interventions/lock",
                    json={"target_id": "x", "scope": "block",
                          "deliverable_id": "m3048-d1", "project_id": "m3048-p1"},
                    headers={"X-User-Id": user},
                )
                assert response.status_code == 403, user
                assert response.json()["code"] == "PERMISSION_DENIED"

    run(scenario())


def test_regenerate_submits_job() -> None:
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            response = await client.post(
                "/deliverables/m3048-d1/sections/s-1/regenerate",
                params={"project_id": "m3048-p1"},
                headers={"X-User-Id": "u-admin"},
            )
            assert response.status_code == 200, response.text
            job_id = response.json()["job_id"]
            assert job_id.startswith("m3048-")
        conn = await asyncpg.connect(DSN)
        try:
            kind = await conn.fetchval(
                "SELECT kind FROM jobs WHERE job_id = $1", job_id
            )
        finally:
            await conn.close()
        assert kind == "report"

    run(scenario())


def test_inject_endpoint_full_pipeline_with_optin() -> None:
    app = make_app()
    store = PgLedgerStore(dsn=DSN, id_factory=lambda: f"led-m3048-seed-{uuid4().hex[:6]}")
    run(store.derive("m3048-p1", 0, "initial", {"add": []}))

    async def scenario() -> None:
        async with await _client(app) as client:
            response = await client.post(
                "/projects/m3048-p1/evidence",
                json={"evidence_kind": "text", "content_ref": "内部实测 8%",
                      "claim_text": "转化率可达 8%", "expected_version": 1,
                      "user_evidence_optin": True},
                headers={"X-User-Id": "u-admin"},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["alignment"] == "supports"
            assert body["fact_added"] is True
            assert body["ledger_version"] == 2
            assert body["score_axis"] == "user_provided"
            assert body["user_evidence_verdict_optin"] is True

    run(scenario())


def test_dispute_conflict_409_then_confirmed_resubmit() -> None:
    app = make_app()
    store = PgLedgerStore(dsn=DSN, id_factory=lambda: f"led-m3048-x-{uuid4().hex[:6]}")
    run(store.derive("m3048-p1", 0, "initial", {"add": [{
        "fact_id": "f-1", "statement": "s", "value": None, "unit": None,
        "citation_ids": [], "status": "frozen", "origin": "injected",
        "created_in_version": 0, "source_claim_id": None, "promoted_from": None,
    }]}))
    run(store.derive("m3048-p1", 1, "inject_evidence", {"add": []}))  # 前进到 v2

    async def scenario() -> None:
        async with await _client(app) as client:
            stale = await client.post(
                "/projects/m3048-p1/disputes",
                json={"dispute_id": "dsp-1", "deliverable_id": "m3048-d1",
                      "target_kind": "fact", "target_id": "f-1",
                      "reason_text": "数字存疑", "expected_version": 1},
                headers={"X-User-Id": "u-admin"},
            )
            assert stale.status_code == 409
            body = stale.json()
            assert body["code"] == "LEDGER_CONFLICT"
            assert body["detail"]["current_version"] == 2

            confirmed = await client.post(
                "/projects/m3048-p1/disputes",
                json={"dispute_id": "dsp-1", "deliverable_id": "m3048-d1",
                      "target_kind": "fact", "target_id": "f-1",
                      "reason_text": "数字存疑", "expected_version": 1,
                      "confirmed_version": 2},
                headers={"X-User-Id": "u-admin"},
            )
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["ledger_version"] == 3
        events = await PgEditService(dsn=DSN).events_for("m3048-d1")
        assert [e.action for e in events] == ["dispute"]

    run(scenario())


def test_regenerate_block_with_guidance_flows_into_payload() -> None:
    """FE-CORE-007 chain: body {block_id, guidance} → Job payload
    (action=regenerate_block + block_id + guidance) for the worker (FE-CORE-005)."""
    captured: list[dict[str, Any]] = []

    async def capture(job_id: str, kind: str, payload: dict[str, Any]) -> None:
        captured.append(payload)

    deps = InterventionApiDeps(
        dsn=DSN,
        runner=PgJobRunner(
            dsn=DSN, role_resolver=lambda u, o: ROLES.get((u, o)),
            id_factory=lambda: f"m3048-{uuid4().hex[:10]}", enqueue=capture,
        ),
        role_resolver=lambda u, o: ROLES.get((u, o)),
        owner_scope_for_project=lambda pid: Principal(kind="org", id="org-1"),
        ledger_store=PgLedgerStore(dsn=DSN, id_factory=lambda: f"led-g{uuid4().hex[:6]}",
                                   now=lambda: NOW),
        scorer=DualScaleScorer(ScorerContext(today=NOW.date())),
        aligner=LLMCitationAligner(provider=SupportsProvider()),  # type: ignore[arg-type]
        now=lambda: NOW,
    )
    app = create_interventions_app(deps)

    async def scenario() -> None:
        async with await _client(app) as client:
            resp = await client.post(
                "/deliverables/m3048-d1/sections/s-1/regenerate",
                params={"project_id": "m3048-p1"},
                headers={"X-User-Id": "u-admin"},
                json={"block_id": "b2", "guidance": "更简洁一点"},
            )
            assert resp.status_code == 200, resp.text

    run(scenario())
    assert captured, "enqueue hook not called"
    assert captured[0]["action"] == "regenerate_block"
    assert captured[0]["block_id"] == "b2"
    assert captured[0]["guidance"] == "更简洁一点"
