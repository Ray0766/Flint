"""Keyword 仓储：幂等 upsert（M1-021，contracts/models.py#Keyword）。

- 幂等键 = (canonical, lang)（migration-0001 的 UNIQUE 约束）。
- 冲突时更新 aliases 与 embedding（最新形态），keyword_id 与 first_seen
  保持首见值不被覆盖（验收硬条款）。
- embedding 以 pgvector 文本形态写入（::vector 转换）。
"""
from __future__ import annotations

import json

import asyncpg

from flint.domain.models import Keyword

_UPSERT_SQL = """
INSERT INTO keywords (keyword_id, canonical, lang, aliases, embedding, first_seen)
VALUES ($1, $2, $3, $4::jsonb, $5::vector, $6)
ON CONFLICT (canonical, lang) DO UPDATE SET
    aliases = EXCLUDED.aliases,
    embedding = EXCLUDED.embedding
RETURNING keyword_id
"""


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(v) for v in embedding) + "]"


async def upsert_keywords_on(
    conn: asyncpg.Connection, keywords: list[Keyword]
) -> dict[tuple[str, str], str]:
    """Connection-scoped variant: caller owns the transaction boundary
    (M1-040：步数据与 job_steps 记录同事务提交)。"""
    result: dict[tuple[str, str], str] = {}
    for kw in keywords:
        stored_id: str = await conn.fetchval(
            _UPSERT_SQL,
            kw.keyword_id,
            kw.canonical,
            kw.lang,
            json.dumps(kw.aliases, ensure_ascii=False),
            _vector_literal(kw.embedding),
            kw.first_seen,
        )
        result[(kw.canonical, kw.lang)] = stored_id
    return result


async def upsert_keywords(
    dsn: str, keywords: list[Keyword]
) -> dict[tuple[str, str], str]:
    """Upsert a batch; returns (canonical, lang) -> stored keyword_id."""
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            return await upsert_keywords_on(conn, keywords)
    finally:
        await conn.close()
