"""FB-06：解引用端点③ `GET /citations/{id}` —— citation_id → 可点的引文短段。

## 本卡只取，不产

`quote_span` 是 Gate① 生产链已经钉好并落库的东西（`flint/evidence/`）。本卡**只把它取出来**，
NEVER 在读取面重新抽一段——重抽的那段和当初钉住的那段迟早不是同一段，
而报告正文里那条引用指的是当初那一段。

## 失锚照实返回，仍然可见

`quote_span IS NULL` = **失锚**：这条引用还指着一篇文献，但没有钉住具体段落。
照实标 `anchored: false` 并**照常返回**文献链接——
**NEVER 因为失锚就把整条引用藏起来**：藏起来之后，正文里那句结论看上去就是没有出处的，
而它其实有出处，只是段落丢了。这两件事对读者的意义完全不同。

## `access="private"` 的既有纪律（冻结件 `Doc` docstring 逐字）

「access="private"(用户材料): 产品内可点开原文段落; 导出/分享强制标注
『引自用户提供材料, 外部不可核验』, 链接不外链 [审5]」。

本端点是**产品内的读取面**，所以段落照给；但响应必须把 `access` 与
「能不能外链 / 该标什么」一并交出去，让下游的导出与分享**有东西可依据**——
下游猜不出来的规则等于没有规则。

## 多租户：`citations` 与 `docs` 都**没有归属列**（第 3 次同类收窄，见 trace §3）
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.deref import DerefApiDeps, create_deref_app

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "fb06-"
USER = "fb06-user"

ANCHORED = f"{PREFIX}cit-anchored"
LOST = f"{PREFIX}cit-lost"
PRIVATE = f"{PREFIX}cit-private"
QUOTE = "检索增强生成在企业知识库场景已有落地，中试证据可复现。"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _frozen_share_note() -> str:
    """从冻结件 `Doc` 的 docstring 里取那句强制标注文案。

    测试与实现各自从**同一个源头**取，而不是彼此对着抄——抄的那份和源头迟早不一致。
    """
    import inspect

    from contracts.models import Doc

    doc = inspect.getdoc(Doc) or ""
    return doc[doc.find("「") + 1:doc.find("」")]


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(f"DELETE FROM citations WHERE citation_id LIKE '{PREFIX}%'")
            await conn.execute(f"DELETE FROM docs WHERE doc_id LIKE '{PREFIX}%'")
            await conn.executemany(
                "INSERT INTO docs (doc_id, source_id, kind, title, url, published_at, "
                "meta, origin, access) VALUES ($1, $2, $3, $4, $5, $6, '{}'::jsonb, $7, $8)",
                [
                    (f"{PREFIX}doc-pub", "arxiv", "paper", "RAG in production",
                     "https://example.invalid/2506.06962", date(2026, 6, 20),
                     "retrieved", "public"),
                    (f"{PREFIX}doc-priv", "upload", "user_upload", "内部评估报告",
                     "https://example.invalid/private.pdf", None,
                     "user_provided", "private"),
                ],
            )
            await conn.executemany(
                "INSERT INTO citations (citation_id, doc_id, locator, quote_span) "
                "VALUES ($1, $2, $3, $4)",
                [
                    (ANCHORED, f"{PREFIX}doc-pub", "p.4 §3", QUOTE),
                    (LOST, f"{PREFIX}doc-pub", "p.9", None),          # 失锚
                    (PRIVATE, f"{PREFIX}doc-priv", "第 2 节", "内部数据：单月 12.5 万"),
                ],
            )
        finally:
            await conn.close()

    run(wipe())


def client() -> TestClient:
    return TestClient(create_deref_app(DerefApiDeps(dsn=DSN, today=lambda: date(2026, 8, 4))))


def get(citation_id: str, *, user: str | None = USER) -> Any:
    headers = {"X-User-Id": user} if user is not None else {}
    return client().get(f"/citations/{citation_id}", headers=headers)


# ───────────────────────── acceptance①：短段 + 来源链接


def test_the_quote_and_its_source_link_come_back_together() -> None:
    """引文短段与来源链接一起给——只有短段的话，读者没法去核。"""
    body = get(ANCHORED).json()

    assert body["quote_span"] == QUOTE
    assert body["locator"] == "p.4 §3"
    assert body["doc"]["url"] == "https://example.invalid/2506.06962"
    assert body["doc"]["title"] == "RAG in production"
    assert body["channel"] == "citation"


def test_the_contract_field_names_are_used_verbatim() -> None:
    """`Citation` 的四个字段逐字出现，NEVER 改名。"""
    from dataclasses import fields

    from contracts.models import Citation

    body = get(ANCHORED).json()
    assert {f.name for f in fields(Citation)} <= set(body)


def test_the_endpoint_only_reads_what_gate1_already_pinned() -> None:
    """本卡只取不产：库里那段是什么，回的就是什么（逐字节相等）。

    在读取面重抽一段的话，它和当初钉住的那段迟早不是同一段，
    而正文里那条引用指的是当初那一段。
    """
    body = get(ANCHORED).json()

    async def stored() -> Any:
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(
                "SELECT quote_span FROM citations WHERE citation_id = $1", ANCHORED)
        finally:
            await conn.close()

    assert body["quote_span"] == run(stored())


# ───────────────────────── acceptance②：失锚照实且仍可见


def test_an_unanchored_citation_is_still_returned_and_marked() -> None:
    """失锚 → `anchored: false`，但**整条引用照常返回**。

    藏起来之后，正文里那句结论看上去就是没有出处的——而它其实有出处，只是段落丢了。
    这两件事对读者的意义完全不同。
    """
    response = get(LOST)
    body = response.json()

    assert response.status_code == 200
    assert body["anchored"] is False
    assert body["quote_span"] is None
    assert body["doc"]["url"] == "https://example.invalid/2506.06962", "文献链接仍在"
    assert body["locator"] == "p.9", "定位符还在，读者仍能去翻那一页"
    assert "失锚" in body["anchor_note"]


def test_an_anchored_citation_is_not_marked_lost() -> None:
    """正例：有短段的引用不带失锚标记（否则上一条等于恒真）。"""
    body = get(ANCHORED).json()

    assert body["anchored"] is True
    assert body["anchor_note"] is None


# ───────────────────────── 私有材料的既有纪律（冻结件 Doc docstring）


def test_a_private_source_is_readable_in_product_but_flagged_for_export() -> None:
    """私有材料：产品内可读，但响应要把「不可外链 + 该标什么」交给下游。

    下游猜不出来的规则等于没有规则——导出与分享要照 [审5] 标注，
    就得从这里拿到依据。
    """
    body = get(PRIVATE).json()

    assert body["quote_span"] == "内部数据：单月 12.5 万", "产品内可点开原文段落"
    assert body["doc"]["access"] == "private"
    assert body["external_link_allowed"] is False
    # 期望值也从冻结件取：首版在这里写死了一个全角逗号的版本，而契约用的是半角，
    # 当场红。**写死期望值就是把契约抄了一遍**，抄本与正本迟早不一致——
    # 而这条断言存在的理由恰恰是防这件事。
    assert body["share_note"] == _frozen_share_note()


def test_a_public_source_carries_no_share_restriction() -> None:
    """正例：公开来源不带限制（否则上一条可以靠「一律标私有」满足）。"""
    body = get(ANCHORED).json()

    assert body["doc"]["access"] == "public"
    assert body["external_link_allowed"] is True
    assert body["share_note"] is None


def test_the_share_note_is_the_frozen_wording() -> None:
    """标注文案取自冻结件 `Doc` 的 docstring，NEVER 自己另写一句。

    自己写一句的那天，导出里的说法与契约里的说法就不是同一句了。
    """
    import inspect

    from contracts.models import Doc

    doc_rule = inspect.getdoc(Doc) or ""
    note = get(PRIVATE).json()["share_note"]

    assert note.replace("，", ", ") in doc_rule.replace("，", ", ")


# ───────────────────────── acceptance③：只读 + 身份


def test_identity_is_required() -> None:
    assert get(ANCHORED, user=None).status_code == 422


def test_an_unknown_citation_is_404() -> None:
    assert get(f"{PREFIX}cit-nope").status_code == 404


def test_the_endpoint_module_never_writes() -> None:
    from tests.v041.test_deref_fact import _write_statements

    source = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")
    assert _write_statements(source) == []


def test_the_three_reference_channels_stay_distinct() -> None:
    """引文通道不混进 Fact / PriceCell 的字段（S2-2 的同一条纪律）。"""
    from dataclasses import fields

    from contracts.models import Fact, PriceCell

    body = get(ANCHORED).json()
    foreign = ({f.name for f in fields(Fact)} | {f.name for f in fields(PriceCell)}) - {"unit"}

    assert foreign & set(body) == set(), f"别的通道字段漏进来了：{foreign & set(body)}"
