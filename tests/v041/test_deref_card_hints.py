"""FB-08：解引用端点⑤⑥ `GET /cards/{ref}`（证据卡）· `GET /hints/{ref}`（缺口提示）。

## 两个 ref 的持久化实况（trace §3 有全表核对）

- **证据卡**在库里：`evidence_cards` 表（M1-032 的七要素），本端点真取它；
- **缺口提示不在库里**：`hints_ref → SectionState.gap_hints`，而全库 31 张表里
  **没有 section_states / gap_hints**。所以本端点按冻结件把**呈现契约**建好，
  并留一个显式的取数缝（`gap_hints_source`），默认「取不到 → 404」。
  测试注入构造的 hint 来验呈现规则——**那才是 acceptance② 的正题**。

## acceptance② 的正题：不确定 NEVER 伪装成确定

冻结件 `GapHint` 的 docstring 原话：

> expand 拒绝注水的出口 [D13]。**missing_permission 绝不伪装成缺资料 [审8]**：
> missing_data → 「补充以下任一即可」+ 一键注入；
> missing_permission → 「需 {required_scope}, 你当前无权访问」→ 请 owner 授权。

这两种缺口**修法完全不同**：一个去补资料，一个去要权限。把后者说成前者，
用户会一直找一份根本不存在于他手里的材料。所以：

- `missing_permission` 的提示里 NEVER 出现 `suggested_sources`（那是「去补资料」的话术）；
- 每条提示都自带 `is_conclusion: false` —— 缺口是**缺口**，不是一句已经站住的结论。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.deref import DerefApiDeps, create_deref_app
from flint.domain.models import GapHint

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "fb08-"
USER = "fb08-user"
CARD = f"{PREFIX}card-01"
CLUSTER = f"{PREFIX}cluster-01"

DATA_GAP = GapHint(
    missing_what="缺少 2026 年的单价数据",
    cause="missing_data",
    suggested_sources=["厂商公开定价页", "用户上传的报价单"],
    action="search",
    target_count=2,
)
PERMISSION_GAP = GapHint(
    missing_what="缺少财务口径的成本明细",
    cause="missing_permission",
    suggested_sources=[],
    action="request_permission",
    required_scope="finance.cost_detail",
)
HINTS = {f"{PREFIX}sec-gaps": [DATA_GAP, PERMISSION_GAP]}


def run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_slate() -> None:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(f"DELETE FROM evidence_cards WHERE card_id LIKE '{PREFIX}%'")
            await conn.execute(f"DELETE FROM clusters WHERE cluster_id LIKE '{PREFIX}%'")
            category = await conn.fetchval("SELECT category_id FROM categories LIMIT 1")
            # centroid 是 NOT NULL 的 vector(1024)：夹具照数据库的约束给一个零向量，
            # 而不是照我以为的形态写（FB-06 的 ck_docs_kind 才刚教过一次）。
            zero_vector = "[" + ",".join(["0"] * 1024) + "]"
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
                "status, first_seen, last_active) "
                "VALUES ($1, $2, $3, $4::vector, 'active', '2026-07-04', '2026-07-04')",
                CLUSTER, "检索增强生成", category, zero_vector)
            await conn.execute(
                "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids, flags, "
                "top_links) VALUES ($1, $2, $3, $4, $5)",
                CARD, CLUSTER, json.dumps(["kw-rag"]), json.dumps(["accelerating"]),
                json.dumps([{"url": "https://example.invalid/a", "title": "A",
                            "source_id": "arxiv", "percentile": 0.9}]))
        finally:
            await conn.close()

    run(wipe())


def client() -> TestClient:
    return TestClient(create_deref_app(
        DerefApiDeps(dsn=DSN, gap_hints_source=lambda ref: HINTS.get(ref))))


def get(path: str, *, user: str | None = USER) -> Any:
    headers = {"X-User-Id": user} if user is not None else {}
    return client().get(path, headers=headers)


# ───────────────────────── ⑤ 证据卡


def test_the_card_body_carries_its_seven_elements() -> None:
    """证据卡回七要素里落库的那几项（card_id / cluster_id / keywords / flags / top_links）。"""
    body = get(f"/cards/{CARD}").json()

    assert body["card_id"] == CARD
    assert body["cluster_id"] == CLUSTER
    assert body["keyword_ids"] == ["kw-rag"]
    assert body["flags"] == ["accelerating"]
    assert body["top_links"][0]["url"] == "https://example.invalid/a"
    assert body["channel"] == "evidence_card"


def test_the_cluster_label_travels_with_the_card() -> None:
    """带上簇名与活跃日——只给 cluster_id 的话，读者还要再问一次「那是哪个簇」。"""
    body = get(f"/cards/{CARD}").json()

    assert body["cluster"]["canonical_name"] == "检索增强生成"
    assert body["cluster"]["last_active"] == "2026-07-04"
    assert body["cluster"]["status"] == "active"


def test_an_unknown_card_is_404() -> None:
    assert get(f"/cards/{PREFIX}card-nope").status_code == 404


def test_card_identity_is_required() -> None:
    assert get(f"/cards/{CARD}", user=None).status_code == 422


# ───────────────────────── ⑥ 缺口提示：不确定 NEVER 伪装成确定


def test_the_hints_say_what_is_missing_and_why() -> None:
    """每条提示都说清「缺的是什么」与「为什么算缺」。"""
    body = get(f"/hints/{PREFIX}sec-gaps").json()
    hints = body["hints"]

    assert [h["missing_what"] for h in hints] == [
        "缺少 2026 年的单价数据", "缺少财务口径的成本明细"]
    assert [h["cause"] for h in hints] == ["missing_data", "missing_permission"]
    assert all(h["why"].strip() for h in hints), "每条都要说得出为什么算缺"
    assert body["channel"] == "gap_hint"


def test_a_gap_is_never_presented_as_a_conclusion() -> None:
    """缺口是缺口，不是一句已经站住的结论——每条都自带 `is_conclusion: false`。"""
    body = get(f"/hints/{PREFIX}sec-gaps").json()

    assert body["is_conclusion"] is False
    assert all(h["is_conclusion"] is False for h in body["hints"])


def test_a_permission_gap_is_never_dressed_up_as_a_data_gap() -> None:
    """[审8] 的正题：`missing_permission` **绝不伪装成缺资料**。

    两种缺口修法完全不同：一个去补资料，一个去要权限。把后者说成前者，
    用户会一直找一份根本不存在于他手里的材料。
    """
    hints = {h["cause"]: h for h in get(f"/hints/{PREFIX}sec-gaps").json()["hints"]}
    permission = hints["missing_permission"]

    assert permission["suggested_sources"] == [], "权限缺口不该给「去哪补资料」"
    assert permission["required_scope"] == "finance.cost_detail"
    assert permission["action"] == "request_permission"
    assert "无权访问" in permission["why"]
    assert "补充" not in permission["why"], "权限缺口的话术混进了补资料的说法"


def test_a_data_gap_does_tell_where_to_look() -> None:
    """正例：缺资料的那条**要**给出处建议（否则上一条可以靠「一律不给建议」满足）。"""
    hints = {h["cause"]: h for h in get(f"/hints/{PREFIX}sec-gaps").json()["hints"]}
    data = hints["missing_data"]

    assert data["suggested_sources"] == ["厂商公开定价页", "用户上传的报价单"]
    assert data["required_scope"] is None
    assert "补充" in data["why"]
    assert "无权" not in data["why"]


def test_the_wording_follows_the_frozen_docstring() -> None:
    """两种话术取自冻结件 `GapHint` 的 docstring，NEVER 自己另编一套。

    与 FB-06 的 share_note 同一条纪律：抄一份出来的，和正本迟早不是同一句。
    """
    import inspect

    rule = inspect.getdoc(GapHint) or ""
    hints = {h["cause"]: h for h in get(f"/hints/{PREFIX}sec-gaps").json()["hints"]}

    assert "补充以下任一即可" in rule and "补充以下任一即可" in hints["missing_data"]["why"]
    assert "你当前无权访问" in rule
    assert "你当前无权访问" in hints["missing_permission"]["why"]


def test_hints_that_are_not_persisted_yet_are_404_not_empty() -> None:
    """取不到的 hints_ref → **404**，NEVER 回一个空列表。

    空列表读起来是「这一节没有缺口」——那是一句**结论**，而真相是「没人存过它」。
    这正是 acceptance② 要防的那种伪装。
    """
    response = get(f"/hints/{PREFIX}sec-nope")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_hints_identity_is_required() -> None:
    assert get(f"/hints/{PREFIX}sec-gaps", user=None).status_code == 422


def test_the_default_source_persists_nothing_yet() -> None:
    """现状登记：默认取数缝**取不到任何东西**，因为全库没有存 gap_hints 的表。

    哪天真建了表并接上，这条会红——提醒那时的人来补一条真数据的验收。
    """
    from flint.api.deref import DEFAULT_GAP_HINTS_SOURCE

    assert DEFAULT_GAP_HINTS_SOURCE("any-ref") is None

    async def tables() -> set[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        finally:
            await conn.close()
        return {r["tablename"] for r in rows}

    names = run(tables())
    assert "gap_hints" not in names and "section_states" not in names, (
        "库里已经有存缺口提示的表了，本卡的「未持久化」登记要更新"
    )


def test_the_endpoint_module_never_writes() -> None:
    from tests.v041.test_deref_fact import _write_statements

    source = (REPO / "flint" / "api" / "deref.py").read_text(encoding="utf-8")
    assert _write_statements(source) == []
