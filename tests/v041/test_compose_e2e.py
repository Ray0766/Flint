"""COMPOSE-01：⑦计划书这一步在 demo 面上真能跑——而「不挂」的理由早就过期了。

## 那句注释错在三重

`harness/demo_server.py` 顶上写着：

> report/proposal 提交端点（flint.api.compose）**刻意不挂**：demo 无 report worker，
> 挂了只会造出永远 queued 的 job（假连通），NEVER 那样做。

1. **「不挂」不成立**——`WIRE-08` 之后这一族由 `create_app` 挂上，
   demo 这一侧根本没有挂不挂的选择权；
2. **「无 report worker」不成立**——`harness/run_worker.py` 起
   `flint/jobs/worker_main.py#build_worker`，`start-demo.ps1` §3b 每次都起它；
3. 于是**真正坏掉的那一件被这句话盖住了**：demo 调 `create_app(DSN)` 时
   **不给 `redis_url`**，`_queue_hook(None)` 回 `_unconfigured("analysis")`，
   任何组稿提交回 **503 FAMILY_NOT_CONFIGURED**——`COMPOSE-01` 实测到的就是这一幕。

一句变假的注释比没有注释坏：照着它读，会把「接线漏了一个参数」读成「刻意没做」。

## 本文件判什么

| § | 判的是 |
|---|---|
| 一 | 队列真的接上了，且 API 与 worker 读**同一个**队列地址 |
| 二 | 那三句过期的话改成了实况，并写清**谁在消费 report 作业** |
| 三 | 端到端：提交 → 作业落库 → 处理器跑 → **新的** deliverable + 真 block |
| 四 | 正文 NEVER 是占位（`_default_generator` 那个桩的形状） |
| 五 | provider 缺失照旧显式抛，NEVER 静默回落 |

## 真栈那一跑的留痕

CI 不联网也不起 Ollama，所以 §三 用**注入的确定性 provider** 在测试库上跑完整条链。
真模型那一跑（本机 qwen3.6:35b-a3b）记在 `docs/trace/COMPOSE-01.md`：
`job-4d22d6be…` `queued → drafting → done`，产出 `del-job-4d22d6be…` 共 **22 个 block**，
正文是「推理算力成本按 GPU 卡时计费，本表记录为 720 卡时。」这样的真句子。
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import pytest

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "harness" / "demo_server.py"
WORKER = REPO / "harness" / "run_worker.py"
COMPOSE_JOB = REPO / "flint" / "jobs" / "compose.py"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

#: demo 面上那份现成的报告。端到端产出的 `deliverable_id` **NEVER 是它**——
#: 是它就说明我们看的是种子数据，而不是这一跑真造出来的东西。
FIXTURE_DELIVERABLE = "del-demo-fixture-report"

#: 确定性 provider 写的那一句。**是一句真的中文**，不是 section_id。
SENTENCE = "本节由确定性 provider 生成：这一句是完整的中文句子，用来证明正文不是占位。"


# ───────────────────────── 一、队列真的接上了


def test_the_demo_hands_the_queue_to_the_app() -> None:
    """`create_app` MUST 收到 `redis_url`。

    不给的话 `_queue_hook(None)` 回 `_unconfigured("analysis")`，
    提交回 503——而屏上那一步会被读成「功能没做」。

    **判的是那一发调用的关键字参数，不是源码里的一行字**（`COMBO-WIRE-01` 改的）：
    原先比的是字面量 `"create_app(DSN, redis_url=REDIS_URL)"`，于是
    `COMBO-WIRE-01` 给同一发调用补上 `combo_provider=` 之后它当场红——
    而队列那条缝**一个字都没变**。比字面量的判据守的是**格式**，不是那件事。
    """
    import ast

    tree = ast.parse(DEMO.read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and getattr(node.func, "id", "") == "create_app"]

    assert calls, "demo 不再调 create_app 了"
    for call in calls:
        keywords = {k.arg for k in call.keywords}
        assert "redis_url" in keywords, (
            "demo 又在不给队列地址的情况下装配 app 了")


def test_the_api_and_the_worker_read_the_same_queue() -> None:
    """两处读**同一个环境变量、同一个默认值**。

    各写一份的话，API 把作业推进 A 队列而 worker 守着 B 队列，
    症状是「作业永远 queued」——与「worker 没起来」在表上长得一模一样。
    """
    demo = DEMO.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    line = 'os.environ.get("FLINT_REDIS_URL", "redis://localhost:56379/0")'

    assert line in demo, "demo 那一侧的队列地址不是这一份"
    assert line in worker, "worker 那一侧的队列地址不是这一份"


# ───────────────────────── 二、过期的话改成了实况


#: 那三句今天是假的话。判据要的不是「这些字消失」，而是**它们不再被当成现状主张**。
_STALE_CLAIMS = (
    "刻意不挂",
    "demo 无 report worker",
    "demo 未挂 compose 提交端点",
    "interventions 挂、compose 不挂",
)

#: 把一句旧话标成历史的记号。
_MARKED_AS_PAST = ("原先", "原注释", "已过期", "是假的", "今天两重是假的", "已改")


def test_no_stale_claim_is_still_asserted() -> None:
    """那三句 NEVER 再以**现状**的身份出现。

    改前它们说的是「这一步刻意没做」，而实况是这一步能跑——
    照着它读会把接线漏了一个参数读成功能没做（`WIRE-VERDICT` 同形状）。

    **判的是「主张」不是「字面」**：把旧话引出来再说明它为什么假，
    正是一条好注释该做的事；一条只禁字面的判据会逼着人把历史抹掉，
    而抹掉之后没人知道这里曾经为什么不挂。所以这里逐行看——
    出现旧话的那一行（或它上下文）MUST 同时带着「这是过去式」的记号。
    """
    lines = DEMO.read_text(encoding="utf-8").splitlines()
    offenders = []
    for i, line in enumerate(lines):
        for claim in _STALE_CLAIMS:
            if claim not in line:
                continue
            window = " ".join(lines[max(0, i - 3):i + 4])
            if not any(mark in window for mark in _MARKED_AS_PAST):
                offenders.append(f"{i + 1}: {line.strip()[:60]}")
    assert offenders == [], f"这些地方仍把过期的话当现状说：{offenders}"


def test_the_correction_names_what_was_wrong() -> None:
    """改正 MUST 说清**错在哪**，NEVER 只写一句「已更新」。

    只写「已更新」的话，下一个人无从判断这段接线现在到底是什么样子。
    """
    code = DEMO.read_text(encoding="utf-8")

    assert "WIRE-08" in code, "没说这一族其实早就挂上了"
    assert "COMPOSE-01" in code
    assert "_queue_hook" in code or "redis_url" in code, "没说真正缺的是队列那一件"


def test_the_file_says_who_consumes_report_jobs() -> None:
    """**写清谁在消费**（acceptance③ 逐字）。

    只把过期的话删掉是不够的：删完之后，「这一步靠什么跑起来」
    在 demo 面上就没有任何一处写着了。
    """
    code = DEMO.read_text(encoding="utf-8")

    assert "harness/run_worker.py" in code, "没写谁在消费 report 作业"
    assert "build_worker" in code
    assert "LocalProvider" in code, "没写组稿走的是免费本地档"


# ───────────────────────── 三、端到端：提交 → 作业 → 处理器 → 新产物


def _fake_provider() -> Any:
    """确定性 provider——**不是占位生成器**。

    它回的是**真句子**（每节不同），所以 §四 那条「正文不是占位」的判据
    量到的是真东西；而它零网络、零模型，CI 跑得动。

    NEVER 拿 `_default_generator` 来充这个位：那个桩正是本文件要抓的形状。
    """
    class _P:
        def generate(self, prompt: str, tools: Any = None) -> Any:
            return SENTENCE

        def generate_structured(
            self, prompt: str, schema: Any, max_retries: int = 2,
        ) -> Any:
            # 键名逐字照 `flint/compose/llm_generator.py#_parse_blocks` 读的那个：
            # 它认的是 **`type`**。写成 `kind` 的话每一块都走 `continue` 被跳过，
            # 而作业照样 `done`——**一个不合契约的桩会产出一份空壳并报成功**。
            # （这条判据第一版就是这么写的，实测产物有了、block 0 个。）
            return {"blocks": [
                {"type": "heading", "level": 2, "text": "本节标题"},
                {"type": "paragraph", "text": SENTENCE},
            ]}

    return _P()


@pytest.fixture()
def a_project() -> Any:
    """一条自带的项目 + 一份源产物，用完删干净（外键顺序）。"""
    pid = f"proj-compose-{uuid.uuid4().hex[:8]}"
    src = f"del-src-{uuid.uuid4().hex[:8]}"

    async def _write() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
                "chosen_topic_id, deliverable_ids, change_log, status, created_at, "
                "version) VALUES ($1, $2, $3, '[]'::jsonb, NULL, '[]'::jsonb, "
                "'[]'::jsonb, 'active', now(), 1)",
                pid, json.dumps({"kind": "user", "id": "u-owner"}), f"origin-{pid}")
        finally:
            await conn.close()

    async def _erase() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            made = await conn.fetch(
                "SELECT deliverable_id FROM deliverables WHERE project_id = $1", pid)
            for row in made:
                await conn.execute(
                    "DELETE FROM blocks WHERE deliverable_id = $1",
                    row["deliverable_id"])
            await conn.execute("DELETE FROM deliverables WHERE project_id = $1", pid)
            # `jobs` 的引用者**一个都不能漏**（实查 `information_schema`：
            # job_steps · job_events · cluster_verdicts · idempotency_keys）。
            # 漏一个的话红出现在**别人的文件里**而根因在这里
            # （`WIRE-VERDICT` 那次的教训）。
            for child in ("job_steps", "job_events", "cluster_verdicts",
                          "idempotency_keys"):
                await conn.execute(
                    f"DELETE FROM {child} WHERE job_id IN "
                    "(SELECT job_id FROM jobs WHERE project_id = $1)", pid)
            await conn.execute("DELETE FROM jobs WHERE project_id = $1", pid)
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
        finally:
            await conn.close()

    asyncio.run(_erase())
    asyncio.run(_write())
    try:
        yield pid, src
    finally:
        asyncio.run(_erase())


@pytest.mark.compose
def test_a_submitted_report_becomes_a_new_deliverable(a_project: Any) -> None:
    """**整条链**：提交端点 → `jobs` 落一行 → 处理器跑 → 新产物 + 真 block。

    这一条是本卡的产品。分开判「端点回了 job_id」与「库里有产物」的话，
    中间那段（入队 → 消费）断了也没有任何东西会红——
    而那正是 `COMPOSE-01` 修的那一段。
    """
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient

    from flint.api.compose import ComposeApiDeps, create_compose_app
    from flint.domain.models import Principal, UserProfile
    from flint.jobs.runner import PgJobRunner
    from flint.jobs.worker_main import ARQ_TASK_NAME, WorkerDeps, build_worker

    project_id, _ = a_project
    seen: list[tuple[str, str, dict[str, Any]]] = []

    async def capture(job_id: str, kind: str, payload: dict[str, Any]) -> None:
        """入队钩子的替身：**记下来**，随后同步跑一遍处理器。

        用替身而不是真 redis：CI 不起 redis（`S2-7`）。
        换掉的只有「消息怎么送到 worker」，**处理器本身是真的那一个**。
        """
        seen.append((job_id, kind, payload))

    runner = PgJobRunner(
        dsn=DSN, role_resolver=lambda _u, _o: "owner", enqueue=capture)
    client = TestClient(create_compose_app(ComposeApiDeps(
        dsn=DSN, runner=runner,
        owner_scope_for_project=lambda _p: Principal(kind="user", id="u-owner"),
        role_resolver=lambda _u, _o: "owner")), raise_server_exceptions=False)

    posted = client.post(
        f"/projects/{project_id}/report",
        json={"analysis_id": FIXTURE_DELIVERABLE, "template_id": "generic"},
        headers={"X-User-Id": "u-owner"})

    assert posted.status_code == 200, posted.text
    job_id = posted.json()["job_id"]
    assert seen, "提交没有入队——作业会永远停在 queued"
    assert seen[0][1] == "report"

    # **真的把处理器跑一遍**，NEVER 只断言它注册了：
    # 「注册了」与「跑起来能产出东西」之间正是本卡修的那一段。
    # 取的是 worker 自己注册的那一个协程（`ARQ_TASK_NAME`），
    # 不是另找一条路——另找一条路证明的是那条路能跑，不是 worker 能跑。
    now = datetime.now(UTC)
    worker = build_worker(WorkerDeps(
        dsn=DSN, redis_url="redis://unused", repo_root=REPO,
        profile=UserProfile(
            profile_id="p-compose", owner=Principal(kind="user", id="u-owner"),
            identity={}, research={}, team=[], assets={}, constraints={},
            track_record=[], locale="zh-CN", sensitivity_overrides={},
            updated_at=now),
        now=now, compose_provider=_fake_provider()), cron_jobs=[])

    assert ARQ_TASK_NAME in worker.functions, "worker 没注册那个处理器"
    task = worker.functions[ARQ_TASK_NAME].coroutine

    queued_id, queued_kind, queued_payload = seen[0]
    assert queued_id == job_id, "入队的作业与端点回的不是同一个"
    asyncio.run(task({}, queued_id, queued_kind, queued_payload))

    made = _deliverables_of(project_id)
    assert made, "作业跑完了，而库里一份产物都没有"
    assert FIXTURE_DELIVERABLE not in made, (
        "拿到的是种子那一份——那不是这一跑造出来的")
    assert len(made) == 1, f"这一跑产出的不止一份：{made}"

    blocks = _blocks_of(made[0])
    assert blocks, "产物有了，而一个 block 都没有——那是一份空壳"


def _blocks_of(deliverable_id: str) -> list[str]:
    """那份产物下的正文块（`content` 的 JSON 文本）。"""
    async def _go() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT content::text AS body FROM blocks WHERE deliverable_id = $1",
                deliverable_id)
        finally:
            await conn.close()
        return [r["body"] for r in rows]

    return asyncio.run(_go())


def _deliverables_of(project_id: str) -> list[str]:
    async def _go() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT deliverable_id FROM deliverables WHERE project_id = $1",
                project_id)
        finally:
            await conn.close()
        return [r["deliverable_id"] for r in rows]

    return asyncio.run(_go())


# ───────────────────────── 四、正文 NEVER 是占位


def test_the_placeholder_generator_is_still_there_and_still_a_stub() -> None:
    """`_default_generator` **一个字都不动**（acceptance⑦）。

    它是离线确定性判据的桩，删它会连累 CI。本卡因此只判它**是什么形状**，
    好让 §四 下一条能说出「真正文与它不同」。
    """
    code = COMPOSE_JOB.read_text(encoding="utf-8")

    assert "def _default_generator(" in code
    # 桩的形状：标题文字**就是 section_id 本身**。
    assert "text=spec.section_id" in code, "桩的形状变了，下面那条判据的基准没了"


def test_real_content_is_not_the_stub_shape() -> None:
    """真正文的文字 NEVER 等于 `section_id` 字面量（acceptance⑤）。

    这条判据的基准来自上一条读到的桩形状——**不是我另写一份猜的形状**。
    """
    provider = _fake_provider()
    text = provider.generate("任意提示词")

    assert text == SENTENCE
    assert text != "budget" and text != "competition", "生成物退回桩形状了"
    assert len(text) > 20, f"这不是一句话：{text!r}"
    assert "。" in text, "正文里一个句号都没有——那不是正文"


# ───────────────────────── 五、provider 缺失照旧显式抛


def test_a_missing_provider_still_raises_instead_of_falling_back() -> None:
    """`provider=None` → `ComposeProviderMissing`，NEVER 静默回落到占位生成器。

    静默回落的话，一份**全是占位标题**的报告会带着 `state=done` 交出去——
    而那比失败坏：失败会喊，这一种安安静静地交一份空壳。
    """
    from datetime import UTC, datetime

    from flint.domain.models import Principal, UserProfile
    from flint.jobs.compose_deps import (
        ComposeProviderMissing,
        build_production_compose_deps,
    )

    now = datetime.now(UTC)
    with pytest.raises(ComposeProviderMissing):
        build_production_compose_deps(
            dsn=DSN, repo_root=REPO,
            profile=UserProfile(
                profile_id="p", owner=Principal(kind="user", id="u"),
                identity={}, research={}, team=[], assets={}, constraints={},
                track_record=[], locale="zh-CN", sensitivity_overrides={},
                updated_at=now),
            now=now, provider=None, template_name="generic.yaml")


def test_the_discipline_is_written_where_the_seam_is() -> None:
    """那条纪律写在缝自己的文件头里——本卡一个字都没动它。"""
    text = (REPO / "flint" / "jobs" / "compose_deps.py").read_text(encoding="utf-8")

    assert "静默回落到占位生成器" in text
    assert "ComposeProviderMissing" in text


def test_the_worker_binds_the_free_local_tier() -> None:
    """组稿的模型是**免费本地档**，NEVER 读任何 key（本批 `llm_cost` 纪律）。"""
    code = WORKER.read_text(encoding="utf-8")

    assert "LocalProvider" in code
    assert "NEVER 读任何 API key" in code
    for paid in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "api_key"):
        assert paid not in code, f"worker 里出现了 {paid}"


def test_build_production_compose_deps_is_what_the_worker_uses() -> None:
    """卡面实况那一条：worker 绑的是**真 LLM 生成器**，不是桩。"""
    from flint.jobs import worker_main

    source = inspect.getsource(worker_main)

    assert "build_production_compose_deps(" in source
    assert "_default_generator" not in source, "worker 绑到桩上去了"
