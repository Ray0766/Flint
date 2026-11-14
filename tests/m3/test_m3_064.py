"""M3-064 acceptance tests: invariants bundle.

Acceptance (tasks.json M3-064):
  - E9-named trio + channel enforcer bundled behind one command
  - any broken invariant -> exit 1 with the breakage identified
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from itertools import product
from typing import Any

import asyncpg
import pytest

from eval.invariants import INVARIANT_NODES, main
from flint.compose.blocks import (
    PROTECTED_SQL_PREDICATE,
    PgBlockStore,
    is_protected,
)
from flint.domain.models import Block, HeadingContent

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_bundle_covers_named_invariants() -> None:
    joined = " ".join(INVARIANT_NODES)
    assert "test_partial_never_promoted" in joined
    assert "test_protected_block_never_rewritten" in joined
    assert "test_verdict_shift_requires_rerun" in joined
    assert "test_m3_016.py" in joined, "channel enforcer full file"
    assert "test_protection_predicate_python_sql_equivalence" in joined


@pytest.mark.compose
def test_protection_predicate_python_sql_equivalence() -> None:
    """M3-013 复审 MAY 兑现：2^3 组合在真库比对 Python/SQL 两面谓词。"""

    async def scenario() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM blocks WHERE deliverable_id = 'm3064-d1'"
            )
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id = 'm3064-d1'"
            )
            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, "
                "version, supersedes, inputs, ledger_version, "
                "generation_record_id, stale_reasons, created_at, reproducible) "
                "VALUES ('m3064-d1', 'p-1', 'report', 1, NULL, '[]'::jsonb, "
                "NULL, 'gr-1', '[]'::jsonb, $1, true)",
                NOW,
            )
        finally:
            await conn.close()

        blocks = []
        for index, (locked, user_author, modified) in enumerate(
            product([False, True], repeat=3)
        ):
            blocks.append(Block(
                block_id=f"m3064-b{index}", deliverable_id="m3064-d1",
                section_id="s-1", order=index, type="heading",
                content=HeadingContent(kind="heading", level=1, text="t"),
                claim_ids=[], fact_ids=[],
                author="user" if user_author else "system",
                revision=1, locked=locked, user_modified=modified,
            ))
        await PgBlockStore(dsn=DSN).save_tree("m3064-d1", blocks)

        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT block_id FROM blocks WHERE deliverable_id = 'm3064-d1' "
                f"AND {PROTECTED_SQL_PREDICATE} ORDER BY block_id"
            )
        finally:
            await conn.close()
        sql_protected = {r["block_id"] for r in rows}
        python_protected = {b.block_id for b in blocks if is_protected(b)}
        assert sql_protected == python_protected, "two faces, one predicate"
        assert len(python_protected) == 7, "only the all-False combo unprotected"

    run(scenario())


@pytest.mark.compose
def test_bundle_green_and_breakage_identified() -> None:
    assert main() == 0, "all invariants green behind one command"
    assert main(["tests/m3/no_such_file.py"]) != 0, (
        "broken selector surfaces as nonzero (identification via pytest node)"
    )
