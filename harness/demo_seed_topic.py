"""demo 夹具：给主题详情屏种一条**可复现**的主题（`DEC-041`，opt-in，NEVER 自动跑）。

为什么需要它
------------
`harness/fe_smoke.py` 扫 `/topics/[id]` 时用的样例 id 是占位串 `tp-placeholder`，
`GET /topics/{id}` 于是回带 `code` 的 404——**那是 `TS-007` 要的正确行为**，
红的是取证样例，不是那一屏（与 `DEC-037` 同一形状）。
`CONSOLE_BASELINE` 因此给这一屏留了 1 条 404 额度。

本脚本给它一个**由脚本自己造、随时能重造**的目标。

## 开工时查到的实况：demo 库里已经有六条**真**主题

`docs/blocked/DEMO-TOPIC-SAMPLE-ID-IS-A-PLACEHOLDER.md` 立单时写的是
「库里一条 `topics` 行都没有」。**那句话现在不成立了**——实查：

```
topic-demo14bf9d94b0-1 … -9   共 6 条，seed-demo14bf9d94b0
每条 speculative=false、2 条 why_now 证据（带 citation_id）
```

它们是**模型产出**（某次 demo 跑留下的），归在 `proj-demo14bf9d94b0` 名下，
`/projects/[id]/topics` 那一屏因此**早就有真数据**。

### 那为什么还要种一条夹具

取证样例要的是**可复现**。那六条是一次过去的运行留下的痕迹，
**没有任何脚本能把它们重造出来**——demo 库重建一次，样例 id 又变成死链，
而那正是这张卡要终结的失败。夹具由脚本写死、幂等、随时能撤，才是探针该指的东西。

**两者互不相扰**：本脚本只写自己那几行（`-demo-fixture-` 前缀），
六条真主题**一个字节都不碰**（`_drop` 的每条 DELETE 都按夹具 id 限定）。

若 owner 更希望取证屏上是真产出，`harness/fe_smoke.py` 里改一行
（`"/topics/[id]": "topic-demo14bf9d94b0-1"`）即可——代价是那条 id 依赖于
一次没人复跑的历史运行。

边界（读这段再决定要不要跑）
--------------------------
- 这是**夹具数据**，不是产品生成物：文本由本脚本写死，**NEVER 冒充模型产出**。
  `-demo-fixture-` 前缀是标记，而 `one_liner` 与那篇说明 doc
  把「这是夹具」写在**数据本身**里，不是只写在这段注释里。
- `why_now.speculative=false` 且带两条证据：**因为它真有两条 citation**
  （本脚本一并种下），不是为了让屏好看。证据为空时冻结件 `[C2]` 要求置 `true`，
  那时屏上该出现推测标——两种都是实话，这里给的是有证据的那一种。
- 只写夹具自己那些行，幂等（重复跑先按 id 删同一批再写）；`--drop` 原样撤干净。
- NEVER 触碰 `contracts/`、NEVER 改任何端点响应形状。

跑法：
    python -m harness.demo_seed_topic            # 灌
    python -m harness.demo_seed_topic --drop     # 撤
"""
from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, date, datetime

import asyncpg

from flint.domain.models import (
    Citation,
    Doc,
    Origin,
    Principal,
    Topic,
    TopicSeed,
    WhyNow,
    WhyNowEvidence,
)
from flint.evidence.docstore import PgDocStore
from flint.topic.store import PgOriginStore, PgTopicSeedStore, PgTopicStore

DSN = os.environ.get("FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")

TOPIC_ID = "topic-demo-fixture-vecdb"
SEED_ID = "seed-demo-fixture-vecdb"
ORIGIN_ID = "origin-demo-fixture-vecdb"
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)   # 固定时钟 → 重复跑字节稳定
# 1024 维零向量：本条夹具**不参与相似度检索**，给一个真向量反而像是算出来的。
EMBEDDING: list[float] = [0.0] * 1024


