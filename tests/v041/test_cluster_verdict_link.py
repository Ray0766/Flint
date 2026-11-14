"""PERSIST-04：cluster→判定关系表——分析屏永远说「还没判定」的根因。

## 本卡治的那一屏

`cluster_verdicts` 表不存在（`DEC-048` 八张里的最后一张）。判定按 **job 键**落在
`snapshots['snap-{job_id}-verdict']`，而 `Job` 没有 `cluster` 字段、
`jobs` 表也没有 `cluster_id`——**从一个热点出发无从查起**。
所以热点分析屏对每一个热点永远只会说「还没有过 Gate① 判定」。

## 关系是**一对多**，一对一的写法会当场丢信息

一个 combo 主题由 **2~5 张卡**凑成（`Origin.payload = {card_ids, hypothesis}`），
每张卡背后是一个热点簇。「这次判定判的是哪个 cluster」的诚实答案是**一组**。

一对一只会记住其中一个热点，而用户从另外几个点进去仍看到「还没有判定」——
**而那次判定明明也是为它跑的**。

## `cluster_id` 怎么进到作业里（本卡最实的一段）

开工前实读的提交链路里**没有任何一段带 `cluster_id`**：

```
AnalysisSubmitRequest  {keywords, locale, budget_cny, topic_id?}
analysis.py payload    {"project_id", "keywords", "locale"}
_gate1_handler         只取 keywords 与 locale
run_gate1(job_id, keywords, locale, deps)
```

**所以先建表是错的**——那会得到一张永远空着的表和一屏没变的界面。
本卡走的是「收尾时从 topic 反查」：把**已经存在**的 `topic_id` 放进 payload，
`run_gate1` 收尾时沿四跳查回热点簇：

```
topic.seed_id → topic_seeds.origin_id → origins.payload->'card_ids'
              → evidence_cards.cluster_id
```

**查不到就不写行**。不带 `topic_id` 的旧路径、非 combo 的 origin（`idea` /
`domain` / `competitor` / `document` 的 payload 里**没有** `card_ids`）
都照旧不产生关系行，分析屏对那些热点仍然如实说「还没有判定」。
**NEVER 为了让表不空而猜一个 cluster**——猜错时用户看到的是**另一个热点的判定**，
并会把它引进计划书（`DEC-044` 原话，也是「猜 job id 那条路」当初被判死的理由）。

## 同一个事务

关系行与判定快照**在同一个事务里**写。分两次提交的话，`kill -9` 卡在中间会留下
「判定落了、关系没写」，而续跑会跳过那一步——那次判定就永远查不回来了
（`CHAIN-01` 在同一处用的是同一条理由）。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)
PREFIX = "persist04-"
CLUSTERS = (f"{PREFIX}c1", f"{PREFIX}c2")
CARDS = (f"{PREFIX}card1", f"{PREFIX}card2")
ORIGIN = f"{PREFIX}origin"
SEED = f"{PREFIX}seed"
TOPIC = f"{PREFIX}topic"
JOB = f"{PREFIX}job"
VECTOR = "[" + ",".join(["0"] * 1024) + "]"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(DSN)


async def _seed_chain(*, kind: str = "combo", card_ids: list[str] | None = None) -> None:
    """种一条完整的四跳链：clusters → evidence_cards → origins → topic_seeds → topics。"""
    conn = await _conn()
    try:
        async with conn.transaction():
            await conn.execute("DELETE FROM cluster_verdicts")
            category = await conn.fetchval(
                "SELECT category_id FROM categories LIMIT 1")
            for cluster in CLUSTERS:
                await conn.execute(
                    "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                    "centroid, status, first_seen, last_active) "
                    "VALUES ($1, $2, $3, $4, 'active', $5, $5) "
                    "ON CONFLICT (cluster_id) DO NOTHING",
                    cluster, f"热点-{cluster}", category, VECTOR, NOW.date())
            for card, cluster in zip(CARDS, CLUSTERS, strict=True):
                await conn.execute(
                    "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids, "
                    "flags, top_links) VALUES ($1, $2, $3::jsonb, $4::jsonb, $5::jsonb) "
                    "ON CONFLICT (card_id) DO UPDATE SET cluster_id = EXCLUDED.cluster_id",
                    card, cluster, "[]", "{}", "[]")
            payload = {"hypothesis": "两个热点撑同一个假设"}
            if card_ids is not None:
                payload["card_ids"] = card_ids
            await conn.execute(
                "INSERT INTO origins (origin_id, kind, owner, payload, created_at) "
                "VALUES ($1, $2, $3::jsonb, $4::jsonb, $5) "
                "ON CONFLICT (origin_id) DO UPDATE SET kind = EXCLUDED.kind, "
                "payload = EXCLUDED.payload",
                ORIGIN, kind, json.dumps({"kind": "user", "id": "demo-user"}),
                json.dumps(payload, ensure_ascii=False), NOW)
            await conn.execute(
                "INSERT INTO topic_seeds (seed_id, origin_id, keywords, hypothesis, "
                "context_text) VALUES ($1, $2, $3::jsonb, $4, $5) "
                "ON CONFLICT (seed_id) DO UPDATE SET origin_id = EXCLUDED.origin_id",
                SEED, ORIGIN, '["脑机接口"]', "两个热点撑同一个假设", "")
            # 关系表的 `job_id` 有外键指向 `jobs`——**孤儿关系行进不来**，
            # 所以判据里也要有一条真的作业行。种三个 id：本卡用到的那三个。
            for job in (JOB, f"{JOB}-old", f"{JOB}-new"):
                await conn.execute(
                    "INSERT INTO jobs (job_id, kind, project_id, owner_scope, state, "
                    "progress, budget, cost_accum, cancel_requested, initiated_by, "
                    "created_at, updated_at) "
                    "VALUES ($1, 'gate1_analysis', NULL, $2::jsonb, 'done', 100, 0, 0, "
                    "false, 'demo-user', $3, $3) "
                    "ON CONFLICT (job_id) DO NOTHING",
                    job, json.dumps({"kind": "user", "id": "demo-user"}), NOW)
            await conn.execute(
                "INSERT INTO topics (topic_id, seed_id, one_liner, target_user_tag, "
                "form_factor_tag, why_now, keyword_mapping, embedding) "
                "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8) "
                "ON CONFLICT (topic_id) DO UPDATE SET seed_id = EXCLUDED.seed_id",
                TOPIC, SEED, "一句话", "tag", "form", "{}", "{}", VECTOR)
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _clean() -> Any:
    run(_wipe())
    yield
    run(_wipe())


async def _wipe() -> None:
    conn = await _conn()
    try:
        await conn.execute("DELETE FROM cluster_verdicts")
    finally:
        await conn.close()


# ───────────────────────── 一、表与迁移


def test_the_cluster_verdicts_table_exists_now() -> None:
    """`DEC-048` 八张里的最后一张。实查 `pg_tables`。"""
    async def _probe() -> Any:
        conn = await _conn()
        try:
            return await conn.fetchval(
                "SELECT to_regclass('public.cluster_verdicts') IS NOT NULL")
        finally:
            await conn.close()

    assert run(_probe()) is True


def test_the_migration_leaves_no_gap() -> None:
    """号段不许有洞（本批 rules）。**不留号**——`PERSIST-02` 被阻不影响号段连续。"""
    versions = sorted(
        (REPO / "migrations" / "versions").glob("[0-9][0-9][0-9][0-9]_*.py"))
    numbers = [int(p.name[:4]) for p in versions]

    assert numbers == list(range(1, len(numbers) + 1)), f"号有洞或重号：{numbers}"


def test_the_contract_was_not_touched() -> None:
    """`DEC-044` 有一条**硬**的：`contracts/` 一字不动。

    `Job` 无 `cluster` 字段这件事保持原样，对应关系**落在关系表里**。
    不写这条判据的话，最省事的实现就是给 `Job` 加个字段——
    而那是 `S2-1` 判死的动作。
    """
    for name in ("models.py", "protocols.py"):
        text = (REPO / "contracts" / name).read_text(encoding="utf-8")
        assert "cluster_id" not in text.split("class Job:")[-1].split("\n\n")[0], (
            f"contracts/{name} 的 Job 上出现了 cluster 字段")

    async def _columns() -> list[str]:
        conn = await _conn()
        try:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'jobs'")
        finally:
            await conn.close()
        return [r["column_name"] for r in rows]

    assert "cluster_id" not in run(_columns()), "jobs 表上加了 cluster_id"


# ───────────────────────── 二、写：收尾时沿四跳查回热点簇


def _resolve() -> Any:
    from flint.jobs.cluster_verdict import clusters_for_topic

    return clusters_for_topic


def test_the_four_hop_chain_resolves_every_cluster_of_a_combo() -> None:
    """**一对多**：combo 的两张卡各自的热点簇都要查出来。

    只回第一个的话，用户从第二个热点点进去仍看到「还没有判定」——
    而那次判定明明也是为它跑的。
    """
    run(_seed_chain(card_ids=list(CARDS)))

    async def _go() -> list[str]:
        conn = await _conn()
        try:
            return await _resolve()(conn, TOPIC)
        finally:
            await conn.close()

    assert sorted(run(_go())) == sorted(CLUSTERS)


def test_a_non_combo_origin_resolves_to_nothing_instead_of_guessing() -> None:
    """`idea` / `domain` / `competitor` / `document` 的 payload 里**没有** `card_ids`。

    查不到就是查不到——**NEVER 回退去猜一个 cluster**。
    猜错时用户看到的是另一个热点的判定，并会把它引进计划书。
    """
    run(_seed_chain(kind="idea", card_ids=None))

    async def _go() -> list[str]:
        conn = await _conn()
        try:
            return await _resolve()(conn, TOPIC)
        finally:
            await conn.close()

    assert run(_go()) == []


def test_an_unknown_topic_resolves_to_nothing() -> None:
    """主题不在库里 → 空。**NEVER 抛**：那会把一次判定整个跑失败，
    而关系写不下只是「查不回来」，判定本身是有效的。"""
    async def _go() -> list[str]:
        conn = await _conn()
        try:
            return await _resolve()(conn, "no-such-topic")
        finally:
            await conn.close()

    assert run(_go()) == []


def test_recording_links_is_idempotent() -> None:
    """同一个 job 重跑（续跑）NEVER 写出第二行。"""
    from flint.jobs.cluster_verdict import record_cluster_verdicts

    run(_seed_chain(card_ids=list(CARDS)))

    async def _go() -> int:
        conn = await _conn()
        try:
            for _ in range(2):
                await record_cluster_verdicts(
                    conn, job_id=JOB, cluster_ids=list(CLUSTERS), now=NOW)
            return int(await conn.fetchval(
                "SELECT count(*) FROM cluster_verdicts WHERE job_id = $1", JOB))
        finally:
            await conn.close()

    assert run(_go()) == 2, "两个 cluster 各一行，重跑不该翻倍"


# ───────────────────────── 三、读：按 cluster 查最新一条


def test_the_latest_verdict_wins_when_a_cluster_was_judged_twice() -> None:
    """一个热点多次判定时**取最新一条**（`DEC-044` 定的默认）。

    NEVER 随机显示其中一条：同一个热点每次点开显示不同的判定，
    等于那个判定不再可被引用——而「结论必有引用」是第一条铁律。
    """
    from flint.jobs.cluster_verdict import record_cluster_verdicts
    from flint.repo.cluster_verdict import latest_verdict_job

    run(_seed_chain(card_ids=list(CARDS)))

    async def _go() -> str | None:
        conn = await _conn()
        try:
            await record_cluster_verdicts(
                conn, job_id=f"{JOB}-old", cluster_ids=[CLUSTERS[0]], now=NOW)
            await record_cluster_verdicts(
                conn, job_id=f"{JOB}-new", cluster_ids=[CLUSTERS[0]],
                now=NOW.replace(hour=13))
            return await latest_verdict_job(conn, CLUSTERS[0])
        finally:
            await conn.close()

    assert run(_go()) == f"{JOB}-new"


def test_a_cluster_never_judged_reads_as_none_not_as_an_error() -> None:
    """**四态不倒**：没判过仍是「未判定」，NEVER 与「读失败」合并。"""
    from flint.repo.cluster_verdict import latest_verdict_job

    async def _go() -> str | None:
        conn = await _conn()
        try:
            return await latest_verdict_job(conn, "never-judged")
        finally:
            await conn.close()

    assert run(_go()) is None


# ───────────────────────── 四、端点：按 cluster 取判定


def _client() -> Any:
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    return TestClient(create_app(dsn=DSN), raise_server_exceptions=False)


async def _put_verdict_snapshot(job_id: str, verdict: str) -> None:
    conn = await _conn()
    try:
        await conn.execute(
            "INSERT INTO snapshots (snapshot_id, payload, created_at) "
            "VALUES ($1, $2, $3) ON CONFLICT (snapshot_id) DO UPDATE "
            "SET payload = EXCLUDED.payload",
            f"snap-{job_id}-verdict",
            json.dumps({"verdict": verdict}, ensure_ascii=False).encode("utf-8"),
            NOW)
    finally:
        await conn.close()


def test_the_endpoint_answers_with_the_latest_verdict_for_a_cluster() -> None:
    """`GET /clusters/{id}/verdict`——**`HOTSPOT-03` 那张单要的就是这条端点**。

    那张单当初的结论是「NEVER 自己补一个 cluster 键端点」，因为**没有真相可查**。
    `DEC-044` 之后前提变了：关系表就是那个真相，所以现在补它不是自作主张。
    """
    from flint.jobs.cluster_verdict import record_cluster_verdicts

    run(_seed_chain(card_ids=list(CARDS)))
    run(_put_verdict_snapshot(JOB, "B"))

    async def _link() -> None:
        conn = await _conn()
        try:
            await record_cluster_verdicts(
                conn, job_id=JOB, cluster_ids=[CLUSTERS[0]], now=NOW)
        finally:
            await conn.close()

    run(_link())
    got = _client().get(f"/clusters/{CLUSTERS[0]}/verdict")

    assert got.status_code == 200, got.text
    body = got.json()
    assert body["job_id"] == JOB
    assert body["verdict"]["verdict"] == "B"


def test_a_cluster_without_a_verdict_says_so_instead_of_pretending() -> None:
    """没判过 → **404 + 有 `code` 的错误体**，NEVER 回一个空判定。

    回空判定的话前端分不出「没判过」与「判了但内容是空的」，
    而 `DESIGN-03` 的四态口径正是为此立的。
    """
    got = _client().get("/clusters/never-judged-cluster/verdict")

    assert got.status_code == 404
    assert got.json()["code"] == "NOT_FOUND"


def test_the_job_keyed_endpoint_still_works() -> None:
    """既有 `GET /jobs/{id}/verdict` **一行没动**——本卡是加一条读法，不是换一条。

    换掉的话，作业详情屏那条路会当场断，而它与热点那条路服务的是两种问法。
    """
    run(_put_verdict_snapshot(JOB, "A"))

    got = _client().get(f"/jobs/{JOB}/verdict")

    assert got.status_code == 200, got.text
    assert got.json()["verdict"]["verdict"] == "A"


# ───────────────────────── 五、提交段：`topic_id` 进 payload


def test_the_submit_payload_now_carries_the_topic_id() -> None:
    """**这是「数据从哪来」那一半**：不放进 payload 的话，
    `run_gate1` 收尾时手上没有任何可以反查的东西。

    判的是源码里那一行，因为提交端点要真起作业才跑得到——
    而本卡不需要为了这一条去起一个 worker。
    """
    source = (REPO / "flint" / "api" / "analysis.py").read_text(encoding="utf-8")
    marker = source.split('kind="gate1_analysis"')[1].split("budget=")[0]

    assert '"topic_id"' in marker, "gate1 作业的 payload 里没有 topic_id"


def test_the_handler_passes_the_topic_id_through() -> None:
    """`_gate1_handler` 把它取出来交给 `run_gate1`。

    payload 里有、handler 不取的话，链路在这里静静地断掉——
    而表照样建着、判据照样绿。
    """
    source = (REPO / "flint" / "jobs" / "worker_main.py").read_text(encoding="utf-8")
    body = source.split("def _gate1_handler")[1].split("def _daily_ingest_handler")[0]

    assert "topic_id" in body, "_gate1_handler 没把 topic_id 传下去"
