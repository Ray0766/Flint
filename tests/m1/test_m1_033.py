"""M1-033 acceptance tests: minimal JobRunner (state machine + permissions).

Acceptance (tasks.json M1-033):
  - submit / get / cancel work end to end
  - unauthorized cancel is rejected (review-6 cases)
  - illegal state transitions raise
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Job, Principal
from flint.jobs.runner import IllegalTransition, PgJobRunner

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 23, 9, 0, 0, tzinfo=UTC)

ORG_SCOPE = Principal(kind="org", id="org-1")
ROLES = {
    ("u-owner", "org-1"): "owner",
    ("u-admin", "org-1"): "admin",
    ("u-member", "org-1"): "member",
    ("u-viewer", "org-1"): "viewer",
}


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def make_runner() -> PgJobRunner:
    counter = [0]

    def next_id() -> str:
        counter[0] += 1
        return f"m1033-job-{counter[0]}"

    return PgJobRunner(
        dsn=DSN,
        role_resolver=lambda user_id, org_id: ROLES.get((user_id, org_id)),
        id_factory=next_id,
        now=lambda: NOW,
    )


@pytest.fixture(autouse=True)
def clean_jobs() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'm1033-%'")
            await conn.execute("DELETE FROM job_steps WHERE job_id LIKE 'm1033-%'")
            await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'm1033-%'")
        finally:
            await conn.close()

    run(wipe())


def submit(runner: PgJobRunner, initiated_by: str = "u-member") -> str:
    return run(
        runner.submit(
            kind="daily_ingest",
            payload={"day": "2026-07-23"},
            budget=10.0,
            owner_scope=ORG_SCOPE,
            initiated_by=initiated_by,
        )
    )


def test_submit_then_get_roundtrip() -> None:
    runner = make_runner()
    job_id = submit(runner)
    job = run(runner.get(job_id))
    assert isinstance(job, Job)
    assert job.job_id == job_id
    assert job.kind == "daily_ingest"
    assert job.state == "queued"
    assert job.owner_scope == ORG_SCOPE
    assert job.initiated_by == "u-member"
    assert job.budget == 10.0
    assert job.cancel_requested is False


def test_cancel_by_initiator_allowed() -> None:
    runner = make_runner()
    job_id = submit(runner, initiated_by="u-member")
    run(runner.cancel(job_id, actor_user_id="u-member"))
    job = run(runner.get(job_id))
    assert job.cancel_requested is True
    assert job.state == "cancelled", "queued job cancels at the immediate boundary"


@pytest.mark.parametrize("actor", ["u-owner", "u-admin"])
def test_cancel_by_org_owner_or_admin_allowed(actor: str) -> None:
    runner = make_runner()
    job_id = submit(runner, initiated_by="u-member")
    run(runner.cancel(job_id, actor_user_id=actor))
    assert run(runner.get(job_id)).cancel_requested is True


@pytest.mark.parametrize("actor", ["u-viewer", "u-stranger"])
def test_cancel_unauthorized_rejected(actor: str) -> None:
    """Review-6: cancel right = initiator, or owner/admin inside owner_scope.
    member (non-initiator), viewer and strangers are all rejected."""
    runner = make_runner()
    job_id = submit(runner, initiated_by="u-owner")
    with pytest.raises(PermissionError):
        run(runner.cancel(job_id, actor_user_id=actor))
    job = run(runner.get(job_id))
    assert job.cancel_requested is False
    assert job.state == "queued"


def test_cancel_by_non_initiator_member_rejected() -> None:
    runner = make_runner()
    job_id = submit(runner, initiated_by="u-owner")
    with pytest.raises(PermissionError):
        run(runner.cancel(job_id, actor_user_id="u-member"))


def test_legal_forward_path_to_done() -> None:
    runner = make_runner()
    job_id = submit(runner)
    for state in ["retrieving", "judging", "drafting", "validating", "done"]:
        run(runner.advance(job_id, state))
    assert run(runner.get(job_id)).state == "done"


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        (["retrieving", "judging"], "retrieving"),   # backward
        (["retrieving"], "queued"),                  # backward to start
        (["retrieving", "judging", "drafting", "validating", "done"], "queued"),  # from terminal
    ],
)
def test_illegal_transitions_raise(path: list[str], bad: str) -> None:
    runner = make_runner()
    job_id = submit(runner)
    for state in path:
        run(runner.advance(job_id, state))
    with pytest.raises(IllegalTransition):
        run(runner.advance(job_id, bad))


def test_cancel_takes_effect_at_stage_boundary() -> None:
    """Review-6/D8: cancel_requested flips immediately; the running stage
    finishes and the NEXT boundary lands in cancelled instead."""
    runner = make_runner()
    job_id = submit(runner)
    run(runner.advance(job_id, "retrieving"))
    run(runner.cancel(job_id, actor_user_id="u-admin"))
    job = run(runner.get(job_id))
    assert job.state == "retrieving", "running stage is not interrupted mid-flight"
    run(runner.advance(job_id, "judging"))  # boundary honours the pending cancel
    assert run(runner.get(job_id)).state == "cancelled"


def test_unknown_job_raises() -> None:
    runner = make_runner()
    with pytest.raises(KeyError):
        run(runner.get("m1033-ghost"))
