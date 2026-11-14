"""compose job 编排 + 断点续跑（M3-060，技术方案 E4 / DraftCheckpoint）。

- 5 步线性：outline → freeze → draft → align → render；每步与 job_steps
  记录**同一事务**提交（先例 M1-035/M2-040），kill -9 零重放窗口；重跑读
  job_steps 跳已完成步。
- DraftCheckpoint(kind="draft", completed_section_ids, ledger_version)：
  outline 后空清单、draft 后全节、ledger_version 自 freeze 起回填。
- **同门原则执行位**（M3-042/048 复审备忘兑现）：draft 步产出一律经
  draft_section_with_channels（ledger-only + 三通道门）——初稿与再生成
  同门。
- 渐进交付：draft 步逐 block 发 PartialBlockEvent + 节级 partial_output_ref
  （M3-059）；align 步 alignment_rate 写回 generation_records（M3-024）；
  render 步 guarded_render（M3-037 门禁）出 markdown 快照。
- 确定性：固定时钟 + 确定性 id（del-/rec-/led-{job} 族 + canonical 快照）
  → 续跑产物 diff 为空；事件全序与一次跑完一致（步边界崩溃口径，
  M2-040 同款已知边界）。
"""
from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import asyncpg

from flint.align.stage1 import LLMCitationAligner
from flint.compose.align_gate import align_gate
from flint.compose.blocks import PgBlockStore
from flint.compose.deliverable import PgDeliverableStore
from flint.compose.draft import BlockGenerator
from flint.compose.draft_channels import draft_section_with_channels
from flint.compose.freeze import freeze_ledger
from flint.compose.progressive import emit_partial_blocks
from flint.compose.templates import load_template
from flint.domain.models import (
    JSON,
    Block,
    Completion,
    Deliverable,
    DraftCheckpoint,
    GenerationRecord,
    HeadingContent,
    JobState,
    Principal,
    SectionSpec,
    StepEvent,
    UserProfile,
)
from flint.domain.protocols import LLMProvider as LLMProviderProto
from flint.jobs.checkpoints import serialize_checkpoint
from flint.jobs.events import PgJobEventStream
from flint.jobs.state import enter_state
from flint.ledger.read import get_ledger
from flint.ledger.store import PgLedgerStore

STEP_ORDER: Final[list[str]] = ["outline", "freeze", "draft", "align", "render"]

_STEP_STATE: Final[dict[str, JobState]] = {
    "outline": "drafting",
    "freeze": "drafting",
    "draft": "drafting",
    "align": "validating",
    "render": "validating",
}


class _SupportsAligner:
    """离线确定性对齐 provider（章节离线场景恒 supports）。"""

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        raise RuntimeError("offline compose: free-form generation disabled")

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        return {"alignment": "supports"}


@dataclass
class ComposeDeps:
    dsn: str
    template_path: Path
    profile: UserProfile
    now: datetime
    generator_factory: Callable[[SectionSpec, str], BlockGenerator]
    # M4-039：生产 provider 经配置注入；None = 离线确定性对齐（CI 恒此路）
    aligner_provider: LLMProviderProto | None = None


def _aligner_provider(deps: ComposeDeps) -> LLMProviderProto:
    if deps.aligner_provider is not None:
        return deps.aligner_provider
    return _SupportsAligner()


@dataclass
class ComposeReport:
    job_id: str
    steps_run: list[str] = field(default_factory=list)


def _default_generator(spec: SectionSpec, deliverable_id: str) -> BlockGenerator:
    def generate(pool: list) -> list[Block]:  # type: ignore[type-arg]
        fact_ids = [pool[0].fact_id] if pool else []
        return [
            Block(
                block_id=f"b-{deliverable_id}-{spec.section_id}",
                deliverable_id=deliverable_id,
                section_id=spec.section_id,
                order=0,
                type="heading",
                content=HeadingContent(
                    kind="heading", level=2, text=spec.section_id
                ),
                claim_ids=[],
                fact_ids=fact_ids,
                author="system",
                revision=1,
                locked=False,
            )
        ]

    return generate


