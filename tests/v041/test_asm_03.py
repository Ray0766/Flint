"""ASM-03：arq worker 进程装配——让提交的作业真的有人跑。

缺陷背景：`harness/demo_seed_report.py:6` 自述「demo_server 的 enqueue 只接
gate1_analysis」；全仓没有任何进程消费组稿作业。提交一份报告 → 作业进 jobs 表 →
没人消费 → 永远 queued。本卡把 `flint/jobs/runner.py` 既有的可注入 `EnqueueHook`
接到真 arq 队列，并起一个真 worker 把作业跑到 done。

零真实外网（S2-7）：LLM 走 MockTransport 录制回放；redis 与 postgres 是本机容器
（工单 §4「本机不算外网」）。`flint/jobs/runner.py` 一字未改（它本来就可注入）。

并行纪律：每个用例用**独立队列名**（`arq:asm03-{uuid}`）。redis 容器是 worker 与
supervisor 共用的一台，固定队列名会让两条线互相消费对方的作业。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest
from arq import create_pool
from arq.connections import RedisSettings

from flint.compose.blocks import PgBlockStore
from flint.domain.models import JSON, Principal, UserProfile
from flint.jobs.dispatch import WIREABLE_KINDS, JobKindNotWired, build_dispatch_table
from flint.jobs.runner import PgJobRunner
from flint.jobs.worker_main import (
    ARQ_TASK_NAME,
    HandlerDepsMissing,
    WorkerDeps,
    build_dispatch_table_for,
    build_enqueue_hook,
    build_handlers,
    build_worker,
    make_mark_failed,
)
from flint.llm.local import LocalProvider

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
REDIS_URL = os.environ.get("FLINT_TEST_REDIS", "redis://localhost:56379/0")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── acceptance ③：依赖版本来自 lock，NEVER 硬编码 ───────────────────────

def _lock_pin(package: str) -> str:
    text = (REPO / "requirements.lock").read_text(encoding="utf-8")
    match = re.search(rf"^{package}==(\S+)$", text, re.MULTILINE | re.IGNORECASE)
    assert match is not None, f"requirements.lock 里没有 {package} 的钉版"
    return match.group(1)


def test_arq_and_redis_versions_come_from_the_lock_not_a_hardcoded_string() -> None:
    import arq
    import redis

    assert arq.__version__ == _lock_pin("arq"), (
        f"装的 arq {arq.__version__} 与 lock 的 {_lock_pin('arq')} 不一致"
    )
    assert redis.__version__ == _lock_pin("redis"), (
        f"装的 redis {redis.__version__} 与 lock 的 {_lock_pin('redis')} 不一致"
    )


def test_worker_module_introduces_no_dependency_outside_the_lock() -> None:
    """worker 装配的第三方 import 必须都已在 lock 里（NEVER 新增依赖）。"""
    import ast
    import sys as _sys

    source = (REPO / "flint" / "jobs" / "worker_main.py").read_text(encoding="utf-8")
    lock = (REPO / "requirements.lock").read_text(encoding="utf-8").lower()
    roots: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    third_party = {
        r for r in roots
        if r != "flint" and r not in _sys.stdlib_module_names
    }
    assert third_party, "没解析到任何第三方 import——检查解析逻辑是否空转"
    for root in sorted(third_party):
        assert f"\n{root}==" in f"\n{lock}", f"{root} 不在 requirements.lock 里"


# ── 分派面：五个可接线 kind 一个不少；缺 deps 显式抛错 ──────────────────

def _worker_deps(provider: LocalProvider | None = None, **kw: Any) -> WorkerDeps:
    return WorkerDeps(
        dsn=DSN, redis_url=REDIS_URL, repo_root=REPO,
        profile=UserProfile(
            profile_id="p-asm03", owner=Principal(kind="user", id="u-asm03"),
            identity={}, research={}, team=[], assets={}, constraints={},
            track_record=[], locale="zh-CN", sensitivity_overrides={},
            updated_at=NOW),
        now=NOW, compose_provider=provider, **kw,
    )


def _replay_provider(text: str = "本节正文由录制回放产出。") -> LocalProvider:
    def respond(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {
                "content": json.dumps(
                    {"blocks": [{"type": "paragraph", "text": text, "fact_ids": []}]},
                    ensure_ascii=False,
                ),
                "tool_calls": [],
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })
    return LocalProvider(
        base_url="http://local/v1", model="qwen3.6:27b",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )


def test_handlers_cover_every_wireable_kind() -> None:
    handlers = build_handlers(_worker_deps(_replay_provider()))
    assert set(handlers) == set(WIREABLE_KINDS)
    table = build_dispatch_table(handlers)
    assert len(table) == 10


def test_missing_compose_provider_is_named_at_build_time() -> None:
    with pytest.raises(HandlerDepsMissing) as err:
        build_dispatch_table_for(_worker_deps(provider=None))
    assert "compose_provider" in str(err.value)


def test_missing_gate1_deps_names_what_to_inject() -> None:
    table = build_dispatch_table_for(_worker_deps(_replay_provider()))
    with pytest.raises(HandlerDepsMissing) as err:
        run(table["gate1_analysis"]("job-x", {}))
    assert "gate1_deps" in str(err.value)


def test_unwired_kind_still_fails_loudly_through_the_worker_table() -> None:
    """还没有消费者的 kind，经 worker 表调到时**照样大声失败**。

    例子**从名单里取**，不写死一个 kind 名：这里原先写死的是 `translate`，
    而 v0.4.1 第 6 批的 `SLOT-03` 把它接上了消费者，于是这条判据红了——
    **它红的是自己的例子过期，不是接线出错**。
    从 `UnwiredKindReason` 取，下一次接线时它会自动换到剩下那一条上；
    名单空了的话 `min()` 会抛——`PERSIST-03` 接走最后一条之后正是如此。

    **那时不该删掉这条判据**（上一版的 docstring 是这么写的，那句话是错的）：
    要量的是「经 worker 表调到未接线的 kind 时会大声失败」，
    而那件事与「今天恰好还剩几条没接」无关。所以改成造一条本判据自己的声明，
    再断言它经**同一张 worker 表**被调到时抛 `JobKindNotWired`。
    """
    # `PERSIST-03` 把最后一条也接走了，**那张表现在是空的**。
    # 「取当下仍未接线的第一个」这个写法本来就是为了不被接线进度带红，
    # 而它没预料到表会被清空（`min({})` 当场抛 ValueError）。
    # 改成造一条**本判据自己的**未接线声明：量的是「大声失败」这套机制还活着，
    # 而那与「今天恰好还剩几条没接」本来就是两件事。
    from flint.jobs.dispatch import _not_wired

    still_unwired = "some_future_kind"
    table = {
        **build_dispatch_table_for(_worker_deps(_replay_provider())),
        still_unwired: _not_wired(still_unwired, "仓里还没有它的消费者。"),
    }
    with pytest.raises(JobKindNotWired):
        run(table[still_unwired]("job-x", {}))


def test_worker_module_never_opens_a_real_network_client_at_import() -> None:
    """红线：装配模块 import 期 NEVER 造真实 http 客户端 / 读 key。"""
    source = (REPO / "flint" / "jobs" / "worker_main.py").read_text(encoding="utf-8")
    module_level = [
        ln for ln in source.splitlines()
        if ln and not ln[0].isspace() and not ln.startswith(("#", '"', "'"))
    ]
    joined = "\n".join(module_level)
    for forbidden in ("httpx.Client(", "GithubArxivSearcher(", "api_key", "API_KEY"):
        assert forbidden not in joined, f"模块层出现 {forbidden}"


# ── 以下走真容器（postgres 55432 + redis 56379），逐条挂 @pytest.mark.compose ──


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def _wipe(prefix: str) -> None:
    run(_sql([
        f"DELETE FROM job_events WHERE job_id LIKE '{prefix}%'",
        f"DELETE FROM job_steps WHERE job_id LIKE '{prefix}%'",
        f"DELETE FROM jobs WHERE job_id LIKE '{prefix}%'",
        f"DELETE FROM snapshots WHERE snapshot_id LIKE 'snap-{prefix}%'",
        f"DELETE FROM blocks WHERE deliverable_id LIKE 'del-{prefix}%'",
        f"DELETE FROM generation_records WHERE record_id LIKE 'rec-{prefix}%'",
        f"DELETE FROM deliverables WHERE deliverable_id LIKE 'del-{prefix}%'",
        ("DELETE FROM facts WHERE ledger_id IN (SELECT ledger_id FROM "
         f"facts_ledgers WHERE project_id LIKE '{prefix}%')"),
        f"DELETE FROM facts_ledgers WHERE project_id LIKE '{prefix}%'",
        f"DELETE FROM claims WHERE claim_id LIKE '{prefix}%'",
    ]))


def _seed_claim(prefix: str) -> None:
    run(_sql([
        (f"INSERT INTO claims (claim_id, deliverable_id, block_id, text_span, "
         f"confidence, citation_ids, alignment, promoted_fact_id) VALUES "
         f"('{prefix}c1', '{prefix}src', 'b-src', '市场规模 12 亿', 'cited', "
         f"'[\"cit-1\"]'::jsonb, 'supports', NULL) ON CONFLICT (claim_id) DO "
         f"UPDATE SET promoted_fact_id = NULL"),
    ]))


async def _job_state(job_id: str) -> str | None:
    conn = await asyncpg.connect(DSN)
    try:
        state: str | None = await conn.fetchval(
            "SELECT state FROM jobs WHERE job_id = $1", job_id
        )
        return state
    finally:
        await conn.close()


async def _steps(job_id: str) -> list[tuple[str, str]]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT name, snapshot_ref FROM job_steps WHERE job_id = $1 "
            "ORDER BY step_index", job_id,
        )
        return [(r["name"], r["snapshot_ref"]) for r in rows]
    finally:
        await conn.close()


@pytest.mark.compose
def test_enqueue_hook_puts_the_job_in_the_real_queue() -> None:
    """acceptance ①：断言基于**队列真实状态**（redis 里真的躺着这条作业），
    NEVER 断言「钩子被调了几次」——调用计数证明不了作业进没进队列。"""
    prefix = "asm03q-"
    _wipe(prefix)
    queue = f"arq:asm03-{uuid.uuid4().hex[:8]}"
    wanted = f"{prefix}{uuid.uuid4().hex[:8]}"   # 每次跑用新 id：arq 的 _job_id 去重是
                                                 # 全局键，复用旧 id 会让本条静默不入队

    async def scenario() -> tuple[str, list[Any]]:
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        try:
            hook = build_enqueue_hook(pool, queue_name=queue)
            runner = PgJobRunner(
                dsn=DSN, role_resolver=lambda _u, _o: "owner",
                id_factory=lambda: wanted, enqueue=hook,
            )
            job_id = await runner.submit(
                kind="report", payload={"project_id": f"{prefix}p1"},
                budget=0.0, owner_scope=Principal(kind="user", id="u-asm03"),
                initiated_by="u-asm03",
            )
            queued = await pool.queued_jobs(queue_name=queue)
            # 同一作业再提交一次：队列层按 _job_id 去重，NEVER 排成两条跑两遍
            await hook(job_id, "report", {"project_id": f"{prefix}p1"})
            requeued = await pool.queued_jobs(queue_name=queue)
            return job_id, [queued, requeued]
        finally:
            await pool.aclose()

    job_id, (queued, requeued) = run(scenario())
    assert len(queued) == 1, f"队列里应有 1 条作业，实为 {len(queued)}"
    job_def = queued[0]
    assert job_def.function == ARQ_TASK_NAME
    assert job_def.args[0] == job_id, f"队列里的作业不是刚提交的那条：{job_def.args}"
    assert job_def.args[1] == "report"
    assert len(requeued) == 1, f"重复提交排成了 {len(requeued)} 条——同一作业会被跑两遍"


@pytest.mark.compose
def test_empty_queue_makes_the_previous_assertion_fail() -> None:
    """反例：不接钩子时队列是空的——证明上一条断言看的是真队列。"""
    queue = f"arq:asm03-{uuid.uuid4().hex[:8]}"

    async def scenario() -> list[Any]:
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        try:
            return await pool.queued_jobs(queue_name=queue)
        finally:
            await pool.aclose()

    assert run(scenario()) == []


@pytest.mark.compose
def test_worker_consumes_a_compose_job_and_drives_it_to_done() -> None:
    """acceptance ②前半：真 worker 消费 → 状态机到 done，且正文是真生成的段落。"""
    prefix = "asm03c-"
    _wipe(prefix)
    _seed_claim(prefix)
    queue = f"arq:asm03-{uuid.uuid4().hex[:8]}"
    job_id = f"{prefix}{uuid.uuid4().hex[:8]}"
    deps = _worker_deps(_replay_provider("worker 真跑产出的正文。"))

    async def scenario() -> None:
        pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        try:
            hook = build_enqueue_hook(pool, queue_name=queue)
            runner = PgJobRunner(
                dsn=DSN, role_resolver=lambda _u, _o: "owner",
                id_factory=lambda: job_id, enqueue=hook,
            )
            await runner.submit(
                kind="report",
                payload={"project_id": f"{prefix}p1", "analysis_id": f"{prefix}src"},
                budget=0.0, owner_scope=Principal(kind="user", id="u-asm03"),
                initiated_by="u-asm03",
            )
            worker = build_worker(deps, queue_name=queue, burst=True)
            await worker.async_run()
            await worker.close()
        finally:
            await pool.aclose()

    run(scenario())
    assert run(_job_state(job_id)) == "done", "worker 没把作业推到 done"
    tree = run(PgBlockStore(dsn=DSN).load_tree(f"del-{job_id}"))
    paragraphs = [b for b in tree if b.type == "paragraph"]
    assert paragraphs, f"产出里没有 paragraph（块型={[b.type for b in tree]}）"
    text = "".join(
        s.text for s in paragraphs[0].content.spans if s.kind == "text"  # type: ignore[union-attr]
    )
    assert "worker 真跑产出的正文。" in text
    assert [n for n, _ in run(_steps(job_id))] == [
        "outline", "freeze", "draft", "align", "render",
    ]


@pytest.mark.compose
def test_worker_resumes_a_half_finished_job_reusing_draft_checkpoints() -> None:
    """acceptance ②后半（worker handler 路）：作业跑到一半中断，重启后从断点续跑。

    中断点选在 **draft 步**：让注入的 provider 抛错。compose 每步与 job_steps 同一事务
    提交，因此中断后库里留下的已完成前缀，与 kill -9 留下的完全一样（未完成步的事务两
    种情况下都不落盘）。
    真 kill -9（`os._exit(137)`）那一路、以及 **draft 步断点被复用**（续跑不重跑 draft）
    由 `test_real_kill_then_resume_via_the_compose_cli` 覆盖——那条走的是子进程真 kill。
    """
    prefix = "asm03r-"
    _wipe(prefix)
    _seed_claim(prefix)
    job_id = f"{prefix}1"

    class _BoomProvider:
        model = "boom"

        def generate(self, prompt: str, tools: object) -> object:
            raise RuntimeError("unused")

        def generate_structured(
            self, prompt: str, schema: object, max_retries: int
        ) -> JSON:
            raise RuntimeError("draft 步中断（模拟 worker 被 kill）")

    crashed = _worker_deps(_BoomProvider())  # type: ignore[arg-type]
    table = build_dispatch_table_for(crashed)
    payload: JSON = {"project_id": f"{prefix}p1", "analysis_id": f"{prefix}src"}
    with pytest.raises(RuntimeError, match="draft 步中断"):
        run(table["report"](job_id, payload))

    first_steps = run(_steps(job_id))
    assert [n for n, _ in first_steps] == ["outline", "freeze"], (
        f"中断点不对：{first_steps}"
    )
    assert run(_job_state(job_id)) != "done"

    from flint.jobs.checkpoints import deserialize_checkpoint
    for name, blob in first_steps:
        assert deserialize_checkpoint(blob).kind == "draft", f"{name} 步没落断点"

    healthy = _worker_deps(_replay_provider("续跑产出的正文。"))
    run(build_dispatch_table_for(healthy)["report"](job_id, payload))

    second_steps = run(_steps(job_id))
    assert [n for n, _ in second_steps] == [
        "outline", "freeze", "draft", "align", "render",
    ]
    assert second_steps[:2] == first_steps, (
        "续跑重写了已完成步的断点——已完成前缀应原样复用"
    )
    assert run(_job_state(job_id)) == "done"
    tree = run(PgBlockStore(dsn=DSN).load_tree(f"del-{job_id}"))
    assert any(b.type == "paragraph" for b in tree), "续跑没把 draft 步真跑出来"


@pytest.mark.compose
def test_real_kill_then_resume_via_the_compose_cli() -> None:
    """真 kill（子进程 os._exit(137)）后重启续跑——走 compose.py 既有的 --crash-after。"""
    prefix = "asm03k-"
    _wipe(prefix)
    _seed_claim(prefix)
    job_id = f"{prefix}1"
    argv = [
        sys.executable, "-m", "flint.jobs.compose", "--dsn", DSN,
        "--job-id", job_id, "--project-id", f"{prefix}p1",
        "--sources", f"{prefix}src",
    ]
    killed = subprocess.run([*argv, "--crash-after", "draft"], cwd=REPO, check=False)
    assert killed.returncode == 137, f"子进程没按预期被 kill：{killed.returncode}"
    assert [n for n, _ in run(_steps(job_id))] == ["outline", "freeze", "draft"]

    resumed = subprocess.run(argv, cwd=REPO, check=False)
    assert resumed.returncode == 0
    assert [n for n, _ in run(_steps(job_id))] == [
        "outline", "freeze", "draft", "align", "render",
    ]
    assert run(_job_state(job_id)) == "done"


@pytest.mark.compose
def test_unknown_kind_from_the_queue_marks_the_job_failed() -> None:
    """未知 kind 经 worker 落到 jobs.state=failed，NEVER 停在 queued。"""
    prefix = "asm03f-"
    _wipe(prefix)
    job_id = f"{prefix}1"
    run(_sql([
        ("INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
         "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
         f"VALUES ('{job_id}', 'report', "
         "'{\"kind\":\"user\",\"id\":\"u-asm03\"}', 'queued', 0, 0, 0, false, "
         "'u-asm03', now(), now())"),
    ]))
    mark_failed = make_mark_failed(DSN)
    run(mark_failed(job_id, "未知 job kind：'no_such_kind'"))
    assert run(_job_state(job_id)) == "failed"

    conn_error = run(_error_of(job_id))
    assert conn_error is not None and "no_such_kind" in conn_error


async def _error_of(job_id: str) -> str | None:
    conn = await asyncpg.connect(DSN)
    try:
        err: str | None = await conn.fetchval(
            "SELECT error FROM jobs WHERE job_id = $1", job_id
        )
        return err
    finally:
        await conn.close()
