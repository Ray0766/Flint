"""渐进交付：PartialBlockEvent（M3-059，D8 / v0.3.1 §4）。

- draft 逐 block 产 PartialBlockEvent（seq 续 M1-034 单调流，绝不重启）；
- 每节完成后更新 jobs.partial_output_ref（断线客户端先 GET 快照携最新
  section 引用，再 Last-Event-ID 续流——重连三步曲的服务端半边）。
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import asyncpg

from flint.domain.models import Block, PartialBlockEvent
from flint.jobs.events import PgJobEventStream


async def emit_partial_blocks(
    dsn: str,
    events: PgJobEventStream,
    job_id: str,
    blocks: list[Block],
    section_ref_factory: Callable[[str], str],
    ts: datetime,
) -> list[str]:
    conn = await asyncpg.connect(dsn)
    try:
        refs: list[str] = []
        current_section: str | None = None
        for block in sorted(blocks, key=lambda b: (b.section_id, b.order)):
            if block.section_id != current_section:
                if current_section is not None:
                    refs.append(section_ref_factory(current_section))
                    await conn.execute(
                        "UPDATE jobs SET partial_output_ref = $2, updated_at = $3 "
                        "WHERE job_id = $1",
                        job_id, refs[-1], ts,
                    )
                current_section = block.section_id
            await events.append(
                job_id,
                PartialBlockEvent(kind="partial_block", block_id=block.block_id),
                ts=ts,
            )
        if current_section is not None:
            refs.append(section_ref_factory(current_section))
            await conn.execute(
                "UPDATE jobs SET partial_output_ref = $2, updated_at = $3 "
                "WHERE job_id = $1",
                job_id, refs[-1], ts,
            )
        return refs
    finally:
        await conn.close()