def fixture_docs() -> list[Doc]:
    """两篇公开文献 + 一篇说明本脚本自己的私有件。

    第三篇不是凑数：它让「这条主题是夹具」这句话有**数据面上的出处**，
    而不是只写在代码注释里——注释不会跟着数据被查询出来。
    """
    return [
        Doc(
            doc_id="doc-demo-fixture-topic-pgvector", source_id="github", kind="repo",
            title="pgvector/pgvector",
            url="https://github.com/pgvector/pgvector",
            published_at=None, meta={"fixture": True},
            origin="retrieved", access="public",
        ),
        Doc(
            doc_id="doc-demo-fixture-topic-hnsw", source_id="arxiv", kind="paper",
            title=(
                "Efficient and robust approximate nearest neighbor search using "
                "Hierarchical Navigable Small World graphs"
            ),
            url="http://arxiv.org/abs/1603.09320",
            published_at=date(2016, 3, 30),
            meta={"fixture": True}, origin="retrieved", access="public",
        ),
        Doc(
            doc_id="doc-demo-fixture-topic-note", source_id="fixture",
            kind="user_upload",
            title="demo 夹具主题说明（harness/demo_seed_topic.py）",
            url="file://harness/demo_seed_topic.py",
            published_at=NOW.date(), meta={"fixture": True},
            origin="user_provided", access="private",
        ),
    ]


def fixture_citations() -> list[Citation]:
    """两条给 `why_now` 的证据用，一条标明夹具身份。

    HNSW 那条 `quote_span` 取的是论文摘要里的原句；pgvector 那条
    `quote_span=None`——**失锚态照实标记**，NEVER 编一句 README 原文来把它填满：
    编出来的那句话在屏幕上与真引文长得一模一样。
    """
    return [
        Citation(
            citation_id="cit-demo-fixture-topic-pgvector",
            doc_id="doc-demo-fixture-topic-pgvector", locator=None, quote_span=None,
        ),
        Citation(
            citation_id="cit-demo-fixture-topic-hnsw",
            doc_id="doc-demo-fixture-topic-hnsw", locator="Abstract",
            quote_span=(
                "We present a new approach for the approximate K-nearest neighbor "
                "search based on navigable small world graphs with controllable "
                "hierarchy (Hierarchical NSW, HNSW)."
            ),
        ),
        Citation(
            citation_id="cit-demo-fixture-topic-note",
            doc_id="doc-demo-fixture-topic-note",
            locator="本文件 fixture_topic()",
            quote_span="这条主题由夹具脚本写死，NEVER 当作模型产出。",
        ),
    ]


def fixture_origin() -> Origin:
    return Origin(
        origin_id=ORIGIN_ID, kind="idea",
        owner=Principal(kind="user", id="demo-user"),
        payload={"text": "【夹具】向量库选型这件事，团队每季度重吵一次"},
        created_at=NOW,
    )


def fixture_seed() -> TopicSeed:
    return TopicSeed(
        seed_id=SEED_ID, origin_id=ORIGIN_ID,
        keywords=["向量数据库", "pgvector", "HNSW", "检索延迟"],
        hypothesis=None,     # `idea` 入口非必填（`combo` 才必填）
        context_text=(
            "【夹具】小团队在 Postgres 里直接开 pgvector，还是单独上一套向量库——"
            "这个决定每季度被重新讨论一次，而每次讨论都从零开始找数字。"
        ),
    )


