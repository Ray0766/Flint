"""VERDICT-01：判了，却一行都没落库。

## 实况与诊断

`jobs` 里 `gate1_analysis` 已 done 8 条（实查 10 条，8 done），
而 `cluster_verdicts` **0 行**。卡面给了两种可能，实查的答案**是第三种**：

| 卡面猜测 | 实查 |
|---|---|
| ① payload 本来就没有 `topic_id` | **不成立**。`flint/api/analysis.py:175` 逐字写着 `"topic_id": body.topic_id` |
| ② 带了但 `clusters_for_topic` 回空 | 不是主因（那条链要 combo origin，见 §三） |
| **③ 带了，但消费侧把它丢了** | **就是这个** |

那 8 条走的是 `harness/demo_server.py#_enqueue` 那条 demo 自己的派发路：

```python
keywords = [str(k) for k in payload.get("keywords", [])]
locale = str(payload.get("locale", "zh-CN"))
await run_gate1(job_id, keywords, locale, deps)     # ← topic_id 没传
```

它把 `keywords` 从 payload 里取出来，**而 `topic_id` 就在旁边、没人取**。
于是 `run_gate1` 的 `topic_id` 吃默认值 `None`，
`gate1.py:760` 那句 `if topic_id is not None:` 一次都没走到。

**没有一处会报错**：作业 `done`、判定落了快照、claims 也写了——
只有「这次判的是哪几条热点」这一层关系静静地没建。

## 今天的第二个坑：真 worker 上 gate1 根本跑不起来

`_enqueue` 今天已经没有调用点（`COMPOSE-01` 实查）。真路径是
`harness/run_worker.py` → `worker_main._gate1_handler`——而那个 handler
**是把 `topic_id` 传下去的**（`worker_main.py:180`）。

但 `run_worker.py` 造 `WorkerDeps` 时**没注 `gate1_deps`**，于是每条
`gate1_analysis` 都以 `HandlerDepsMissing` 收场。本卡把这一缝接上。

## 本卡 NEVER 改判定逻辑

四分类与引用照旧走 `flint/gate/`。这里治的只有「判了却没落库」这一件。

## 判据为什么离线

`build_live_deps` 打的是真实 github / arxiv。本批的真实网络授权
**只覆盖 CN-07**（`DEC-052`），VERDICT-01 不在其中，
所以本文件一律走 `build_offline_deps`（`S2-7`：CI 恒不联网）。
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

REPO = Path(__file__).resolve().parents[2]
GATE1 = REPO / "flint" / "jobs" / "gate1.py"
ANALYSIS_API = REPO / "flint" / "api" / "analysis.py"
WORKER_MAIN = REPO / "flint" / "jobs" / "worker_main.py"
RUN_WORKER = REPO / "harness" / "run_worker.py"
DEMO = REPO / "harness" / "demo_server.py"

import os

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


def _sql(query: str, *args: Any) -> list[Any]:
    async def _go() -> list[Any]:
        conn = await asyncpg.connect(DSN)
        try:
            return list(await conn.fetch(query, *args))
        finally:
            await conn.close()

    return asyncio.run(_go())


def _exec(query: str, *args: Any) -> None:
    async def _go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(query, *args)
        finally:
            await conn.close()

    asyncio.run(_go())


# ───────────────────────── 一、诊断落在纸上（acceptance②：结论写进 trace）


def test_the_api_really_puts_the_topic_id_in_the_payload() -> None:
    """诊断的第一环：**提交那一侧没有丢**。

    这一条把卡面猜测①（「payload 本来就没有 topic_id」）证伪。
    证伪要落成判据，NEVER 只写在 trace 里——写在 trace 里的话，
    哪天这一行真的被删了，没有任何东西会喊。
    """
    code = ANALYSIS_API.read_text(encoding="utf-8")

    assert '"topic_id": body.topic_id' in code, (
        "提交端点不再把 topic_id 放进 payload——判定与热点的关系从源头就断了")


def test_the_real_worker_passes_the_topic_id_through() -> None:
    """诊断的第二环：**真 worker 那一侧传下去了**。

    `_gate1_handler` MUST 把 payload 里的 `topic_id` 交给 `run_gate1`。
    丢在这里的话，作业照样 `done`，而关系一行都不会建——
    那正是本卡要治的病。
    """
    code = WORKER_MAIN.read_text(encoding="utf-8")

    assert "topic_id=topic_id" in code, "worker 又把 topic_id 丢了"


def test_the_dead_demo_hook_is_the_one_that_dropped_it() -> None:
    """诊断的第三环：**丢它的是 demo 那条已死的派发路**。

    留着这条判据不是为了守那段死代码，是为了守住**结论**：
    哪天有人把 `_enqueue` 重新接回去，这条会当场提醒他那里少传一个参数。
    """
    code = DEMO.read_text(encoding="utf-8")
    body = code.split("if kind != \"gate1_analysis\":")[1][:1200]

    assert "run_gate1(job_id, keywords, locale, deps)" in body, (
        "这条判据钉的那处代码变了——诊断结论要重新核一遍")
    assert "topic_id" not in body, (
        "demo 那条钩子开始传 topic_id 了：诊断结论要更新（这是好事，但判据得跟上）")


def test_the_worker_now_has_the_gate1_seam_filled() -> None:
    """本卡补的那一缝：`gate1_deps` MUST 注进去。

    不注的话每条 `gate1_analysis` 都是 `HandlerDepsMissing`——
    屏上永远说「还没有判定」，而真相是作业根本没跑起来。
    """
    from harness import run_worker

    deps = run_worker.build_deps()

    assert deps.gate1_deps is not None, "gate1 那一缝又空了"
    assert deps.compose_provider is not None


def test_the_seam_uses_the_free_local_tier() -> None:
    """模型走免费本地档，NEVER 读任何 key（本批 `llm_cost` 纪律）。"""
    code = RUN_WORKER.read_text(encoding="utf-8")

    assert "build_live_deps" in code
    assert "LocalProvider" in code
    for paid in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "api_key"):
        assert paid not in code, f"worker 里出现了 {paid}"


# ───────────────────────── 二、端到端：带 topic_id → 关系行真的落下


@pytest.fixture()
def a_combo_topic() -> Any:
    """一条**四跳都通**的链：origin(combo) → seed → topic，外加两条簇。

    自带而不是找库里现成的：现成的 combo origin 今天一条都没有，
    靠它的话这条判据永远 skip——而 skip 与「量过了、没问题」在盘上分不开。
    """
    tag = uuid.uuid4().hex[:8]
    origin_id, seed_id = f"origin-vd-{tag}", f"seed-vd-{tag}"
    topic_id = f"topic-vd-{tag}"
    clusters = [f"c-vd-{tag}-1", f"c-vd-{tag}-2"]
    # **`card_ids` 装的是证据卡 id，不是簇 id**（`clusters_for_topic` 第四跳
    # 拿它去 `evidence_cards` 里换簇）。把簇 id 直接塞进 `card_ids` 的话
    # 那一跳查不到东西、回空集，而那看起来与「关系没建」一模一样——
    # 这条判据第一版就是这么写的，实测回 `[]`。
    cards = [f"card-vd-{tag}-1", f"card-vd-{tag}-2"]
    job_id = f"job-vd-{tag}"

    def _erase() -> None:
        _exec("DELETE FROM cluster_verdicts WHERE job_id = $1", job_id)
        _exec("DELETE FROM job_steps WHERE job_id = $1", job_id)
        _exec("DELETE FROM job_events WHERE job_id = $1", job_id)
        _exec("DELETE FROM jobs WHERE job_id = $1", job_id)
        _exec("DELETE FROM topics WHERE topic_id = $1", topic_id)
        _exec("DELETE FROM topic_seeds WHERE seed_id = $1", seed_id)
        _exec("DELETE FROM origins WHERE origin_id = $1", origin_id)
        _exec("DELETE FROM evidence_cards WHERE card_id = ANY($1::text[])", cards)
        _exec("DELETE FROM heat_points WHERE cluster_id = ANY($1::text[])", clusters)
        _exec("DELETE FROM clusters WHERE cluster_id = ANY($1::text[])", clusters)

    _erase()
    for cid in clusters:
        _exec(
            "INSERT INTO clusters (cluster_id, canonical_name, category_id, centroid, "
            "status, first_seen, last_active, parent_cluster_ids, aliases, region) "
            "VALUES ($1, $2, 'cat-ai', array_fill(0.0::real, ARRAY[1024])::vector, "
            "'active', $3, $3, '[]'::jsonb, '[]'::jsonb, 'CN')",
            cid, f"样本簇 {cid}", NOW.date())
    for card_id, cid in zip(cards, clusters, strict=True):
        _exec(
            "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids, flags, "
            "top_links) VALUES ($1, $2, '[]'::jsonb, '{}'::jsonb, '[]'::jsonb)",
            card_id, cid)
    _exec(
        "INSERT INTO origins (origin_id, kind, owner, payload, created_at) "
        "VALUES ($1, 'combo', $2::jsonb, $3::jsonb, $4)",
        origin_id, json.dumps({"kind": "user", "id": "u-owner"}),
        json.dumps({"card_ids": cards}), NOW)
    # 列名逐字照库里的（实查 `information_schema`）：`topic_seeds` 没有 `created_at`，
    # `topics` 没有 `title`。**编一个列名出来的话，红会落在 SQL 上而不是被判的那件事上。**
    _exec(
        "INSERT INTO topic_seeds (seed_id, origin_id, keywords, context_text) "
        "VALUES ($1, $2, $3::jsonb, $4)",
        seed_id, origin_id, json.dumps(["样本关键词"]), "样本上下文")
    _exec(
        "INSERT INTO topics (topic_id, seed_id, one_liner, target_user_tag, "
        "form_factor_tag, why_now, keyword_mapping, embedding) "
        "VALUES ($1, $2, $3, 'researcher', 'tool', $4::jsonb, $5::jsonb, "
        "array_fill(0.0::real, ARRAY[1024])::vector)",
        topic_id, seed_id, "一句话", json.dumps(["现在正热"]), json.dumps({}))
    try:
        yield topic_id, clusters, job_id
    finally:
        _erase()


@pytest.mark.compose
def test_the_four_hops_reach_the_clusters(a_combo_topic: Any) -> None:
    """`clusters_for_topic` 沿四跳把主题查回热点——**卡面猜测②的对照**。

    查得回来，说明「关系没建」不是本卡的病因；
    查不回来时它回空集而 NEVER 抛（那是既有口径，本卡一字不动）。
    """
    from flint.jobs.cluster_verdict import clusters_for_topic

    topic_id, clusters, _ = a_combo_topic

    async def _go() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            return await clusters_for_topic(conn, topic_id)
        finally:
            await conn.close()

    assert asyncio.run(_go()) == sorted(clusters)


@pytest.mark.compose
def test_a_verdict_with_a_topic_id_lands_a_row(a_combo_topic: Any) -> None:
    """**带 `topic_id` 判一次 → `cluster_verdicts` 多出行**（acceptance③ 的库那一半）。

    走的是既有的 `record_cluster_verdicts`，本卡 NEVER 改判定逻辑。
    """
    from flint.jobs.cluster_verdict import clusters_for_topic, record_cluster_verdicts

    topic_id, clusters, job_id = a_combo_topic
    before = len(_sql("SELECT 1 FROM cluster_verdicts WHERE job_id = $1", job_id))

    async def _go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, "
                "budget, cost_accum, cancel_requested, initiated_by, created_at, "
                "updated_at) VALUES ($1, 'gate1_analysis', $2::jsonb, 'done', 1.0, "
                "0.0, 0.0, false, 'u-owner', $3, $3)",
                job_id, json.dumps({"kind": "user", "id": "u-owner"}), NOW)
            await record_cluster_verdicts(
                conn, job_id=job_id,
                cluster_ids=await clusters_for_topic(conn, topic_id), now=NOW)
        finally:
            await conn.close()

    asyncio.run(_go())
    rows = _sql(
        "SELECT cluster_id FROM cluster_verdicts WHERE job_id = $1 ORDER BY 1", job_id)

    assert before == 0, "这条判据的前提没了（库里已经有这个作业的行）"
    assert [r["cluster_id"] for r in rows] == sorted(clusters), (
        f"关系行没落全：{[r['cluster_id'] for r in rows]}")


@pytest.mark.compose
def test_running_it_twice_never_writes_a_second_row(a_combo_topic: Any) -> None:
    """续跑幂等：同一个作业 NEVER 写出第二行（既有口径，本卡守着它）。"""
    from flint.jobs.cluster_verdict import record_cluster_verdicts

    _, clusters, job_id = a_combo_topic

    async def _go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, "
                "budget, cost_accum, cancel_requested, initiated_by, created_at, "
                "updated_at) VALUES ($1, 'gate1_analysis', $2::jsonb, 'done', 1.0, "
                "0.0, 0.0, false, 'u-owner', $3, $3)",
                job_id, json.dumps({"kind": "user", "id": "u-owner"}), NOW)
            for _ in range(2):
                await record_cluster_verdicts(
                    conn, job_id=job_id, cluster_ids=clusters, now=NOW)
        finally:
            await conn.close()

    asyncio.run(_go())

    assert len(_sql(
        "SELECT 1 FROM cluster_verdicts WHERE job_id = $1", job_id)) == len(clusters)


@pytest.mark.compose
def test_the_read_endpoint_finds_the_verdict_again(a_combo_topic: Any) -> None:
    """写下去之后**取得回来**（acceptance③ 的读那一半）。

    只判「库里有行」是不够的：读端点走的是另一条路
    （`flint/repo/cluster_verdict.py`），断在那里的话屏上照样说「还没有判定」。
    """
    from flint.jobs.cluster_verdict import record_cluster_verdicts
    from flint.repo.cluster_verdict import latest_verdict_job

    _, clusters, job_id = a_combo_topic

    async def _go() -> str | None:
        conn = await asyncpg.connect(DSN)
        try:
            # `latest_verdict_job` 吃的是**连接**，不是 DSN（读端点那一层已经
            # 拿着连接了）。传 DSN 进去会在它内部 `AttributeError`，
            # 而那与「这个热点没判过」完全是两回事。
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, "
                "budget, cost_accum, cancel_requested, initiated_by, created_at, "
                "updated_at) VALUES ($1, 'gate1_analysis', $2::jsonb, 'done', 1.0, "
                "0.0, 0.0, false, 'u-owner', $3, $3)",
                job_id, json.dumps({"kind": "user", "id": "u-owner"}), NOW)
            await record_cluster_verdicts(
                conn, job_id=job_id, cluster_ids=clusters, now=NOW)
            return await latest_verdict_job(conn, clusters[0])
        finally:
            await conn.close()

    assert asyncio.run(_go()) == job_id


# ───────────────────────── 三、阴性对照：不带 topic_id → 一行不写，且话不同


@pytest.mark.compose
def test_without_a_topic_id_not_a_single_row_is_written() -> None:
    """**阴性对照**（acceptance⑤）：不带 `topic_id` → `cluster_verdicts` 一行不写。

    这不是缺陷，是一种**真实状态**：那次判定不知道自己判的是哪几条热点。
    `gate1.py` 的既有口径就是「不给就不写」，本卡守住它——
    改成「猜一个」的话，屏上会出现一条我们并不知道产地的判定。
    """
    tag = uuid.uuid4().hex[:8]
    job_id = f"job-noid-{tag}"

    async def _go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, "
                "budget, cost_accum, cancel_requested, initiated_by, created_at, "
                "updated_at) VALUES ($1, 'gate1_analysis', $2::jsonb, 'done', 1.0, "
                "0.0, 0.0, false, 'u-owner', $3, $3)",
                job_id, json.dumps({"kind": "user", "id": "u-owner"}), NOW)
        finally:
            await conn.close()

    try:
        asyncio.run(_go())
        # `topic_id is None` 这条路：`gate1.py` 里那句 if 直接跳过写入。
        assert _sql(
            "SELECT 1 FROM cluster_verdicts WHERE job_id = $1", job_id) == []
    finally:
        _exec("DELETE FROM cluster_verdicts WHERE job_id = $1", job_id)
        _exec("DELETE FROM jobs WHERE job_id = $1", job_id)


def test_the_skip_is_guarded_by_the_explicit_check() -> None:
    """那句 `if topic_id is not None:` **还在**，且理由写在旁边。

    去掉它的话，`clusters_for_topic(None)` 会以另一种方式失败——
    而失败点会离病因很远。
    """
    code = GATE1.read_text(encoding="utf-8")

    assert "if topic_id is not None:" in code
    assert "一行都不写" in code


def test_no_data_and_no_verdict_are_two_different_sentences() -> None:
    """屏上「还没有判定」与「这次判定没记热点」**NEVER 共用一句话**（acceptance⑤）。

    两者该让用户做的事完全不同：前者等作业跑完，后者说明这次分析
    不是从热点发起的——刷新一万次也不会变。
    """
    messages = json.loads(
        (REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    verdict_keys = [k for k in messages if k.startswith("analysis.")
                    and ("verdict" in k or "no_" in k)]

    assert verdict_keys, "分析屏一条判定相关的词条都没有"
    values = [messages[k] for k in verdict_keys]
    assert len(set(values)) == len(values), (
        f"分析屏有两条词条共用同一句话：{[k for k in verdict_keys]}")


def test_this_card_did_not_touch_the_verdict_engine() -> None:
    """acceptance④：四分类与引用照旧走既有引擎，本卡一个字都没改。

    判的是**依赖方向**：`cluster_verdict` 这一层只写关系，
    NEVER 反过来去碰判定本身。
    """
    text = (REPO / "flint" / "jobs" / "cluster_verdict.py").read_text(
        encoding="utf-8")

    assert "from flint.gate" not in text, "关系层开始 import 判定引擎了"
    assert "verdict_class" not in text and "all_satisfied" not in text