def build_offline_compose_deps(dsn: str, repo_root: Path) -> ComposeDeps:
    fixed_now = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
    profile = UserProfile(
        profile_id="p-owner", owner=Principal(kind="user", id="u-owner"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={},
        updated_at=fixed_now,
    )
    return ComposeDeps(
        dsn=dsn,
        template_path=repo_root / "assets" / "templates" / "generic.yaml",
        profile=profile,
        now=fixed_now,
        generator_factory=_default_generator,
    )


async def _ensure_job(conn: asyncpg.Connection, job_id: str, now: datetime) -> str:
    await conn.execute(
        "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
        "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
        "VALUES ($1, 'report', '{\"kind\":\"user\",\"id\":\"u-owner\"}', "
        "'queued', 0, 0, 0, false, 'u-owner', $2, $2) "
        "ON CONFLICT (job_id) DO NOTHING",
        job_id, now,
    )
    state: str = await conn.fetchval("SELECT state FROM jobs WHERE job_id = $1", job_id)
    return state


#: `DESIGN-STATE`：**推进状态只有一处真相**（`flint/jobs/state.py`）。
#: 改前这个函数在 compose / gate1 / spec_export 三处各有一份、逐字相同，
#: 而 `design_generate` 一份都没有——于是它只写事件流，`jobs.state` 停在 queued。
#: 这里保留同名别名，既有调用点一个都不用改。
_enter_state = enter_state


async def _completed_steps(conn: asyncpg.Connection, job_id: str) -> list[str]:
    rows = await conn.fetch(
        "SELECT name FROM job_steps WHERE job_id = $1 ORDER BY step_index", job_id
    )
    return [r["name"] for r in rows]


async def run_compose(
    job_id: str,
    project_id: str,
    source_deliverable_ids: list[str],
    deps: ComposeDeps,
    crash_after: str | None = None,
) -> ComposeReport:
    report = ComposeReport(job_id=job_id)
    events = PgJobEventStream(dsn=deps.dsn)
    ledger_ids = [0]

    def next_ledger_id() -> str:
        ledger_ids[0] += 1
        return f"led-{job_id}-{ledger_ids[0]:03d}"

    ledger_store = PgLedgerStore(
        dsn=deps.dsn, id_factory=next_ledger_id, now=lambda: deps.now
    )
    deliverable_id = f"del-{job_id}"
    record_id = f"rec-{job_id}"

    conn = await asyncpg.connect(deps.dsn)
    try:
        state = await _ensure_job(conn, job_id, deps.now)
        if state in ("done", "failed", "cancelled"):
            return report
        completed = await _completed_steps(conn, job_id)

        spec, section_specs = load_template(deps.template_path)
        section_ids = [sid for sid, _r in spec.sections]

        for index, name in enumerate(STEP_ORDER):
            await _enter_state(conn, events, job_id, _STEP_STATE[name], deps.now)
            if name in completed:
                continue
            await events.append(
                job_id,
                StepEvent(kind="step", step_name=name, phase="start", cost=None),
                ts=deps.now,
            )
            async with conn.transaction():
                completed_sections: list[str] = []
                ledger_version = 0
                if name == "outline":
                    pass  # 纯函数：outline 由模板确定性重算（先例 M2-040 plan）
                elif name == "freeze":
                    ledger = await freeze_ledger(
                        deps.dsn, ledger_store, project_id,
                        source_deliverable_ids, actor="u-owner",
                    )
                    ledger_version = ledger.version
                elif name == "draft":
                    ledger_version = await _current_ledger_version(
                        conn, project_id
                    )
                    ledger = await get_ledger(
                        deps.dsn, project_id, ledger_version
                    )
                    tree: list[Block] = []
                    for section_spec in section_specs:
                        blocks = draft_section_with_channels(
                            section_spec, ledger,
                            deps.generator_factory(section_spec, deliverable_id),
                            entries_by_id={}, profile=deps.profile,
                        )  # 同门原则：初稿经 ledger-only + 三通道门
                        tree.extend(blocks)
                    store = PgDeliverableStore(dsn=deps.dsn)
                    await store.save_generation_record(GenerationRecord(
                        record_id=record_id, deliverable_id=deliverable_id,
                        job_id=job_id, prompt_version="compose@1",
                        model="offline", params={},
                        retrieval_snapshot_id="none", ledger_version=ledger_version,
                        pricebook_version=None,
                        user_evidence_verdict_optin=False,
                        ts=deps.now, cost=0.0,
                    ))
                    await store.save_deliverable(Deliverable(
                        deliverable_id=deliverable_id, project_id=project_id,
                        type="report", version=1, supersedes=None,
                        inputs=source_deliverable_ids,
                        ledger_version=ledger_version,
                        generation_record_id=record_id, stale_reasons=[],
                        created_at=deps.now,
                    ))
                    await PgBlockStore(dsn=deps.dsn).save_tree(
                        deliverable_id, tree
                    )
                    await emit_partial_blocks(
                        deps.dsn, events, job_id, tree,
                        section_ref_factory=lambda s: f"partial-{deliverable_id}-{s}",
                        ts=deps.now,
                    )
                    completed_sections = section_ids
                elif name == "align":
                    ledger_version = await _current_ledger_version(conn, project_id)
                    aligner = LLMCitationAligner(provider=_aligner_provider(deps))
                    record = await PgDeliverableStore(
                        dsn=deps.dsn
                    ).load_generation_record(record_id)
                    result = align_gate(aligner, [], {}, record)
                    await conn.execute(
                        "UPDATE generation_records SET alignment_rate = $2 "
                        "WHERE record_id = $1",
                        record_id, result.record.alignment_rate,
                    )
                    completed_sections = section_ids
                else:  # render
                    ledger_version = await _current_ledger_version(conn, project_id)
                    from flint.render.gatekeeper import guarded_render
                    from flint.render.markdown import render_markdown

                    tree = await PgBlockStore(dsn=deps.dsn).load_tree(
                        deliverable_id
                    )
                    rendered = guarded_render(tree, render_markdown)
                    await conn.execute(
                        "INSERT INTO snapshots (snapshot_id, payload, created_at) "
                        "VALUES ($1, $2, $3)",
                        f"snap-{job_id}-render",
                        rendered.encode("utf-8"), deps.now,
                    )
                    await conn.execute(
                        "UPDATE jobs SET partial_output_ref = $2, updated_at = $3 "
                        "WHERE job_id = $1",
                        job_id, f"snap-{job_id}-render", deps.now,
                    )
                    completed_sections = section_ids
                checkpoint = DraftCheckpoint(
                    kind="draft",
                    completed_section_ids=completed_sections,
                    ledger_version=ledger_version,
                )
                await conn.execute(
                    "INSERT INTO job_steps (job_id, step_index, name, state, "
                    "started_at, ended_at, cost, snapshot_ref) VALUES "
                    "($1, $2, $3, 'done', $4, $4, 0, $5)",
                    job_id, index, name, deps.now,
                    serialize_checkpoint(checkpoint),
                )
            completed.append(name)
            report.steps_run.append(name)
            await events.append(
                job_id,
                StepEvent(kind="step", step_name=name, phase="end", cost=0.0),
                ts=deps.now,
            )
            if crash_after == name:
                os._exit(137)

        await _enter_state(conn, events, job_id, "done", deps.now)
    finally:
        await conn.close()
    return report


async def _current_ledger_version(
    conn: asyncpg.Connection, project_id: str
) -> int:
    version: int | None = await conn.fetchval(
        "SELECT MAX(version) FROM facts_ledgers WHERE project_id = $1", project_id
    )
    return version or 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="flint compose driver")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--sources", required=True)
    parser.add_argument("--crash-after", default=None)
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    deps = build_offline_compose_deps(dsn=args.dsn, repo_root=repo_root)
    asyncio.run(
        run_compose(
            job_id=args.job_id, project_id=args.project_id,
            source_deliverable_ids=args.sources.split(","),
            deps=deps, crash_after=args.crash_after,
        )
    )


if __name__ == "__main__":
    main()
