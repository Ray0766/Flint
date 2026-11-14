"""regenerate_section（M3-042，冻结协议 InterventionService.regenerate_section）。

- 只动目标节的未受保护块：受保护块自动原样携带（内容逐字节不动）；
  生成器若产出被改的受保护块 id，guard_rewrite（M3-028 统一出口）拒绝。
- 版本语义：新 Deliverable（版本 +1、supersedes 指旧版）+ 新 GenerationRecord
  + 新 block 树（旧版树原样留存可回读）；写入同一事务——guard 拒绝时
  零落库（无半写）。
- 携带块换绑 new deliverable_id 属版本复制的结构性重绑（S2-5 管内容改写，
  不管版本归属字段）；guard 在换绑**之前**以原样比对执行。
- 返回 job_id（编排身份由调用方注入；JobRunner 提交面归 M3-048 API 线）。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import asyncpg

from flint.compose.blocks import _to_row, is_protected
from flint.compose.deliverable import PgDeliverableStore
from flint.compose.protect import guard_rewrite
from flint.domain.models import Block, GenerationRecord

SectionGenerator = Callable[[list[Block]], list[Block]]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PgRegenerateService:
    def __init__(
        self, dsn: str, now: Callable[[], datetime] = _utcnow
    ) -> None:
        self._dsn = dsn
        self._now = now

    async def regenerate_section(
        self,
        deliverable_id: str,
        section_id: str,
        generator: SectionGenerator,
        new_deliverable_id: str,
        generation_record: GenerationRecord,
        job_id: str,
    ) -> str:
        from flint.compose.blocks import PgBlockStore

        block_store = PgBlockStore(dsn=self._dsn)
        deliverable_store = PgDeliverableStore(dsn=self._dsn)

        current_tree = await block_store.load_tree(deliverable_id)
        current = await deliverable_store.load_deliverable(deliverable_id)

        section_blocks = [b for b in current_tree if b.section_id == section_id]
        other_blocks = [b for b in current_tree if b.section_id != section_id]
        protected = [b for b in section_blocks if is_protected(b)]
        unprotected = [b for b in section_blocks if not is_protected(b)]

        generated = generator(list(unprotected))
        generated_ids = {b.block_id for b in generated}
        proposal = generated + [
            b for b in protected if b.block_id not in generated_ids
        ]
        guard_rewrite(section_blocks, proposal)  # 原样比对，先于换绑（S2-5）

        rebound = [
            replace(b, deliverable_id=new_deliverable_id)
            for b in [*other_blocks, *proposal]
        ]
        reindexed: list[Block] = []
        order_by_section: dict[str, int] = {}
        for block in sorted(rebound, key=lambda b: (b.section_id, b.order)):
            index = order_by_section.get(block.section_id, 0)
            reindexed.append(replace(block, order=index))
            order_by_section[block.section_id] = index + 1

        bumped = replace(
            current,
            deliverable_id=new_deliverable_id,
            version=current.version + 1,
            supersedes=current.deliverable_id,
            generation_record_id=generation_record.record_id,
        )
        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO generation_records (record_id, deliverable_id, "
                    "job_id, prompt_version, model, params, retrieval_snapshot_id, "
                    "ledger_version, pricebook_version, user_evidence_verdict_optin, "
                    "ts, cost, alignment_rate, structured_output_failures) VALUES "
                    "($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, "
                    "$13, $14)",
                    generation_record.record_id, generation_record.deliverable_id,
                    generation_record.job_id, generation_record.prompt_version,
                    generation_record.model,
                    json.dumps(generation_record.params, ensure_ascii=False),
                    generation_record.retrieval_snapshot_id,
                    generation_record.ledger_version,
                    generation_record.pricebook_version,
                    generation_record.user_evidence_verdict_optin,
                    generation_record.ts, generation_record.cost,
                    generation_record.alignment_rate,
                    generation_record.structured_output_failures,
                )
                await conn.execute(
                    "INSERT INTO deliverables (deliverable_id, project_id, type, "
                    "version, supersedes, inputs, ledger_version, "
                    "generation_record_id, stale_reasons, created_at, reproducible) "
                    "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9::jsonb, "
                    "$10, $11)",
                    bumped.deliverable_id, bumped.project_id, bumped.type,
                    bumped.version, bumped.supersedes,
                    json.dumps(bumped.inputs, ensure_ascii=False),
                    bumped.ledger_version, bumped.generation_record_id,
                    "[]", self._now(), bumped.reproducible,
                )
                for block in reindexed:
                    await conn.execute(
                        "INSERT INTO blocks (block_id, deliverable_id, section_id, "
                        "block_order, type, content, claim_ids, fact_ids, author, "
                        "revision, locked, user_modified, needs_review, "
                        "review_reason, review_severity) VALUES ($1, $2, $3, $4, "
                        "$5, $6::jsonb, $7::jsonb, $8::jsonb, $9, $10, $11, $12, "
                        "$13, $14, $15)",
                        *_to_row(block),
                    )
        finally:
            await conn.close()
        return job_id
