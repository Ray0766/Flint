"""API 硬化（M3-056，M2 出口遗留 2 收口）。

- claim_idempotency：先建 job 再声明幂等键——INSERT..ON CONFLICT DO
  NOTHING 后**回读胜者** job_id；败者把自己刚建的孤儿 job 置 cancelled
  并返回胜者 id——「重复提交返回原 job_id」在并发面也成立。
- parse_last_event_id：畸形头 → LastEventIdInvalid（端点译 400
  VALIDATION_FAILED，绝不 500）。
"""
from __future__ import annotations

from datetime import UTC, datetime

import asyncpg

from flint.domain.models import Principal


class LastEventIdInvalid(Exception):
    def __init__(self, raw: str) -> None:
        super().__init__(f"Last-Event-ID must be a non-negative integer: {raw!r}")
        self.raw = raw


def parse_last_event_id(raw: str | None) -> int:
    if raw is None:
        return 0
    stripped = raw.strip()
    if not stripped.isdigit():
        raise LastEventIdInvalid(raw)
    return int(stripped)


async def claim_idempotency(
    dsn: str, principal: Principal, key: str, my_job_id: str
) -> str:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            "INSERT INTO idempotency_keys (principal_kind, principal_id, idem_key, "
            "job_id, created_at) VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT ON CONSTRAINT pk_idempotency DO NOTHING",
            principal.kind, principal.id, key, my_job_id, datetime.now(UTC),
        )
        winner: str = await conn.fetchval(
            "SELECT job_id FROM idempotency_keys WHERE principal_kind = $1 "
            "AND principal_id = $2 AND idem_key = $3",
            principal.kind, principal.id, key,
        )
        if winner != my_job_id:
            # 败者：孤儿 job 立即取消（审6 阶段边界=queued 即时落）
            await conn.execute(
                "UPDATE jobs SET state = 'cancelled', cancel_requested = true, "
                "updated_at = $2 WHERE job_id = $1 AND state = 'queued'",
                my_job_id, datetime.now(UTC),
            )
        return winner
    finally:
        await conn.close()
