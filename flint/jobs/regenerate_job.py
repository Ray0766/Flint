"""regenerate Job 真执行（FE-CORE-005 e2e 接线）。

arq worker 消费者实调 dispatch_regenerate：载 DB（当前 block 树 + deliverable + 账本）
→ 建生产生成器（免费档 qwen3.6 via LocalProvider，注入闭包）→ 按 block_id 派发块级/
章节级 → **过真 draft_section_with_channels 通道门**（账本外事实拒稿）→ 落库（新
deliverable 版本 +1、supersedes 旧版、新 GenerationRecord、新 block 树）。

NEVER 绕门；guidance 只引导方向（FE-CORE-006）。生成器 provider 由上游注入——CI 用
录制回放/合成（离线，S2-7）；真机 qwen3.6 端到端为 owner 单一授权跑。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.compose.llm_generator import build_block_regenerator, llm_generator_factory
from flint.compose.templates import load_template
from flint.domain.models import GenerationRecord, UserProfile
from flint.domain.protocols import LLMProvider
from flint.jobs.regenerate_worker import dispatch_regenerate, parse_regenerate_payload
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
    """执行一个 regenerate Job → 返回新 deliverable_id。派发块级/章节级、过真门、落库。"""
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
