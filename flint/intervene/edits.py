"""EditEvent 沉淀（M3-047，冻结件 EditEvent / F3 数据资产）。

- 七枚举动作全落库（before/after 快照留痕可回放）。
- edit_text 命中 author=="system" 的 block → user_modified=True（v0.3.2；
  同一事务提交——事件与置位不脱节）；author=="user" 块本就受保护，不置位。
"""
from __future__ import annotations

import json

import asyncpg

from flint.domain.models import EditEvent


class PgEditService:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def record(self, event: EditEvent) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO edit_events (event_id, deliverable_id, section_id, "
                    "block_id, action, before, after, user_id, ts) VALUES "
                    "($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9)",
                    event.event_id, event.deliverable_id, event.section_id,
                    event.block_id, event.action,
                    json.dumps(event.before, ensure_ascii=False)
                    if event.before is not None else None,
                    json.dumps(event.after, ensure_ascii=False)
                    if event.after is not None else None,
                    event.user_id, event.ts,
                )
                if event.action == "edit_text" and event.block_id is not None:
                    await conn.execute(
                        "UPDATE blocks SET user_modified = true "
                        "WHERE block_id = $1 AND author = 'system'",
                        event.block_id,
                    )
        finally:
            await conn.close()

    async def events_for(self, deliverable_id: str) -> list[EditEvent]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT * FROM edit_events WHERE deliverable_id = $1 ORDER BY ts",
                deliverable_id,
            )
        finally:
            await conn.close()
        return [
            EditEvent(
                event_id=r["event_id"],
                deliverable_id=r["deliverable_id"],
                section_id=r["section_id"],
                block_id=r["block_id"],
                action=r["action"],
                before=json.loads(r["before"]) if r["before"] is not None else None,
                after=json.loads(r["after"]) if r["after"] is not None else None,
                user_id=r["user_id"],
                ts=r["ts"],
            )
            for r in rows
        ]
