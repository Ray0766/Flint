"""Feature B-1：DocStore——落 Doc(元信息) + Citation(quote_span, doc_id FK) 到 0006 表。

门 1=C 硬约束：Doc 只落元信息（无 content 字段/无全文）；证据正文只进 Citation.quote_span
短段。守 §3.5「采集层永不落原文正文」——本卡 verify 含 check_metadata_only 仍 0 违规断言。
"""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Citation, Doc
from flint.evidence.docstore import PgDocStore
from flint.sources.throttle import check_metadata_only

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _wipe() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM citations WHERE citation_id LIKE 'cit-b1%'")
            await conn.execute("DELETE FROM docs WHERE doc_id LIKE 'doc-b1%'")
        finally:
            await conn.close()
    run(wipe())
    yield
    run(wipe())


def _doc(doc_id: str) -> Doc:
    return Doc(
        doc_id=doc_id, source_id="github", kind="repo",
        title="acme/widget", url="https://github.com/acme/widget",
        published_at=date(2026, 7, 1),
        meta={"fetched_at": datetime(2026, 7, 26, tzinfo=UTC).isoformat()},
        origin="retrieved", access="public")


def test_doc_roundtrip_metadata_only() -> None:
    store = PgDocStore(DSN)
    d = _doc("doc-b1-round")
    run(store.save_doc(d))
    assert run(store.load_doc("doc-b1-round")) == d          # 元信息逐字保真


def test_citation_roundtrip_quote_span_fk() -> None:
    store = PgDocStore(DSN)
    run(store.save_doc(_doc("doc-b1-cit")))                   # FK 前置
    c = Citation(
        citation_id="cit-b1-1", doc_id="doc-b1-cit",
        locator=None, quote_span="一句被引的短证据段")
    run(store.save_citation(c))
    assert run(store.load_citation("cit-b1-1")) == c
    assert run(store.citations_for_doc("doc-b1-cit")) == [c]


def test_upsert_idempotent() -> None:
    store = PgDocStore(DSN)
    d = _doc("doc-b1-idem")
    run(store.save_doc(d))
    run(store.save_doc(d))                                    # 内容寻址幂等，不炸
    assert run(store.load_doc("doc-b1-idem")) == d


def test_compliance_no_fulltext_column_introduced() -> None:
    # §3.5 守卫：DocStore 落库后，全库仍无全文正文列（Doc 无 content 字段）
    assert run(check_metadata_only(DSN)) == []
