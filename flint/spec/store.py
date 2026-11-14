"""spec 数据面（M4-001，冻结件 TaskSpec 持久化）。"""
from __future__ import annotations

import json

import asyncpg

from flint.domain.models import TaskSpec


def _row(spec_set_id: str, position: int, task: TaskSpec) -> tuple[object, ...]:
    return (
        spec_set_id, task.task_id, task.title,
        json.dumps(task.inputs, ensure_ascii=False),
        json.dumps(task.outputs, ensure_ascii=False),
        json.dumps(task.acceptance, ensure_ascii=False),
        json.dumps(task.depends_on, ensure_ascii=False),
        task.milestone, task.estimate_days, task.estimate_cycles,
        task.oneshot, task.verify_cmd,
        json.dumps(task.context_refs, ensure_ascii=False)
        if task.context_refs is not None else None,
        task.review_gate, position,
    )


class PgSpecStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save_set(self, spec_set_id: str, tasks: list[TaskSpec]) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM task_specs WHERE spec_set_id = $1", spec_set_id
                )
                await conn.executemany(
                    "INSERT INTO task_specs (spec_set_id, task_id, title, inputs, "
                    "outputs, acceptance, depends_on, milestone, estimate_days, "
                    "estimate_cycles, oneshot, verify_cmd, context_refs, "
                    "review_gate, position) VALUES ($1, $2, $3, $4::jsonb, "
                    "$5::jsonb, $6::jsonb, $7::jsonb, $8, $9, $10, $11, $12, "
                    "$13::jsonb, $14, $15)",
                    [_row(spec_set_id, i, t) for i, t in enumerate(tasks)],
                )
        finally:
            await conn.close()

    async def load_set(self, spec_set_id: str) -> list[TaskSpec]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT * FROM task_specs WHERE spec_set_id = $1 ORDER BY position",
                spec_set_id,
            )
        finally:
            await conn.close()
        return [
            TaskSpec(
                task_id=r["task_id"], title=r["title"],
                inputs=json.loads(r["inputs"]),
                outputs=json.loads(r["outputs"]),
                acceptance=json.loads(r["acceptance"]),
                depends_on=json.loads(r["depends_on"]),
                milestone=r["milestone"],
                estimate_days=r["estimate_days"],
                estimate_cycles=r["estimate_cycles"],
                oneshot=r["oneshot"], verify_cmd=r["verify_cmd"],
                context_refs=(
                    json.loads(r["context_refs"])
                    if r["context_refs"] is not None else None
                ),
                review_gate=r["review_gate"],
            )
            for r in rows
        ]
