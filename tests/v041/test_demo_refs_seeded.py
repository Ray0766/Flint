"""FIX-02 · demo 报告正文引用的实体从未入库——正文里九个 id 一个也解不开。

## 缺陷

`harness/demo_seed_report.py` 只写 `deliverables` 与 `blocks` 两张表，
而它写进去的 Block 树**引用了九个实体**（两条 fact · 两条 price entry ·
两条 citation · 一条 chart · 一张质量卡 · 一条 gap hints）。
装配后实测：九条全部解不开（404 / 422）。

前端此刻的显示是**对的**（FB-09：端点不可用时如实标注并显示原 id），
坏的是数据面——报告屏上没有一条引用能换成人话。

## 判据只认真栈上的解引用

卡面 acceptance② 逐字：「判据是**装配后的真栈上逐条解引用拿到内容**，
NEVER 只断言种子脚本里有那几行」。

断言脚本源码里有那几行 INSERT 的写法，在下面每一种情况下都会继续绿：
表结构改名、外键挡住写入、归属过滤把行滤掉、字段写进了另一列。
**「写了 INSERT」与「读得回来」是两件事**，而这张卡要的是后者。

所以这里全程走 `create_app(dsn)` 装配出来的应用 + `TestClient` 发 HTTP，
一条一条 GET，判回来的**内容**，不判脚本。

## 引用清单从夹具树里现取，NEVER 手抄

手抄一份九条的清单，等于给夹具树加了第二个真相：
哪天有人往树里加第十条引用，手抄的那份不会跟着变——**新加的那条从此不在任何判据下**。
所以 `_refs()` 走一遍 `build_tree()` 的判别联合，树里有几条就判几条。
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from flint.api.app import create_app
from flint.domain.models import (
    Block,
    ChartContent,
    CitationListContent,
    CitationMark,
    ClaimSpan,
    FactCell,
    GapNoticeContent,
    ParagraphContent,
    PriceCell,
    ProfileRef,
    QualityCardContent,
    TableContent,
)
from harness.demo_seed_report import DELIVERABLE_ID, build_tree, seed

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
TICKET = REPO / "docs" / "blocked" / "DEMO-REPORT-REFS-NOT-SEEDED.md"
NO_STORAGE_TICKET = REPO / "docs" / "blocked" / "DEMO-REFS-NO-STORAGE-FACE.md"
USER = "demo-user"

# 三类**没有存储面**的引用（见 NO_STORAGE_TICKET）：
#   chart —— `ChartSpec` 只在模板里定义，而 `flint/api/deref.py` 自己写着
#            「NEVER 去改 assets/ 里的模板凑数据」；
#   card  —— `QualityCardContent.card_ref` 按冻结件指向 `QualityCard`（现算不落库，
#            FB-08 §8-1 已登记），而 `/cards/{id}` 服务的是 `EvidenceCard`：
#            往 `evidence_cards` 塞一行就能把 404 变成 200，代价是屏上「质量卡」
#            那一格显示的是一张证据卡——**用一个看起来对的答案盖住一个类型不符**；
#   hints —— 全库没有 `section_states` / `gap_hints` 表。
NO_STORAGE_FACE = {
    ("chart", "chart-demo-cost-trend"),
    ("card", "qc-demo-fixture-01"),
    ("hints", "sec-04-gap-hints"),
}
# 不属于解引用六族的引用通道：claim 与 profile 各有自己的读取面，不在本卡。
OUT_OF_FAMILY = {
    ("claim", "clm-demo-01"),
    ("profile", "research.publications[0]"),
}
ROUTE = {
    "fact": "/facts/{id}",
    "price": "/price-entries/{id}",
    "citation": "/citations/{id}",
    "chart": "/charts/{id}",
    "card": "/cards/{id}",
    "hints": "/hints/{id}",
}


def _refs(tree: list[Block]) -> list[tuple[str, str, dict[str, Any]]]:
    """夹具树里全部引用：`(kind, id, extra)`。**现取，NEVER 手抄一份清单。**

    走的是 `BlockContent` 的判别联合本身——树里加了新的一支而这里没跟上时，
    `test_every_kind_of_reference_in_the_tree_is_accounted_for` 会红。
    """
    found: list[tuple[str, str, dict[str, Any]]] = []
    for block in tree:
        content = block.content
        if isinstance(content, ParagraphContent):
            for span in content.spans:
                if isinstance(span, CitationMark):
                    found.append(("citation", span.citation_id, {}))
                elif isinstance(span, ClaimSpan):
                    found.append(("claim", span.claim_id, {}))
                elif isinstance(span, ProfileRef):
                    found.append(("profile", span.field_path, {}))
        elif isinstance(content, TableContent):
            for row in content.rows:
                for cell in row:
                    if isinstance(cell, FactCell):
                        found.append(("fact", cell.fact_id, {}))
                    elif isinstance(cell, PriceCell):
                        found.append((
                            "price", cell.price_entry_id,
                            {"quantity": cell.quantity},
                        ))
        elif isinstance(content, ChartContent):
            found.append(("chart", content.chart_id, {}))
        elif isinstance(content, QualityCardContent):
            found.append(("card", content.card_ref, {}))
        elif isinstance(content, CitationListContent):
            found.extend(("citation", cid, {}) for cid in content.citation_ids)
        elif isinstance(content, GapNoticeContent):
            found.append(("hints", content.hints_ref, {}))
    return found


def _get(client: TestClient, kind: str, ref: str, extra: dict[str, Any]) -> Any:
    return client.get(
        ROUTE[kind].format(id=ref), params=extra, headers={"x-user-id": USER},
    )


@pytest.fixture(scope="module")
def client() -> Any:
    """真栈：种子灌进测试库 → 装配后的应用 → HTTP。收尾把夹具撤干净。"""
    asyncio.run(seed(dsn=DSN))
    with TestClient(create_app(DSN)) as test_client:
        yield test_client
    asyncio.run(seed(drop_only=True, dsn=DSN))


# ───────────────────────── acceptance①②：逐条解引用拿到内容


def test_every_reference_with_a_storage_face_resolves(client: TestClient) -> None:
    """夹具树里**每一条**有存储面的引用，在装配后的真栈上都换得回内容。

    改前实测九条全部解不开——报告屏正文里赫然写着 `fact-demo-vecdb-cost`。
    """
    unresolved: list[str] = []
    for kind, ref, extra in _refs(build_tree()):
        if (kind, ref) in NO_STORAGE_FACE or (kind, ref) in OUT_OF_FAMILY:
            continue
        got = _get(client, kind, ref, extra)
        if got.status_code != 200:
            unresolved.append(f"{kind} {ref} → {got.status_code} {got.text[:80]}")

    assert unresolved == [], "这些引用在真栈上解不开：\n" + "\n".join(unresolved)


def test_the_content_is_real_content_not_an_empty_shell(client: TestClient) -> None:
    """拿回来的是**内容**，不是一个字段齐全的空壳。

    只判 200 的话，一行 `statement=''` 的种子照样绿，
    而报告屏上那句话仍然是空的。
    """
    fact = _get(client, "fact", "fact-demo-vecdb-cost", {}).json()
    assert fact["statement"].strip(), "事实的正文是空的"
    assert fact["value"] is not None and fact["unit"], "事实没有数值与单位"
    assert fact["citation_ids"], "事实没有出处——三条铁律第一条"
    assert fact["channel"] == "fact"

    price = _get(client, "price", "pe-demo-vecdb-2026", {"quantity": 12.0}).json()
    assert price["item"].strip() and price["source"].strip()
    # 金额是后端按 quantity 算的，前端零计算。
    assert price["amount_low"] == pytest.approx(price["price_low"] * 12.0)
    assert price["channel"] == "price"

    citation = _get(client, "citation", "cit-demo-arxiv-2506-06962", {}).json()
    assert citation["doc"]["title"].strip() and citation["doc"]["url"].startswith("http")
    assert citation["quote_span"], "引用没钉住段落"
    assert citation["anchored"] is True

    # 失锚态照实标记：LightRAG 那条只指着仓库、没钉住段落。
    # 编一句 README 原文把它填满的话，屏幕上与真引文长得一模一样。
    loose = _get(client, "citation", "cit-demo-gh-lightrag", {}).json()
    assert loose["anchored"] is False
    assert loose["anchor_note"], "失锚了却没有一句说明"


def test_the_fixture_facts_never_claim_to_be_promoted(client: TestClient) -> None:
    """夹具事实 `origin == "injected"`，NEVER 冒充 `promoted_claim`。

    `promoted_claim` 的含义是「它来自一条通过两段式对齐的 claim」——
    夹具里没有那条 claim，写成 promoted 就是**给一个没走过流程的数字盖上流程的章**。
    """
    for ref in ("fact-demo-vecdb-cost", "fact-demo-infer-cost"):
        fact = _get(client, "fact", ref, {}).json()
        assert fact["origin"] == "injected", ref
        assert fact["source_claim_id"] is None, ref
        assert fact["promoted_from"] is None, ref


def test_an_unseeded_id_still_returns_the_honest_404(client: TestClient) -> None:
    """**阴性对照**：没种过的 id 照样 404。

    没有这条，上面那些 200 可能是「这个端点对谁都回 200」换来的。
    顺带钉住 FB-09 依赖的那个形状：`code == "NOT_FOUND"`。
    """
    got = _get(client, "fact", "fact-demo-never-seeded", {})

    assert got.status_code == 404
    assert got.json()["code"] == "NOT_FOUND"


def test_seeding_twice_is_idempotent(client: TestClient) -> None:
    """再灌一次不炸、也不长出第二份——夹具脚本声明的就是幂等。"""
    asyncio.run(seed(dsn=DSN))

    got = _get(client, "fact", "fact-demo-vecdb-cost", {})
    assert got.status_code == 200
    listed = client.get(
        f"/deliverables/{DELIVERABLE_ID}/blocks", headers={"x-user-id": USER})
    assert listed.status_code == 200
    assert len(listed.json()["blocks"]) == len(build_tree())


# ───────────────────────── acceptance③：FB-09 的既有行为保留


def test_the_three_without_a_storage_face_stay_honest(client: TestClient) -> None:
    """chart / 质量卡 / gap hints **没有存储面**：照实 404，NEVER 回空壳。

    - chart：`ChartSpec` 只在模板里定义，而 `flint/api/deref.py` 自己写着
      「NEVER 去改 assets/ 里的模板凑数据」；
    - 质量卡：`card_ref` 按冻结件指向 `QualityCard`（现算不落库），
      而 `/cards/{id}` 服务的是 `EvidenceCard`——**塞一行就能变 200，
      但那是拿一个看起来对的答案盖住一个类型不符**；
    - gap hints：全库没有 `section_states` / `gap_hints` 表，
      默认取数缝如实回 `None`（**空列表读起来是「这一节没有缺口」，那是一句结论**）。

    补它们要动的面在本卡 outputs 之外 → 已开单登记。
    这三条也让报告屏上**仍然看得见 FB-09 的诚实态**：
    六条换成了人话，三条如实标注并显示原 id。

    哪天它们有了存储面，这条会红——那时来这里把它移出 NO_STORAGE_FACE。
    """
    for kind, ref in sorted(NO_STORAGE_FACE):
        got = _get(client, kind, ref, {})
        assert got.status_code == 404, f"{kind} {ref} 有存储面了：{got.status_code}"
        assert got.json()["code"] == "NOT_FOUND"

    head = NO_STORAGE_TICKET.read_text(encoding="utf-8")
    for _kind, ref in NO_STORAGE_FACE:
        assert ref in head, f"单子里没点名 {ref}"


def test_every_kind_of_reference_in_the_tree_is_accounted_for() -> None:
    """树里出现的**每一种**引用通道，要么在六族里、要么已登记。

    夹具树加了一支新的 `BlockContent` 而这里没跟上时，那条新引用会**悄悄不在任何判据下**。
    """
    kinds = {kind for kind, _ref, _extra in _refs(build_tree())}
    known = set(ROUTE) | {k for k, _ in OUT_OF_FAMILY}

    assert kinds <= known, f"树里有没归口的引用通道：{sorted(kinds - known)}"
    assert kinds & set(ROUTE) == set(ROUTE), (
        f"六族里有通道在树里没被覆盖到：{sorted(set(ROUTE) - kinds)}"
    )


def test_the_seed_script_still_declares_its_fixture_boundary(
    client: TestClient,
) -> None:
    """夹具身份 NEVER 被这次补种冲淡。

    补种把夹具数字放进了与真数据同一张表：价格行与真报价同列、簇与真簇同表。
    所以「这是夹具」要写在**数据本身**里——只写在脚本注释里的话，
    屏幕上那两个金额与真实报价长得一模一样。
    """
    import harness.demo_seed_report as mod

    assert "NEVER 冒充模型产出" in (mod.__doc__ or "")
    # ① 种进去的每个 id 都带 demo 标记（没有存储面的两条不在此列：
    #    `sec-04-gap-hints` 是章节 id，本来就不是夹具实体）。
    for kind, ref, _extra in _refs(build_tree()):
        if (kind, ref) in OUT_OF_FAMILY or (kind, ref) in NO_STORAGE_FACE:
            continue
        assert "demo" in ref, f"{ref} 看不出是夹具"
    # ② 价格行把这句话**回给了前端**，而不是只留在注释里。
    price = _get(client, "price", "pe-demo-vecdb-2026", {"quantity": 12.0}).json()
    assert "夹具" in price["source"], f"价目的 source 没自报家门：{price['source']}"
    # ③ 私有材料那条诚实态照旧：不外链 + 强制标注。
    note = _get(client, "citation", "cit-demo-fixture-note", {}).json()
    assert note["external_link_allowed"] is False
    assert note["share_note"]


# ───────────────────────── acceptance④：单子


def test_the_ticket_is_closed() -> None:
    """判**机读状态行**（`HYG-01` 立的语法），NEVER 判「已关闭」三个字。

    按字符串搜「已关闭」会把 `K1-02` 那张数成已解决——它正文里那句说的是
    **reddit 的自助注册已关闭**。单子的状态要有一处说了算。
    """
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "**状态** closed" in head
    assert "FIX-02" in head
