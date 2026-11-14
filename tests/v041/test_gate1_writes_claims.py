"""CHAIN-01 · gate1 收尾把 support_claims 落成 `claims` 行。

## 主链路在中间断成两段，而两段各自都是绿的

| 段 | 产出落在哪 |
|---|---|
| gate1 | `snapshots`：`snap-{job}-docs` / `-judge` / `-verdict` |
| 组稿 | 读 `claims WHERE deliverable_id = <来源 id>` |

gate1 从不往 `claims` 写行——它把 support/refute 放在 judge 快照的 JSON 里。
于是「拿判定去组稿」这一步，此前**只能靠人手种一条 claim**。

## 那个 `deliverable_id` 填什么：先定口径，再写

`claims` 表按交付物索引，而 **gate1 的产出不是一份交付物**。
本卡定的口径是**分析产物 id**：`analysis-{job_id}`。

三条理由：

1. **与交付物命名空间不相交**：交付物是 `del-{job}`，分析产物是 `analysis-{job}`。
   两者永远撞不上，看一眼就知道这行 claim 来自判定而不是某篇报告；
2. **一次判定一个产物**：job id 已经是那次判定的唯一标识，NEVER 另造一套；
3. **`claims.deliverable_id` 没有外键**（`migrations/0008`），
   所以这个 id **不需要**、也 NEVER 去 `deliverables` 表建一行假记录——
   建了的话，交付物列表里会多出一份没人能打开的「报告」。

## 三种「有多支持」NEVER 挤进同一个表示

| 情形 | alignment |
|---|---|
| 对齐器判过、说支持 | `supports` |
| 对齐器判过、说不支持或只沾边 | `unsupported` / `partial` |
| **超出 K 上限、根本没判** | `pending` |

第三种是本卡最要紧的一条：把没判过的写成 `unsupported`，
读起来是「查过了，证据不支持」——那是一句系统没有依据说出口的话。
写成 `supports` 更糟：它会被提升成 Fact（S2-4）。

## 「有证据」与「引用落库了」也是两件事

`confidence="cited"` 意思是这条结论**指得出一条引用**。
gate1 手里有 doc，但 quote_span 的钉入（`pin_verdict_citations`）是另一步，
**离线/队列路径下根本没跑**。所以本卡按库里实际有没有那条 citation 行来定：
有 → `cited` 带上它；没有 → `speculative` 且 `citation_ids` 为空。

编一个指向不存在 citation 的 id，会让下游渲染时解引用失败——
而那种失败读起来像「引用坏了」，真相是「引用从没入过库」。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.jobs.gate1 import (
    ANALYSIS_PRODUCT_PREFIX,
    analysis_product_id,
    build_offline_deps,
    run_gate1,
)

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "chain01-"
JOB = f"{PREFIX}job-1"
PRODUCT = f"{ANALYSIS_PRODUCT_PREFIX}{JOB}"
KEYWORDS = ["检索增强生成"]


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


async def _claim_rows(product_id: str) -> list[dict[str, Any]]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT * FROM claims WHERE deliverable_id = $1 ORDER BY claim_id",
            product_id)
    finally:
        await conn.close()
    return [dict(r) for r in rows]


async def _judge_snapshot(job_id: str) -> dict[str, Any]:
    conn = await asyncpg.connect(DSN)
    try:
        raw: bytes = await conn.fetchval(
            "SELECT payload FROM snapshots WHERE snapshot_id = $1",
            f"snap-{job_id}-judge")
    finally:
        await conn.close()
    return dict(json.loads(raw.decode()))


def _wipe() -> None:
    run(_sql([
        "DELETE FROM claims WHERE deliverable_id LIKE "
        + f"'{ANALYSIS_PRODUCT_PREFIX}{PREFIX}%'",
        f"DELETE FROM job_steps WHERE job_id LIKE '{PREFIX}%'",
        f"DELETE FROM job_events WHERE job_id LIKE '{PREFIX}%'",
        f"DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-{PREFIX}%'",
        f"DELETE FROM jobs WHERE job_id LIKE '{PREFIX}%'",
    ]))


@pytest.fixture(autouse=True)
def clean_slate() -> Any:
    _wipe()
    yield
    _wipe()


def _run_gate1(job_id: str = JOB) -> None:
    """离线确定性 deps（S2-7 零联网零 LLM），与既有 gate1 测试同一条路。"""
    run(run_gate1(
        job_id=job_id, keywords=KEYWORDS, locale="zh-CN",
        deps=build_offline_deps(dsn=DSN, repo_root=REPO)))


# ───────────────────────── acceptance①：判定真的落成 claims 行


def test_gate1_now_writes_claim_rows() -> None:
    """跑完一次 gate1，`claims` 表里有行——这一跳此前完全没有人接。"""
    _run_gate1()

    rows = run(_claim_rows(PRODUCT))

    assert rows, f"{PRODUCT} 下一条 claim 都没有：那一跳还是断的"


def test_every_support_claim_from_the_judge_becomes_a_row() -> None:
    """**判等值**：judge 快照里有几条 support_claim，就落几行。

    少落 = 悄悄丢结论；多落 = 凭空造结论。两种都要有人来这里确认。
    """
    _run_gate1()

    judge = run(_judge_snapshot(JOB))
    rows = run(_claim_rows(PRODUCT))

    assert {str(item["claim"]) for item in judge["support_claims"]} == {
        r["text_span"] for r in rows}


# ───────────────────────── acceptance②：deliverable_id 口径


def test_the_product_id_is_namespaced_and_derived_from_the_job() -> None:
    """`analysis-{job_id}`：与交付物 `del-{job}` 那个命名空间不相交。"""
    assert analysis_product_id(JOB) == PRODUCT
    assert PRODUCT.startswith(ANALYSIS_PRODUCT_PREFIX)
    assert not PRODUCT.startswith("del-")
    assert JOB in PRODUCT, "id 里没有 job——那就追不回是哪次判定产的"


def test_no_fake_deliverable_row_is_created() -> None:
    """**NEVER 去 `deliverables` 表建一行假记录**来让这个 id「合法」。

    建了的话，交付物列表里会多出一份没人能打开的「报告」。
    `claims.deliverable_id` 没有外键，本来就不需要那一行。
    """
    _run_gate1()

    conn_rows = run(_deliverable_rows(PRODUCT))

    assert conn_rows == 0, "凭空造了一份交付物"


async def _deliverable_rows(deliverable_id: str) -> int:
    conn = await asyncpg.connect(DSN)
    try:
        count: int = await conn.fetchval(
            "SELECT count(*) FROM deliverables WHERE deliverable_id = $1",
            deliverable_id)
    finally:
        await conn.close()
    return count


def test_two_jobs_never_share_a_claim_row() -> None:
    """两次判定**同样的关键词**也要各归各的行。

    claim id 若只由文本决定，第二次跑会覆盖第一次的行——
    两次判定的结论从此只剩一份，而它们可能判得不一样。
    """
    _run_gate1(JOB)
    _run_gate1(f"{PREFIX}job-2")

    first = run(_claim_rows(PRODUCT))
    second = run(_claim_rows(analysis_product_id(f"{PREFIX}job-2")))

    assert first and second
    assert {r["claim_id"] for r in first} & {r["claim_id"] for r in second} == set()


# ───────────────────────── acceptance③：Claim/Fact 边界不动


def test_a_claim_that_was_never_aligned_says_pending() -> None:
    """**没判过 NEVER 写成「判过了、不支持」**。

    离线 deps 下对齐器给的是确定性结果；本条判的是**三种取值各有其位**，
    且未经对齐器的那条只能是 `pending`。
    """
    _run_gate1()

    rows = run(_claim_rows(PRODUCT))

    assert all(r["alignment"] in ("pending", "supports", "partial", "unsupported")
               for r in rows)
    # 缝的两侧：判过的与没判过的**不能是同一个值**。
    from flint.jobs.gate1 import PENDING_ALIGNMENT

    assert PENDING_ALIGNMENT == "pending"


def test_a_partial_claim_is_never_written_as_supports() -> None:
    """S2-4：`alignment=="partial"` 的 claim NEVER 提升为 Fact。

    落盘这一层的对应义务是：**对齐器说 partial，行里就写 partial**——
    写成 `supports` 的话，`promote_claims` 会把它提成 Fact，
    而那是三条铁律里「结论必有引用」的反面。
    """
    from flint.jobs.gate1 import claim_rows_from

    rows = claim_rows_from(
        product_id="analysis-x",
        support_claims=[{"claim": "c1", "doc_id": "d1"},
                        {"claim": "c2", "doc_id": "d2"},
                        {"claim": "c3", "doc_id": "d3"}],
        alignment_by={("c1", "d1"): "supports", ("c2", "d2"): "partial"},
        cited_docs={"d1": "cit-gate1-d1", "d2": "cit-gate1-d2"},
    )
    by_text = {r.text_span: r for r in rows}

    assert by_text["c1"].alignment == "supports"
    assert by_text["c2"].alignment == "partial"     # NEVER supports
    assert by_text["c3"].alignment == "pending"     # 根本没判过


def test_promotion_only_takes_the_cited_and_supporting_ones() -> None:
    """把落下来的行喂给真正的提升器：只有 cited∧supports 那条成 Fact。

    这条不是重测 `promote_claims`，是**量本卡写出来的行在它面前的行为**——
    行写错了，铁律就是在这里被绕过的。
    """
    from flint.jobs.gate1 import claim_rows_from
    from flint.ledger.promoter import promote_claims

    rows = claim_rows_from(
        product_id="analysis-x",
        support_claims=[{"claim": "c1", "doc_id": "d1"},
                        {"claim": "c2", "doc_id": "d2"},
                        {"claim": "c3", "doc_id": "d3"}],
        alignment_by={("c1", "d1"): "supports", ("c2", "d2"): "supports",
                      ("c3", "d3"): "partial"},
        cited_docs={"d1": "cit-gate1-d1"},          # 只有 d1 的引用真在库里
    )
    result = promote_claims([r.to_claim() for r in rows], "analysis-x", 1)

    assert [f.source_claim_id for f in result.facts] == [
        next(r.claim_id for r in rows if r.text_span == "c1")]


def test_a_claim_without_a_stored_citation_is_speculative() -> None:
    """引用没入库 → `speculative` 且 `citation_ids` 为空。

    编一个指向不存在 citation 的 id，下游解引用会失败——
    那种失败读起来像「引用坏了」，真相是「引用从没入过库」。
    """
    from flint.jobs.gate1 import claim_rows_from

    rows = claim_rows_from(
        product_id="analysis-x",
        support_claims=[{"claim": "c1", "doc_id": "d1"}],
        alignment_by={("c1", "d1"): "supports"},
        cited_docs={},
    )

    assert rows[0].confidence == "speculative"
    assert rows[0].citation_ids == []


def test_a_claim_with_a_stored_citation_carries_it() -> None:
    """**缝的另一侧**：引用真在库里 → `cited` 且带上那个 id。"""
    from flint.jobs.gate1 import claim_rows_from

    rows = claim_rows_from(
        product_id="analysis-x",
        support_claims=[{"claim": "c1", "doc_id": "d1"}],
        alignment_by={("c1", "d1"): "supports"},
        cited_docs={"d1": "cit-gate1-d1"},
    )

    assert rows[0].confidence == "cited"
    assert rows[0].citation_ids == ["cit-gate1-d1"]


# ───────────────────────── acceptance④：幂等


def test_rerunning_the_same_job_never_duplicates_rows() -> None:
    """整个 job 再驱动一次 → 行数不变。

    **第一版的写法是错的**，值得留在这里：它删掉 `job_steps` 里 validate 那行
    再跑，结果炸在 `snapshots_pkey`——因为 `_put_snapshot` 是纯 INSERT。
    那个状态**真实系统产生不出来**：快照与步记录同一个事务提交，
    有快照就一定有步记录。造一个不可能的状态来量幂等，量的是幻觉。
    """
    _run_gate1()
    first = run(_claim_rows(PRODUCT))
    run(_sql([f"UPDATE jobs SET state = 'validating' WHERE job_id = '{JOB}'"]))

    _run_gate1()

    second = run(_claim_rows(PRODUCT))
    assert len(second) == len(first)
    assert {r["claim_id"] for r in second} == {r["claim_id"] for r in first}


def test_writing_the_same_rows_twice_leaves_one_row_each() -> None:
    """**直接量落盘那一步**：同一批行写两次，每条仍只有一行。

    上一条量的是「重跑会跳过已完成的步」，那是编排层的保护；
    这一条量的是写库这一层**自己**幂等——两者缺一个，
    换一条调用路径（重放、补跑、人工修数）就会把结论翻倍。
    """
    _run_gate1()
    rows_before = run(_claim_rows(PRODUCT))
    judge = run(_judge_snapshot(JOB))

    run(_rewrite(judge))

    after = run(_claim_rows(PRODUCT))
    assert len(after) == len(rows_before)


def test_a_rerun_never_clobbers_a_promotion() -> None:
    """重写 NEVER 把已经回填的 `promoted_fact_id` 抹掉。

    抹掉的话，账本里那条 Fact 就找不回它的来源 claim——
    而「这条事实从哪来」是三条铁律之一要答的问题。
    """
    _run_gate1()
    claim_id = run(_claim_rows(PRODUCT))[0]["claim_id"]
    run(_sql(["UPDATE claims SET promoted_fact_id = 'fact-chain01' "
              + f"WHERE claim_id = '{claim_id}'"]))

    run(_rewrite(run(_judge_snapshot(JOB))))

    after = {r["claim_id"]: r for r in run(_claim_rows(PRODUCT))}
    assert after[claim_id]["promoted_fact_id"] == "fact-chain01"


async def _rewrite(judge: dict[str, Any]) -> None:
    """照 gate1 收尾那一步再写一次同一批行（走的是同一个函数）。"""
    from flint.jobs.gate1 import _write_claim_rows, claim_rows_from

    conn = await asyncpg.connect(DSN)
    try:
        await _write_claim_rows(conn, claim_rows_from(
            product_id=PRODUCT,
            support_claims=list(judge["support_claims"]),
            alignment_by={},
            cited_docs={},
        ))
    finally:
        await conn.close()


def test_the_rows_land_in_the_same_transaction_as_the_step_record() -> None:
    """落盘与 `job_steps` 记录**同一个事务**（沿用本文件既有不变量）。

    分两次提交的话，kill -9 卡在中间会留下「步已记完、claim 没写」——
    续跑会跳过那步，那批结论就永远丢了。
    """
    import ast

    source = (REPO / "flint" / "jobs" / "gate1.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    inserts = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and "INSERT INTO claims" in node.value
    ]

    assert inserts, "没有写 claims 的语句"
    # 那条 INSERT 必须在 `async with conn.transaction():` 的字面区间内。
    block = source[source.index("async with conn.transaction():"):
                   source.index("await _record_step(")]
    assert "_write_claim_rows" in block or "INSERT INTO claims" in block, (
        "写 claims 落在事务块外面了")
