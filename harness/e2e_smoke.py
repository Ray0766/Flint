"""端到端冒烟（ASM-05）：主链第一次真跑通。

## 这条链此前断在哪

`docs/steward/项目实况报告-2026-08-03.md#四` 实测：提交端点在、组稿编排在、报告读端点
在，但**中间没有人**——没有进程消费组稿作业，默认生成器只产占位 heading。demo 里报告页
的内容是 `harness/demo_seed_report.py` 播种的 fixture（`del-demo-fixture-` 前缀即其标记）。

本模块把五步串起来跑一次，每步单独报成败：

    submit（POST /projects/{id}/report）
      → enqueue（作业真的进了 arq 队列）
      → consume（worker 真的取走并跑完）
      → compose（GET /deliverables/{id}/blocks 非空且含 paragraph）
      → render（GET /deliverables/{id}/render?fmt=markdown 出 markdown）

失败时抛 `SmokeFailure`，消息里点名**断在哪一步**——「断言失败」四个字对排障没有用。

## 零真实网络

LLM 由调用方注入（CI 注入录制回放 provider；本机模型也走同一注入口）。postgres 与
redis 是本机容器。本模块自己 NEVER 造 http 客户端、NEVER 读 key。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import asyncpg
from arq import create_pool
from arq.connections import RedisSettings
from fastapi.testclient import TestClient

from flint.api.compose import ComposeApiDeps, create_compose_app
from flint.api.deliverables import DeliverableApiDeps, create_deliverables_app
from flint.authz import build_role_resolver
from flint.domain.models import JSON, JobKind, Principal, UserProfile
from flint.domain.protocols import LLMProvider
from flint.jobs.runner import PgJobRunner
from flint.jobs.worker_main import WorkerDeps, build_enqueue_hook, build_worker

STEP_ORDER: tuple[str, ...] = ("submit", "enqueue", "consume", "compose", "render")
FIXTURE_PREFIX = "del-demo-fixture-"


@dataclass(frozen=True)
class SmokeStep:
    name: str
    detail: str


@dataclass
class SmokeResult:
    job_id: str = ""
    deliverable_id: str = ""
    blocks: list[JSON] = field(default_factory=list)
    markdown: str = ""
    steps: list[SmokeStep] = field(default_factory=list)

    def step_names(self) -> list[str]:
        return [s.name for s in self.steps]


class SmokeFailure(AssertionError):
    """冒烟断了。消息第一句就是断在哪一步。"""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"端到端冒烟断在「{step}」步：{detail}")
        self.step = step
        self.detail = detail


@dataclass
class SmokeConfig:
    dsn: str
    redis_url: str
    repo_root: Path
    provider: LLMProvider
    profile: UserProfile
    now: datetime
    project_id: str
    analysis_id: str
    job_id: str
    queue_name: str
    user_id: str = "u-smoke"
    template_id: str = "generic"


def _enqueue_hook(cfg: SmokeConfig) -> Callable[[str, JobKind, JSON], object]:
    """每次入队现开一个 pool：提交端点跑在 TestClient 自己的事件循环里，
    跨循环复用连接池会绑错 loop。"""
    async def enqueue(job_id: str, kind: JobKind, payload: JSON) -> None:
        pool = await create_pool(RedisSettings.from_dsn(cfg.redis_url))
        try:
            await build_enqueue_hook(pool, queue_name=cfg.queue_name)(
                job_id, kind, payload
            )
        finally:
            await pool.aclose()

    return enqueue


def _worker_deps(cfg: SmokeConfig) -> WorkerDeps:
    return WorkerDeps(
        dsn=cfg.dsn, redis_url=cfg.redis_url, repo_root=cfg.repo_root,
        profile=cfg.profile, now=cfg.now, compose_provider=cfg.provider,
    )


def _submit(cfg: SmokeConfig, result: SmokeResult) -> None:
    # AUTH-05：真解析器。这条链路上的作业是**个人归属**（`kind == "user"`），
    # 那条路根本不问角色——但 NEVER 因此留一只常量手在这里：
    # 留着它，哪天有人把这条链改成 org 归属，越权会**静默地**通过。
    runner = PgJobRunner(
        dsn=cfg.dsn, role_resolver=build_role_resolver(cfg.dsn),
        id_factory=lambda: cfg.job_id, enqueue=_enqueue_hook(cfg),  # type: ignore[arg-type]
    )
    app = create_compose_app(ComposeApiDeps(
        dsn=cfg.dsn, runner=runner,
        owner_scope_for_project=lambda _pid: Principal(kind="user", id=cfg.user_id),
        role_resolver=build_role_resolver(cfg.dsn),
    ))
    with TestClient(app) as client:
        response = client.post(
            f"/projects/{cfg.project_id}/report",
            json={"analysis_id": cfg.analysis_id, "template_id": cfg.template_id},
            headers={"X-User-Id": cfg.user_id},
        )
    if response.status_code != 200:
        raise SmokeFailure(
            "submit", f"提交端点返回 {response.status_code}：{response.text}"
        )
    result.job_id = response.json()["job_id"]
    result.steps.append(SmokeStep("submit", f"job_id={result.job_id}"))


async def _enqueue_check(cfg: SmokeConfig, result: SmokeResult) -> None:
    pool = await create_pool(RedisSettings.from_dsn(cfg.redis_url))
    try:
        queued = await pool.queued_jobs(queue_name=cfg.queue_name)
    finally:
        await pool.aclose()
    ids = [j.args[0] for j in queued if j.args]
    if result.job_id not in ids:
        raise SmokeFailure(
            "enqueue",
            f"提交成功但队列 {cfg.queue_name} 里没有它（队列现有 {ids}）——"
            "作业会永远停在 queued",
        )
    result.steps.append(SmokeStep("enqueue", f"queue={cfg.queue_name}"))


async def _consume(cfg: SmokeConfig, result: SmokeResult) -> None:
    worker = build_worker(_worker_deps(cfg), queue_name=cfg.queue_name, burst=True)
    try:
        await worker.async_run()
    finally:
        await worker.close()
    conn = await asyncpg.connect(cfg.dsn)
    try:
        row = await conn.fetchrow(
            "SELECT state, error FROM jobs WHERE job_id = $1", result.job_id
        )
    finally:
        await conn.close()
    if row is None:
        raise SmokeFailure("consume", f"jobs 表里没有 {result.job_id}")
    if row["state"] != "done":
        raise SmokeFailure(
            "consume",
            f"worker 跑完后作业状态是 {row['state']}（error={row['error']!r}），不是 done",
        )
    result.steps.append(SmokeStep("consume", "state=done"))


def _deliverable_client(cfg: SmokeConfig) -> TestClient:
    return TestClient(create_deliverables_app(DeliverableApiDeps(dsn=cfg.dsn)))


def _compose_check(cfg: SmokeConfig, result: SmokeResult) -> None:
    result.deliverable_id = f"del-{result.job_id}"
    with _deliverable_client(cfg) as client:
        response = client.get(f"/deliverables/{result.deliverable_id}/blocks")
    if response.status_code != 200:
        raise SmokeFailure(
            "compose", f"/blocks 返回 {response.status_code}：{response.text}"
        )
    blocks = response.json()["blocks"]
    if not blocks:
        raise SmokeFailure("compose", "/blocks 是空的——组稿没产出任何块")
    kinds = [b["type"] for b in blocks]
    if "paragraph" not in kinds:
        raise SmokeFailure(
            "compose",
            f"/blocks 里没有 paragraph（块型={kinds}）——占位生成器只产 heading，"
            "这说明生产生成器没接上",
        )
    result.blocks = blocks
    result.steps.append(SmokeStep("compose", f"blocks={len(blocks)}"))


def _render_check(cfg: SmokeConfig, result: SmokeResult) -> None:
    with _deliverable_client(cfg) as client:
        response = client.get(
            f"/deliverables/{result.deliverable_id}/render", params={"fmt": "markdown"}
        )
    if response.status_code == 409:
        raise SmokeFailure(
            "render",
            f"导出被门禁拦下：{response.json().get('detail')}",
        )
    if response.status_code != 200:
        raise SmokeFailure(
            "render", f"/render 返回 {response.status_code}：{response.text}"
        )
    if not response.text.strip():
        raise SmokeFailure("render", "/render 出了空 markdown")
    result.markdown = response.text
    result.steps.append(SmokeStep("render", f"markdown={len(response.text)}字符"))


async def run_e2e_smoke(cfg: SmokeConfig) -> SmokeResult:
    """跑一次主链。任一步断掉即抛 SmokeFailure，消息点名断在哪一步。"""
    result = SmokeResult()
    _submit(cfg, result)
    await _enqueue_check(cfg, result)
    await _consume(cfg, result)
    _compose_check(cfg, result)
    _render_check(cfg, result)
    return result


def render_status(cfg: SmokeConfig, deliverable_id: str) -> tuple[int, JSON]:
    """只跑导出这一步，返回 (status_code, body)——门禁两种用例都要看到它的原样输出。"""
    with _deliverable_client(cfg) as client:
        response = client.get(
            f"/deliverables/{deliverable_id}/render", params={"fmt": "markdown"}
        )
    if response.headers.get("content-type", "").startswith("application/json"):
        body: JSON = response.json()
    else:
        body = {"text": response.text}
    return response.status_code, body
