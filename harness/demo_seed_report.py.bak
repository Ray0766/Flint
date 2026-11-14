"""demo 夹具：给报告 L0 屏灌一份**覆盖全部诚实态**的 Block 树（opt-in，NEVER 自动跑）。

为什么需要它
------------
`GET /deliverables/{id}/blocks`（M3-058）是报告屏的读契约，端点真实存在；但 demo 后端
没有 report 组稿 worker（demo_server 的 enqueue 只接 gate1_analysis），真实链路
Gate①→report→Block 树在本环境跑不通 → 库里没有任何带诚实态的交付物 → 前端只能拿 404。

本脚本**不跑生成**，只做一件事：用冻结件 `flint.domain.models` 的域对象 + 生产 store
（`PgDeliverableStore` / `PgBlockStore`）把一棵 Block 树写进库，交给**真端点**去服务、
交给**真门禁**（`guarded_render`，M3-037）去判导出。于是：

  - 409 EXPORT_BLOCKED 是后端门禁**真算**出来的（blocking 块存在 → 拒导出），
  - 保护块（locked ∨ author=="user" ∨ user_modified）是后端**真字段**，
  - 前端一处也不需要造数据。

正文里那些 id 也要解得开（FIX-02）
--------------------------------
Block 树里存的是 id（`fact-demo-vecdb-cost`、`pe-demo-vecdb-2026`…），六个解引用端点
（FB-04~FB-09）负责把 id 换成内容。而此前本脚本只写 deliverables/blocks 两张表——
**正文引用的九个实体一个也没入库**，报告屏上九条引用全部显示原 id。

所以现在连它们一起种：两条 fact（走 `PgLedgerStore.derive`）· 两条 price entry ·
三条 citation + 三篇 doc · 一条归属用的 project。
三条**没有存储面**的除外（chart 只在模板里定义、质量卡现算不落库、gap hints 全库没有表）——
它们照旧 404，正是 FB-09 诚实态在这一屏上的活样本，登记在
`docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md`。

边界（读这段再决定要不要跑）
--------------------------
- 这是**夹具数据**，不是产品生成物：文本由本脚本写死，NEVER 冒充模型产出。
  `-demo-fixture-` / `-demo-` 前缀即为标记，价格行的 `source` 与那篇夹具说明 doc
  把「这是夹具」写在**数据本身**里，而不是只写在这段注释里。
- 两条 fact 的 `origin` 恒为 `injected`：`promoted_claim` 的含义是「它来自一条
  通过两段式对齐的 claim」，夹具里没有那条 claim——写成 promoted 等于给一个
  没走过流程的数字盖上流程的章。
- 两篇公开文献的 `origin="retrieved"` 说的是**这条 URL 的来源类别**（公开可核验），
  NEVER 表示本脚本真去抓过；夹具身份由 `doc-demo-fixture-` 前缀标记。
- 不跑它，报告屏就如实显 404「该交付物尚未生成」——那也是正确行为。
- 只写夹具自己那些行，幂等（重复跑先按 id 删同一批再写）；`--drop` 原样撤干净。
- NEVER 触碰 contracts/、NEVER 改任何端点响应形状。

跑法：
    python -m harness.demo_seed_report            # 灌
    python -m harness.demo_seed_report --drop     # 撤（连夹具行一起删干净）
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime

import asyncpg

from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import (
    Block,
    BlockContent,
    ChartContent,
    Citation,
    CitationListContent,
    CitationMark,
    ClaimSpan,
    DeclarationContent,
    Deliverable,
    Doc,
    FactCell,
    GapNoticeContent,
    HeadingContent,
    ParagraphContent,
    PriceCell,
    PriceEntry,
    Principal,
    ProfileRef,
    Project,
    QualityCardContent,
    TableContent,
    TextCell,
    TextSpan,
)
from flint.evidence.docstore import PgDocStore
from flint.ledger.store import PgLedgerStore
from flint.pricebook.seed import seed_pricebook_on
from flint.topic.store import PgProjectStore

DSN = os.environ.get("FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")
DELIVERABLE_ID = "del-demo-fixture-report"
PROJECT_ID = "proj-demo-fixture"
LEDGER_ID = "led-demo-fixture"
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)   # 固定时钟 → 重复跑字节稳定


def _blk(
    block_id: str,
    section_id: str,
    order: int,
    btype: str,
    content: BlockContent,
    *,
    claim_ids: list[str] | None = None,
    fact_ids: list[str] | None = None,
    author: str = "system",
    locked: bool = False,
    user_modified: bool = False,
    needs_review: bool = False,
    review_reason: str | None = None,
    review_severity: str | None = None,
) -> Block:
    return Block(
        block_id=block_id, deliverable_id=DELIVERABLE_ID, section_id=section_id,
        order=order, type=btype,                      # type: ignore[arg-type]
        content=content, claim_ids=claim_ids or [], fact_ids=fact_ids or [],
        author=author,                                # type: ignore[arg-type]
        revision=1, locked=locked, user_modified=user_modified,
        needs_review=needs_review,
        review_reason=review_reason,                  # type: ignore[arg-type]
        review_severity=review_severity,              # type: ignore[arg-type]
    )


def build_tree() -> list[Block]:
    """8 支 BlockContent 判别联合全覆盖 + 五种保护/复核/争议/缺口态各一。"""
    return [
        # ① declaration · locked → 保护块钉顶，前端不得渲染任何控件 [D12]
        _blk(
            "bf-01", "sec-00-intro", 0, "declaration",
            DeclarationContent(
                kind="declaration",
                text="本报告结论均以引用为准，未引用处为推测；数字按三通道标注出处。",
            ),
            locked=True,
        ),
        # ② heading
        _blk(
            "bf-02", "sec-01-market", 0, "heading",
            HeadingContent(kind="heading", level=2, text="市场与需求"),
        ),
        # ③ paragraph · disputed claim + cite + profile 三种 span，advisory 复核（不挡导出）
        _blk(
            "bf-03", "sec-01-market", 1, "paragraph",
            ParagraphContent(kind="paragraph", spans=[
                TextSpan(kind="text", text="检索增强生成在企业知识库场景已有落地，"),
                ClaimSpan(
                    kind="claim", claim_id="clm-demo-01",
                    text="该方向已出现可复现的中试证据", disputed_mark=True,
                ),
                TextSpan(kind="text", text="；本节口径取自 "),
                ProfileRef(kind="profile", field_path="research.publications[0]"),
                TextSpan(kind="text", text=" 与 "),
                CitationMark(kind="cite", citation_id="cit-demo-arxiv-2506-06962"),
                TextSpan(kind="text", text="。"),
            ]),
            claim_ids=["clm-demo-01"],
            needs_review=True, review_reason="fact_disputed", review_severity="advisory",
        ),
        # ④ table · 三通道分渲（text / fact / price），blocking 复核 → 后端门禁真拒导出
        _blk(
            "bf-04", "sec-02-cost", 0, "table",
            TableContent(kind="table", header=["项", "事实", "单价×数量"], rows=[
                [
                    TextCell(kind="text", text="向量库托管"),
                    FactCell(kind="fact", fact_id="fact-demo-vecdb-cost"),
                    PriceCell(kind="price", price_entry_id="pe-demo-vecdb-2026", quantity=12.0),
                ],
                [
                    TextCell(kind="text", text="推理算力"),
                    FactCell(kind="fact", fact_id="fact-demo-infer-cost"),
                    PriceCell(kind="price", price_entry_id="pe-demo-gpu-2026", quantity=720.0),
                ],
            ]),
            fact_ids=["fact-demo-vecdb-cost", "fact-demo-infer-cost"],
            needs_review=True, review_reason="fact_removed", review_severity="blocking",
        ),
        # ⑤ chart · 只有 chart_id，无数据点（前端零计算）
        _blk(
            "bf-05", "sec-02-cost", 1, "chart",
            ChartContent(kind="chart", chart_id="chart-demo-cost-trend"),
        ),
        # ⑥ quality_card · 只有 card_ref（解引用端点未建）
        _blk(
            "bf-06", "sec-03-quality", 0, "quality_card",
            QualityCardContent(kind="quality_card", card_ref="qc-demo-fixture-01"),
        ),
        # ⑦ citation_list
        _blk(
            "bf-07", "sec-03-quality", 1, "citation_list",
            CitationListContent(kind="citation_list", citation_ids=[
                "cit-demo-arxiv-2506-06962", "cit-demo-gh-lightrag",
            ]),
        ),
        # ⑧ gap_notice · author="user" → 保护块只读（缺口不以生成文字填满）[D13][审8]
        _blk(
            "bf-08", "sec-04-gap", 0, "gap_notice",
            GapNoticeContent(kind="gap_notice", hints_ref="sec-04-gap-hints"),
            author="user",
        ),
        # ⑨ 另一支保护形态：system 块被用户改过 → user_modified=True
        _blk(
            "bf-09", "sec-04-gap", 1, "heading",
            HeadingContent(kind="heading", level=3, text="待补：区域定价口径"),
            user_modified=True,
        ),
    ]


def fixture_docs() -> list[Doc]:
    """三篇文献：两篇公开（可外链）+ 一篇夹具自述（private，导出时强制标注不外链）。

    第三篇不是凑数：它让**两条 fact 的出处有地方可指**，而那个出处就是本脚本自己——
    这是实话。给它编一个供应商报价页 URL 才是编造。
    它同时把 `access="private"` 那条诚实态也带上了屏（外链禁止 + 分享标注）。
    """
    return [
        Doc(
            doc_id="doc-demo-fixture-arxiv-2506-06962", source_id="arxiv", kind="paper",
            title="AR-RAG: Autoregressive Retrieval Augmentation for Image Generation",
            url="http://arxiv.org/abs/2506.06962v3",
            published_at=datetime(2025, 6, 8, tzinfo=UTC).date(),
            meta={"fixture": True}, origin="retrieved", access="public",
        ),
        Doc(
            doc_id="doc-demo-fixture-gh-lightrag", source_id="github", kind="repo",
            title="HKUDS/LightRAG",
            url="https://github.com/HKUDS/LightRAG",
            published_at=None, meta={"fixture": True},
            origin="retrieved", access="public",
        ),
        Doc(
            doc_id="doc-demo-fixture-note", source_id="fixture", kind="user_upload",
            title="demo 夹具数据说明（harness/demo_seed_report.py）",
            url="file://harness/demo_seed_report.py",
            published_at=NOW.date(), meta={"fixture": True},
            origin="user_provided", access="private",
        ),
    ]


def fixture_citations() -> list[Citation]:
    """两条进正文、一条给 fact 当出处。

    LightRAG 那条 `quote_span=None` —— **失锚态照实标记**（FB-06 的
    `anchor_note`）。这里不去编一句 README 原文来把它填满：
    编出来的那句话在屏幕上与真引文长得一模一样。
    """
    return [
        Citation(
            citation_id="cit-demo-arxiv-2506-06962",
            doc_id="doc-demo-fixture-arxiv-2506-06962", locator="Abstract",
            quote_span=(
                "We introduce Autoregressive Retrieval Augmentation (AR-RAG), "
                "a novel paradigm that enhances image generation by autoregressively "
                "incorporating knearest neighbor retrievals at the patch level."
            ),
        ),
        Citation(
            citation_id="cit-demo-gh-lightrag",
            doc_id="doc-demo-fixture-gh-lightrag", locator=None, quote_span=None,
        ),
        Citation(
            citation_id="cit-demo-fixture-note",
            doc_id="doc-demo-fixture-note", locator="本文件 fixture_facts()",
            quote_span="两条记账口径由夹具脚本写死，NEVER 当作检索结果。",
        ),
    ]


def fixture_facts() -> list[dict[str, object]]:
    """两条 fact 的 `changes["add"]` 行（`PgLedgerStore.derive` 的入参形状）。

    **说的是记账口径，不是市场行情**：一条编出来的市场报价会被读成一个有出处的数字，
    而钱的通道在 PriceCell 那边——三通道 NEVER 混用（S2-2），
    这里说数量、那里说单价，正是那条铁律在这张表上的样子。
    """
    return [
        {
            "fact_id": "fact-demo-vecdb-cost",
            "statement": "夹具口径：向量库托管按实例月计费，本表按 12 实例月记账。",
            "value": 12.0, "unit": "实例月",
            "citation_ids": ["cit-demo-fixture-note"],
            "status": "frozen", "origin": "injected",
            "source_claim_id": None, "promoted_from": None,
        },
        {
            "fact_id": "fact-demo-infer-cost",
            "statement": "夹具口径：推理算力按 GPU 卡时计费，本表按 720 卡时记账。",
            "value": 720.0, "unit": "卡时",
            "citation_ids": ["cit-demo-fixture-note"],
            "status": "frozen", "origin": "injected",
            "source_claim_id": None, "promoted_from": None,
        },
    ]


def fixture_prices() -> list[PriceEntry]:
    """两条价目。`source` 把「这是夹具」写进**数据本身**——端点原样回给前端。

    只写在脚本注释里的话，屏幕上那两个金额与真实报价长得一模一样。
    """
    note = "夹具数据 · harness/demo_seed_report.py 写死，NEVER 当作真实报价"
    return [
        PriceEntry(
            entry_id="pe-demo-vecdb-2026", item="托管向量库（单实例）", unit="实例月",
            price_low=800.0, price_high=1500.0, currency="CNY", region="CN",
            year=2026, source=note, updated_at=NOW, stale_after_months=12,
        ),
        PriceEntry(
            entry_id="pe-demo-gpu-2026", item="推理 GPU（单卡）", unit="卡时",
            price_low=6.0, price_high=14.0, currency="CNY", region="CN",
            year=2026, source=note, updated_at=NOW, stale_after_months=12,
        ),
    ]


async def _seed_referenced(conn: asyncpg.Connection, dsn: str) -> None:
    """正文引用的实体。**走生产 store**，NEVER 在这里另写一份写库口径。"""
    await PgProjectStore(dsn).save(Project(
        project_id=PROJECT_ID, owner=Principal(kind="user", id="demo-user"),
        origin_id="origin-demo-fixture", topic_ids=[], chosen_topic_id=None,
        deliverable_ids=[DELIVERABLE_ID], change_log=[], status="active",
        created_at=NOW,
    ))
    # 事实走账本：facts 表只经 `derive` 落地，绕过它就等于绕过版本与乐观锁。
    await PgLedgerStore(dsn, id_factory=lambda: LEDGER_ID, now=lambda: NOW).derive(
        PROJECT_ID, 0, "initial",
        {"add": fixture_facts(), "actor": "u-demo-fixture", "created_from": []},
    )
    docs = PgDocStore(dsn)
    for doc in fixture_docs():
        await docs.save_doc(doc)
    for citation in fixture_citations():
        await docs.save_citation(citation)
    await seed_pricebook_on(conn, fixture_prices())
    # 质量卡**故意不种**：`QualityCardContent.card_ref` 按冻结件指向 `QualityCard`
    # （现算不落库，FB-08 §8-1 已登记），而 `/cards/{id}` 服务的是 `EvidenceCard`。
    # 往 `evidence_cards` 塞一行 `qc-demo-fixture-01` 能把 404 变成 200，
    # 代价是屏上「质量卡」那一格里显示的是一张证据卡——
    # **把一个类型不符换成了一个看起来对的答案**，而且从此没人看得见。
    # 照旧 404，登记在 docs/blocked/DEMO-REFS-NO-STORAGE-FACE.md。


async def _drop(conn: asyncpg.Connection) -> None:
    """撤干净。**每一条都按夹具自己的 id 限定**——NEVER 出现一条不带 WHERE 的 DELETE。

    顺序按外键：facts→facts_ledgers、citations→docs、evidence_cards→clusters。
    """
    await conn.execute("DELETE FROM blocks WHERE deliverable_id = $1", DELIVERABLE_ID)
    await conn.execute(
        "DELETE FROM deliverables WHERE deliverable_id = $1", DELIVERABLE_ID
    )
    await conn.execute(
        "DELETE FROM facts WHERE ledger_id IN "
        "(SELECT ledger_id FROM facts_ledgers WHERE project_id = $1)", PROJECT_ID)
    await conn.execute("DELETE FROM facts_ledgers WHERE project_id = $1", PROJECT_ID)
    await conn.execute("DELETE FROM projects WHERE project_id = $1", PROJECT_ID)
    await conn.execute(
        "DELETE FROM citations WHERE citation_id = ANY($1::text[])",
        [c.citation_id for c in fixture_citations()])
    await conn.execute(
        "DELETE FROM docs WHERE doc_id = ANY($1::text[])",
        [d.doc_id for d in fixture_docs()])
    await conn.execute(
        "DELETE FROM pricebook WHERE entry_id = ANY($1::text[])",
        [p.entry_id for p in fixture_prices()])


async def seed(drop_only: bool = False, dsn: str = DSN) -> None:
    """dsn 可注入：判据要在**测试库**上跑同一份种子，而 demo 库的地址写死在模块里。"""
    conn = await asyncpg.connect(dsn)
    try:
        await _drop(conn)
        if not drop_only:
            await _seed_referenced(conn, dsn)
    finally:
        await conn.close()
    if drop_only:
        print(f"dropped fixture deliverable {DELIVERABLE_ID}")
        return

    await PgDeliverableStore(dsn=dsn).save_deliverable(Deliverable(
        deliverable_id=DELIVERABLE_ID, project_id=PROJECT_ID, type="report",
        version=1, supersedes=None, inputs=[], ledger_version=1,
        generation_record_id="rec-demo-fixture", stale_reasons=[], created_at=NOW,
    ))
    tree = build_tree()
    await PgBlockStore(dsn=dsn).save_tree(DELIVERABLE_ID, tree)
    print(f"seeded {DELIVERABLE_ID}: {len(tree)} blocks")
    print(
        f"  引用实体：{len(fixture_facts())} fact · {len(fixture_prices())} price · "
        f"{len(fixture_citations())} citation"
    )
    print("  报告屏 · http://localhost:3001/deliverables/" + DELIVERABLE_ID)
    print("  blocking 块 bf-04 存在 → 导出 markdown/html/docx 应回 409 EXPORT_BLOCKED")
    print("  chart / 质量卡 / gap hints 没有存储面 → 照旧 404，屏上如实显原 id（FB-09）")


def main() -> None:
    parser = argparse.ArgumentParser(description="flint demo 报告夹具（opt-in）")
    parser.add_argument("--drop", action="store_true", help="只删除夹具，不重灌")
    parser.add_argument("--dsn", default=DSN, help="目标库（默认 demo 库）")
    args = parser.parse_args()
    asyncio.run(seed(drop_only=args.drop, dsn=args.dsn))


if __name__ == "__main__":
    main()
