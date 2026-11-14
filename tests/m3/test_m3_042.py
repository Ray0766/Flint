"""M3-042 acceptance tests: regenerate_section under protection.

Acceptance (tasks.json M3-042):
  - only unprotected blocks touched; protected kept verbatim (S2-5
    re-verified on the intervention path)
  - new GenerationRecord + Deliverable version+1; job_id returned
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest

from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.compose.protect import ProtectedBlockViolation
from flint.domain.models import (
    Block,
    Deliverable,
    GenerationRecord,
    ParagraphContent,
    TextSpan,
)
from flint.intervene.regenerate import PgRegenerateService

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
            await conn.execute("DELETE FROM blocks WHERE deliverable_id LIKE 'm3042-%'")
            await conn.execute(
                "DELETE FROM generation_records WHERE record_id LIKE 'm3042-%'"
            )
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3042-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def para(block_id: str, text: str, section: str, order: int,
         deliverable_id: str = "m3042-d1", **flags: Any) -> Block:
    return Block(
        block_id=block_id, deliverable_id=deliverable_id, section_id=section,
        order=order, type="paragraph",
        content=ParagraphContent(kind="paragraph",
                                 spans=[TextSpan(kind="text", text=text)]),
        claim_ids=[], fact_ids=[], author=flags.pop("author", "system"),
        revision=1, locked=flags.pop("locked", False),
        user_modified=flags.pop("user_modified", False),
    )


def record(record_id: str, deliverable_id: str) -> GenerationRecord:
    return GenerationRecord(
        record_id=record_id, deliverable_id=deliverable_id, job_id="j-regen",
        prompt_version="v1", model="m", params={}, retrieval_snapshot_id="s-1",
        ledger_version=1, pricebook_version=None,
        user_evidence_verdict_optin=False, ts=NOW, cost=0.1,
    )


def seed() -> None:
    dstore = PgDeliverableStore(dsn=DSN)
    run(dstore.save_generation_record(record("m3042-r1", "m3042-d1")))
    run(dstore.save_deliverable(Deliverable(
        deliverable_id="m3042-d1", project_id="p-1", type="report", version=1,
        supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="m3042-r1", stale_reasons=[], created_at=NOW,
    )))
    bstore = PgBlockStore(dsn=DSN)
    run(bstore.save_tree("m3042-d1", [
        para("m3042-b1", "用户锁定段", "s-1", 0, locked=True),
        para("m3042-b2", "旧生成段", "s-1", 1),
        para("m3042-b3", "别节内容", "s-2", 0),
    ]))


def service() -> PgRegenerateService:
    return PgRegenerateService(dsn=DSN, now=lambda: NOW)


def test_regenerate_replaces_unprotected_only_and_versions() -> None:
    seed()
    job_id = run(service().regenerate_section(
        deliverable_id="m3042-d1", section_id="s-1",
        generator=lambda pool: [
            para("m3042-b2n", "新生成段", "s-1", 9, deliverable_id="m3042-d2")
        ],
        new_deliverable_id="m3042-d2",
        generation_record=record("m3042-r2", "m3042-d2"),
        job_id="job-regen-1",
    ))
    assert job_id == "job-regen-1"

    dstore = PgDeliverableStore(dsn=DSN)
    v2 = run(dstore.load_deliverable("m3042-d2"))
    assert v2.version == 2 and v2.supersedes == "m3042-d1"
    assert v2.generation_record_id == "m3042-r2"
    assert run(dstore.load_generation_record("m3042-r2")).job_id == "j-regen"

    new_tree = run(PgBlockStore(dsn=DSN).load_tree("m3042-d2"))
    by_id = {b.block_id: b for b in new_tree}
    assert "m3042-b1" in by_id, "protected block carried over"
    assert by_id["m3042-b1"].content == ParagraphContent(
        kind="paragraph", spans=[TextSpan(kind="text", text="用户锁定段")]
    )
    assert "m3042-b2" not in by_id and "m3042-b2n" in by_id, "unprotected replaced"
    assert "m3042-b3" in by_id, "other sections copied along"

    old_tree = run(PgBlockStore(dsn=DSN).load_tree("m3042-d1"))
    assert len(old_tree) == 3, "old version tree intact"


def test_generator_touching_protected_rejected_no_write() -> None:
    seed()
    with pytest.raises(ProtectedBlockViolation):
        run(service().regenerate_section(
            deliverable_id="m3042-d1", section_id="s-1",
            generator=lambda pool: [
                para("m3042-b1", "篡改锁定段", "s-1", 0,
                     deliverable_id="m3042-d2", locked=True)
            ],
            new_deliverable_id="m3042-d2",
            generation_record=record("m3042-r3", "m3042-d2"),
            job_id="job-regen-2",
        ))
    with pytest.raises(KeyError):
        run(PgDeliverableStore(dsn=DSN).load_deliverable("m3042-d2"))
    assert run(PgBlockStore(dsn=DSN).load_tree("m3042-d2")) == [], "no half-write"
