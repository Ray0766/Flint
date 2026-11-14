"""M3-008 acceptance tests: blocks/deliverables migration + Block serialization.

Acceptance (tasks.json M3-008):
  - BlockContent discriminated union (review-16) round trips via JSONB
    losslessly
  - author-never-flips / locked / user_modified / needs_review field surface
    complete
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import asyncpg
import pytest

from flint.compose.block_io import block_content_from_json, block_content_to_json
from flint.domain.models import (
    Block,
    ChartContent,
    CitationListContent,
    ClaimSpan,
    DeclarationContent,
    FactCell,
    GapNoticeContent,
    HeadingContent,
    ParagraphContent,
    PriceCell,
    ProfileRef,
    QualityCardContent,
    TableContent,
    TextCell,
    TextSpan,
)

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)

CONTENTS = [
    HeadingContent(kind="heading", level=2, text="市场分析"),
    ParagraphContent(
        kind="paragraph",
        spans=[
            TextSpan(kind="text", text="需求增速 "),
            ClaimSpan(kind="claim", claim_id="c-1", text="30%", disputed_mark=True),
            ProfileRef(kind="profile", field_path="research.publications[2]"),
        ],
    ),
    TableContent(
        kind="table",
        header=["项目", "数值"],
        rows=[
            [TextCell(kind="text", text="服务器"),
             PriceCell(kind="price", price_entry_id="pe-1", quantity=2.0)],
            [TextCell(kind="text", text="规模"),
             FactCell(kind="fact", fact_id="f-1")],
        ],
    ),
    ChartContent(kind="chart", chart_id="ch-1"),
    DeclarationContent(kind="declaration", text="本报告基于公开信息自动生成"),
    QualityCardContent(kind="quality_card", card_ref="qc-1"),
    CitationListContent(kind="citation_list", citation_ids=["cit-1", "cit-2"]),
    GapNoticeContent(kind="gap_notice", hints_ref="ss-1"),
]


def test_all_eight_kinds_round_trip() -> None:
    for content in CONTENTS:
        payload = block_content_to_json(content)
        restored = block_content_from_json(payload)
        assert restored == content, content.kind
        assert type(restored) is type(content), "precise type recovered (review-16)"


def test_nested_union_precision() -> None:
    paragraph = block_content_from_json(block_content_to_json(CONTENTS[1]))
    assert isinstance(paragraph, ParagraphContent)
    assert type(paragraph.spans[1]) is ClaimSpan
    assert paragraph.spans[1].disputed_mark is True
    table = block_content_from_json(block_content_to_json(CONTENTS[2]))
    assert isinstance(table, TableContent)
    assert type(table.rows[0][1]) is PriceCell
    assert type(table.rows[1][1]) is FactCell


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValueError, match="kind"):
        block_content_from_json({"kind": "hologram"})
    with pytest.raises(ValueError, match="kind"):
        block_content_from_json(
            {"kind": "paragraph", "spans": [{"kind": "emoji", "text": "x"}]}
        )


def test_block_field_surface_complete() -> None:
    block = Block(
        block_id="b-1", deliverable_id="d-1", section_id="s-1", order=0,
        type="heading", content=CONTENTS[0], claim_ids=[], fact_ids=["f-1"],
        author="system", revision=1, locked=False,
    )
    assert block.user_modified is False
    assert block.needs_review is False
    assert block.review_reason is None and block.review_severity is None


@pytest.mark.compose
def test_migration_tables_and_author_check() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM blocks WHERE block_id LIKE 'm3008-%'")
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3008-%'"
            )
            tables = {
                r["table_name"]
                for r in await conn.fetch(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            }
            assert {"blocks", "deliverables"} <= tables

            await conn.execute(
                "INSERT INTO deliverables (deliverable_id, project_id, type, "
                "version, supersedes, inputs, ledger_version, generation_record_id, "
                "stale_reasons, created_at, reproducible) VALUES ('m3008-d1', 'p-1', "
                "'report', 1, NULL, '[]'::jsonb, NULL, 'gr-1', '[]'::jsonb, $1, true)",
                NOW,
            )
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO deliverables (deliverable_id, project_id, type, "
                    "version, supersedes, inputs, ledger_version, "
                    "generation_record_id, stale_reasons, created_at, reproducible) "
                    "VALUES ('m3008-d2', 'p-1', 'poem', 1, NULL, '[]'::jsonb, NULL, "
                    "'gr-1', '[]'::jsonb, $1, true)",
                    NOW,
                )
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "INSERT INTO blocks (block_id, deliverable_id, section_id, "
                    "block_order, type, content, claim_ids, fact_ids, author, "
                    "revision, locked, user_modified, needs_review, review_reason, "
                    "review_severity) VALUES ('m3008-b1', 'm3008-d1', 's-1', 0, "
                    "'heading', '{}'::jsonb, '[]'::jsonb, '[]'::jsonb, 'robot', 1, "
                    "false, false, false, NULL, NULL)",
                )
        finally:
            await conn.close()

    asyncio.run(scenario())
