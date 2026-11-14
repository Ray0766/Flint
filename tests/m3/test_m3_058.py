"""M3-058 acceptance tests: deliverable read + render endpoints.

Acceptance (tasks.json M3-058):
  - GET /deliverables/{id} + /render?fmt= four formats + fmt=pack slot
  - gate refusal surfaces EXPORT_BLOCKED error body (audit 11 via API)
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import httpx
import pytest

from flint.api.deliverables import DeliverableApiDeps, create_deliverables_app
from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import (
    Block,
    ClaimSpan,
    DeclarationContent,
    Deliverable,
    HeadingContent,
    ParagraphContent,
    TableContent,
    TextCell,
    TextSpan,
)

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
            await conn.execute("DELETE FROM blocks WHERE deliverable_id LIKE 'm3058-%'")
            await conn.execute(
                "DELETE FROM deliverables WHERE deliverable_id LIKE 'm3058-%'"
            )
        finally:
            await conn.close()

    run(wipe())


def seed(blocking: bool = False) -> None:
    dstore = PgDeliverableStore(dsn=DSN)
    run(dstore.save_deliverable(Deliverable(
        deliverable_id="m3058-d1", project_id="p-1", type="report", version=1,
        supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="gr-1", stale_reasons=[], created_at=NOW,
    )))
    block = Block(
        block_id="m3058-b1", deliverable_id="m3058-d1", section_id="s-1",
        order=0, type="heading",
        content=HeadingContent(kind="heading", level=1, text="标题"),
        claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        needs_review=blocking,
        review_reason="fact_removed" if blocking else None,
        review_severity="blocking" if blocking else None,
    )
    run(PgBlockStore(dsn=DSN).save_tree("m3058-d1", [block]))


def make_app() -> Any:
    return create_deliverables_app(DeliverableApiDeps(dsn=DSN))


async def _client(app: Any) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    )


def test_read_and_three_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    # 「引擎不可用 → 503」这一支在哪台机器上都要量得到：原先靠的是 Windows 上
    # weasyprint 恰好导不进来（Q-003），换到装了 pango 的机器这条断言就失去了前提。
    monkeypatch.setattr("flint.api.deliverables._pdf_available", lambda: False)
    seed()
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            meta = await client.get("/deliverables/m3058-d1")
            assert meta.status_code == 200
            assert meta.json()["version"] == 1

            md = await client.get("/deliverables/m3058-d1/render",
                                  params={"fmt": "markdown"})
            assert md.status_code == 200 and "# 标题" in md.text

            html = await client.get("/deliverables/m3058-d1/render",
                                    params={"fmt": "html"})
            assert html.status_code == 200 and "<h1>标题</h1>" in html.text

            docx = await client.get("/deliverables/m3058-d1/render",
                                    params={"fmt": "docx"})
            assert docx.status_code == 200
            assert docx.content[:2] == b"PK"

            pdf = await client.get("/deliverables/m3058-d1/render",
                                   params={"fmt": "pdf"})
            assert pdf.status_code == 503, "pdf engine unavailable (Q-003) -> 503"
            assert pdf.json()["code"] == "SERVICE_UNAVAILABLE"

    run(scenario())


def _engine_importable() -> bool:
    import importlib

    try:
        importlib.import_module("weasyprint")
    except (OSError, ImportError):
        return False
    return True


def test_pdf_is_served_when_the_engine_is_there() -> None:
    """另一支：引擎在的机器上，同一个端点回的是一份真 PDF，不是 503。

    引擎不在就 skip 并说清楚——**NEVER 当它通过**。
    """
    if not _engine_importable():
        pytest.skip("本机 weasyprint 导不进来（Q-003：缺 GTK/pango 运行库），这一支量不了")
    seed()
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            pdf = await client.get("/deliverables/m3058-d1/render",
                                   params={"fmt": "pdf"})
            assert pdf.status_code == 200, pdf.text[:300]
            assert pdf.content[:5] == b"%PDF-"

    run(scenario())


def test_export_blocked_error_body() -> None:
    seed(blocking=True)
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            response = await client.get(
                "/deliverables/m3058-d1/render", params={"fmt": "markdown"}
            )
            assert response.status_code == 409
            body = response.json()
            assert body["code"] == "EXPORT_BLOCKED"
            assert body["detail"]["blocking_block_ids"] == ["m3058-b1"]

    run(scenario())


def test_unknown_deliverable_and_bad_fmt() -> None:
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            missing = await client.get("/deliverables/nope/render",
                                       params={"fmt": "markdown"})
            assert missing.status_code == 404
            assert missing.json()["code"] == "NOT_FOUND"

            bad = await client.get("/deliverables/nope/render",
                                   params={"fmt": "tarot"})
            assert bad.status_code == 422

    run(scenario())


# ── FE-000: 结构化 Block 树 JSON 读端点（L0 只读渲染器读契约）──────────────
# 前端 L0 需要**结构化** Block 树 JSON（而非 /render 的已渲染 markdown/html），
# 才能逐块原生只读渲染（8 类 BlockType 各自组件 + 保护标志）。此端点是 L0 的
# 输入契约；后端/Python 面、node 无关、可离线（本地 PG）验收。


def seed_multitype_tree() -> None:
    dstore = PgDeliverableStore(dsn=DSN)
    run(dstore.save_deliverable(Deliverable(
        deliverable_id="m3058-blk", project_id="p-1", type="report", version=1,
        supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="gr-1", stale_reasons=[], created_at=NOW,
    )))

    def blk(bid: str, order: int, btype: str, content: object,
            *, locked: bool = False, author: str = "system") -> Block:
        return Block(
            block_id=bid, deliverable_id="m3058-blk", section_id="s-1",
            order=order, type=btype, content=content,  # type: ignore[arg-type]
            claim_ids=[], fact_ids=[], author=author,  # type: ignore[arg-type]
            revision=1, locked=locked,
        )

    tree = [
        blk("blk-h", 0, "heading",
            HeadingContent(kind="heading", level=1, text="标题")),
        blk("blk-p", 1, "paragraph", ParagraphContent(
            kind="paragraph",
            spans=[TextSpan(kind="text", text="正文"),
                   ClaimSpan(kind="claim", claim_id="c1", text="断言")])),
        blk("blk-d", 2, "declaration",
            DeclarationContent(kind="declaration", text="边界声明"),
            locked=True),
        blk("blk-t", 3, "table", TableContent(
            kind="table", header=["列A"],
            rows=[[TextCell(kind="text", text="格1")]])),
    ]
    run(PgBlockStore(dsn=DSN).save_tree("m3058-blk", tree))


def test_blocks_endpoint_returns_structured_tree() -> None:
    """L0 读契约：GET /deliverables/{id}/blocks 回结构化 Block 树 JSON——
    稳定序 + 全字段 + content 判别联合（kind）+ 保护标志。"""
    seed_multitype_tree()
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            resp = await client.get("/deliverables/m3058-blk/blocks")
            assert resp.status_code == 200
            body = resp.json()
            assert body["deliverable_id"] == "m3058-blk"
            blocks = body["blocks"]
            assert len(blocks) == 4
            # 稳定序（section_id, order）
            assert [b["order"] for b in blocks] == [0, 1, 2, 3]
            assert [b["type"] for b in blocks] == [
                "heading", "paragraph", "declaration", "table"
            ]
            # 全字段在场（L0 渲染 + 保护判定所需）
            for key in ("block_id", "deliverable_id", "section_id", "order",
                        "type", "content", "claim_ids", "fact_ids", "author",
                        "revision", "locked", "user_modified", "needs_review"):
                assert key in blocks[0], f"missing block field: {key}"
            # content 判别联合的 kind 判别字段随类型
            assert blocks[0]["content"]["kind"] == "heading"
            assert blocks[0]["content"]["text"] == "标题"
            assert blocks[1]["content"]["spans"][0]["kind"] == "text"
            assert blocks[1]["content"]["spans"][1]["kind"] == "claim"
            assert blocks[1]["content"]["spans"][1]["claim_id"] == "c1"
            assert blocks[3]["content"]["header"] == ["列A"]
            assert blocks[3]["content"]["rows"][0][0]["kind"] == "text"
            # 保护标志：declaration 系统块 locked=True/author=system
            assert blocks[2]["locked"] is True
            assert blocks[2]["author"] == "system"
            assert blocks[2]["user_modified"] is False

    run(scenario())


def test_blocks_endpoint_unknown_deliverable_404() -> None:
    app = make_app()

    async def scenario() -> None:
        async with await _client(app) as client:
            missing = await client.get("/deliverables/nope/blocks")
            assert missing.status_code == 404
            assert missing.json()["code"] == "NOT_FOUND"

    run(scenario())
