"""regenerate Job 真执行（FE-CORE-005 e2e 接线）。

arq worker 消费者实调 dispatch_regenerate：载 DB（当前 block 树 + deliverable + 账本）
→ 建生产生成器（免费档 qwen3.6 via LocalProvider，注入闭包）→ 按 block_id 派发块级/
章节级 → **过真 draft_section_with_channels 通道门**（账本外事实拒稿）→ 落库（新
deliverable 版本 +1、supersedes 旧版、新 GenerationRecord、新 block 树）。

NEVER 绕门；guidance 只引导方向（FE-CORE-006）。生成器 provider 由上游注入——CI 用
录制回放/合成（离线，S2-7）；真机 qwen3.6 端到端为 owner 单一授权跑。

## 状态与事件（`REGEN-EVT-01` / `DEC-063`）

改前本模块只写产物，不碰 `jobs` 也不写 `job_events`：作业跑完了，`jobs.state` 停在
`queued`、事件流 0 行，屏上没有任何办法知道它结束了；失败时同样一个字没有
（单 `docs/blocked/REGENERATE-JOB-WRITES-NO-EVENTS.md`，2026-08-12 真栈实测）。

现在照 `run_compose` 的做法走 `flint/jobs/state.py#enter_state`——**那一处真相**，
库里那一行与事件流一起写：开工 `drafting`，落库后 `done`；任何一步抛了就先追加一条带原因的
`failed` 事件、再推到 `failed`，然后把异常原样抛回去（worker 那一层还要往 `jobs.error` 落文本）。

作业行不在——没经队列提交的直调（判据、脚本）——照常产出，一条事件都不写。
NEVER 为了有地方写事件而替调用方造一行作业：那一行的发起人与归属只能是编的。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import asyncpg

from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.compose.llm_generator import build_block_regenerator, llm_generator_factory
from flint.compose.templates import load_template
from flint.domain.models import GenerationRecord, JobFailedEvent, UserProfile
from flint.domain.protocols import LLMProvider
from flint.jobs.events import PgJobEventStream
from flint.jobs.regenerate_worker import dispatch_regenerate, parse_regenerate_payload
from flint.jobs.state import enter_state
from flint.ledger.read import get_ledger


@dataclass
class RegenerateJobDeps:
    dsn: str
    provider: LLMProvider
    prompt_text: str
    profile: UserProfile
    template_path: Path
    now: Callable[[], datetime]


async def run_regenerate_job(
    job_id: str, payload: dict[str, object], deps: RegenerateJobDeps,
) -> str:
    """执行一个 regenerate Job → 返回新 deliverable_id；成功与失败都推状态、写事件。"""
    events = PgJobEventStream(dsn=deps.dsn)
    conn = await asyncpg.connect(deps.dsn)
    try:
        submitted: bool = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM jobs WHERE job_id = $1)", job_id)
        if not submitted:
            return await _regenerate(job_id, payload, deps)
        await enter_state(conn, events, job_id, "drafting", deps.now())
        try:
            new_deliverable_id = await _regenerate(job_id, payload, deps)
        except Exception as err:
            # 先说原因，再说终态：订阅的屏按到达顺序读，最后一条必须是终态。
            await events.append(
                job_id,
                JobFailedEvent(kind="failed", reason=f"{type(err).__name__}: {err}"),
                ts=deps.now(),
            )
            await enter_state(conn, events, job_id, "failed", deps.now())
            raise
        await enter_state(conn, events, job_id, "done", deps.now())
        return new_deliverable_id
    finally:
        await conn.close()


async def _regenerate(
    job_id: str, payload: dict[str, object], deps: RegenerateJobDeps,
) -> str:
    """派发块级/章节级、过真门、落库。只管产物，不管作业状态。"""
    req = parse_regenerate_payload(payload)
    block_store = PgBlockStore(dsn=deps.dsn)
    deliverable_store = PgDeliverableStore(dsn=deps.dsn)

    current_tree = await block_store.load_tree(req.deliverable_id)
    current = await deliverable_store.load_deliverable(req.deliverable_id)
    if current.ledger_version is None:
        raise ValueError(f"deliverable {req.deliverable_id} has no ledger_version")
    ledger_version = current.ledger_version
    ledger = await get_ledger(deps.dsn, req.project_id, ledger_version)
    _, section_specs = load_template(deps.template_path)
    spec = next(s for s in section_specs if s.section_id == req.section_id)

    new_deliverable_id = f"{req.deliverable_id}-r-{job_id}"
    section_generator = llm_generator_factory(
        deps.provider, deps.prompt_text, req.guidance,
    )(spec, new_deliverable_id)
    block_regenerator = build_block_regenerator(
        deps.provider, deps.prompt_text, req.guidance,
    )
    # 过真通道门（账本外事实 → DraftViolation，落库前抛，零半写）。
    new_tree = dispatch_regenerate(
        req, current_tree, spec, ledger, {}, deps.profile, new_deliverable_id,
        section_generator, block_regenerator,
    )

    record = GenerationRecord(
        record_id=f"rec-{job_id}", deliverable_id=new_deliverable_id, job_id=job_id,
        prompt_version="section_draft@1",
        model=str(getattr(deps.provider, "model", "local")),
        params={"action": req.action, "block_id": req.block_id or "",
                "guidance": req.guidance or ""},
        retrieval_snapshot_id="none", ledger_version=ledger_version,
        pricebook_version=None, user_evidence_verdict_optin=False,
        ts=deps.now(), cost=0.0,
    )
    await deliverable_store.save_generation_record(record)
    bumped = replace(
        current, deliverable_id=new_deliverable_id, version=current.version + 1,
        supersedes=current.deliverable_id, generation_record_id=record.record_id,
    )
    await deliverable_store.save_deliverable(bumped)
    await block_store.save_tree(new_deliverable_id, new_tree)
    return new_deliverable_id