def fixture_topic() -> Topic:
    """一条**带证据**的主题。

    `speculative=false` 是因为它真有两条 citation，不是为了让屏好看：
    冻结件 `[C2]` 的规则是「evidences 为空 → True」。
    """
    return Topic(
        topic_id=TOPIC_ID, seed_id=SEED_ID,
        one_liner=(
            "【夹具】给小团队的向量库选型助手：把 pgvector 与独立向量库的"
            "延迟、成本、运维负担放在同一张表上比"
        ),
        target_user_tag="10 人以下、已经在用 Postgres 的后端团队",
        form_factor_tag="一次性对比报告（非订阅）",
        why_now=WhyNow(
            claim=(
                "【夹具】pgvector 把 HNSW 索引带进了 Postgres 本体，"
                "「要不要单独上一套向量库」从一道架构题变成了一道成本题——"
                "而算这道题需要的数字散在各处。"
            ),
            evidences=[
                WhyNowEvidence(
                    event="pgvector 在 0.5.0 起内置 HNSW 索引",
                    event_date=date(2023, 8, 28),
                    citation_id="cit-demo-fixture-topic-pgvector",
                ),
                WhyNowEvidence(
                    event="HNSW 论文给出可控层级的近邻图检索方案",
                    event_date=date(2016, 3, 30),
                    citation_id="cit-demo-fixture-topic-hnsw",
                ),
            ],
            speculative=False,
        ),
        keyword_mapping={
            "向量数据库": ["vector database", "vector store"],
            "pgvector": ["pgvector", "postgres vector"],
            "HNSW": ["hnsw", "hierarchical navigable small world"],
        },
        embedding=EMBEDDING,
    )


async def _drop(conn: asyncpg.Connection) -> None:
    """撤干净。**每一条都按夹具自己的 id 限定**——NEVER 出现一条不带 WHERE 的 DELETE。

    顺序按外键：topics → topic_seeds → origins；citations → docs。
    demo 库里那六条**真**主题（`topic-demo14bf9d94b0-*`）一个字节都不碰。
    """
    await conn.execute("DELETE FROM topics WHERE topic_id = $1", TOPIC_ID)
    await conn.execute("DELETE FROM topic_seeds WHERE seed_id = $1", SEED_ID)
    await conn.execute("DELETE FROM origins WHERE origin_id = $1", ORIGIN_ID)
    await conn.execute(
        "DELETE FROM citations WHERE citation_id = ANY($1::text[])",
        [c.citation_id for c in fixture_citations()])
    await conn.execute(
        "DELETE FROM docs WHERE doc_id = ANY($1::text[])",
        [d.doc_id for d in fixture_docs()])


async def seed(drop_only: bool = False, dsn: str = DSN) -> None:
    """dsn 可注入：判据要在**测试库**上跑同一份种子，而 demo 库的地址写死在模块里。"""
    conn = await asyncpg.connect(dsn)
    try:
        await _drop(conn)
    finally:
        await conn.close()
    if drop_only:
        print(f"dropped fixture topic {TOPIC_ID}")
        return

    docs = PgDocStore(dsn)
    for doc in fixture_docs():
        await docs.save_doc(doc)
    for citation in fixture_citations():
        await docs.save_citation(citation)
    await PgOriginStore(dsn).save(fixture_origin())
    await PgTopicSeedStore(dsn).save(fixture_seed())
    await PgTopicStore(dsn).save(fixture_topic())

    topic = fixture_topic()
    print(f"seeded {TOPIC_ID}: {len(topic.why_now.evidences)} 条 why_now 证据 · "
          f"{len(fixture_citations())} citation · {len(fixture_docs())} doc")
    print("  主题详情屏 · http://localhost:3000/topics/" + TOPIC_ID)
    print("  它是夹具：前缀 -demo-fixture- + 文案里的【夹具】，NEVER 冒充模型产出")
    print("  demo 库里那六条真主题（topic-demo14bf9d94b0-*）未受影响")


def main() -> None:
    parser = argparse.ArgumentParser(description="flint demo 主题夹具（opt-in）")
    parser.add_argument("--drop", action="store_true", help="只删除夹具，不重灌")
    parser.add_argument("--dsn", default=DSN, help="目标库（默认本机 demo）")
    args = parser.parse_args()
    asyncio.run(seed(drop_only=args.drop, dsn=args.dsn))


if __name__ == "__main__":
    main()
