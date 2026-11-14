"""Block 树存取与保护谓词（M3-009，冻结件 Block / D3 / v0.3.2）。

- 树序 = (section_id, block_order) 稳定序；load_tree 恢复精确 content 类型
  （M3-008 block_io）。
- 保护谓词单点：is_protected（Python 面）与 PROTECTED_SQL_PREDICATE（SQL
  面）同源三条件——locked ∨ author=="user" ∨ user_modified；一切改写路径
  （M3-026/027/042）MUST 经此判定，受保护块改写抛 PermissionError。
- replace_block：revision 单调 +1（以库内现值为准，防丢失更新）。
"""
from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Final, Literal, cast

import asyncpg

from flint.compose.block_io import block_content_from_json, block_content_to_json
from flint.domain.models import Block, BlockType, ReviewReason, ReviewSeverity

# 域以 contracts/models.py#Block.author 为准（校验后精确 cast 惯用法）
BlockAuthor = Literal["system", "user"]

PROTECTED_SQL_PREDICATE: Final[str] = (
    "(locked OR author = 'user' OR user_modified)"
)


def is_protected(block: Block) -> bool:
    return block.locked or block.author == "user" or block.user_modified


def _to_row(block: Block) -> tuple[Any, ...]:
    return (
        block.block_id, block.deliverable_id, block.section_id, block.order,
        block.type, json.dumps(block_content_to_json(block.content),
                               ensure_ascii=False),
        json.dumps(block.claim_ids, ensure_ascii=False),
        json.dumps(block.fact_ids, ensure_ascii=False),
        block.author, block.revision, block.locked, block.user_modified,
        block.needs_review, block.review_reason, block.review_severity,
    )


def _from_row(row: asyncpg.Record) -> Block:
    review_reason = row["review_reason"]
    review_severity = row["review_severity"]
    return Block(
        block_id=row["block_id"],
        deliverable_id=row["deliverable_id"],
        section_id=row["section_id"],
        order=row["block_order"],
        type=cast(BlockType, row["type"]),
        content=block_content_from_json(json.loads(row["content"])),
        claim_ids=[str(c) for c in json.loads(row["claim_ids"])],
        fact_ids=[str(f) for f in json.loads(row["fact_ids"])],
        author=cast(BlockAuthor, row["author"]),
        revision=row["revision"],
        locked=row["locked"],
        user_modified=row["user_modified"],
        needs_review=row["needs_review"],
        review_reason=cast(ReviewReason, review_reason) if review_reason else None,
        review_severity=(
            cast(ReviewSeverity, review_severity) if review_severity else None
        ),
    )


_INSERT_SQL: Final[str] = (
    "INSERT INTO blocks (block_id, deliverable_id, section_id, block_order, type, "
    "content, claim_ids, fact_ids, author, revision, locked, user_modified, "
    "needs_review, review_reason, review_severity) VALUES ($1, $2, $3, $4, $5, "
    "$6::jsonb, $7::jsonb, $8::jsonb, $9, $10, $11, $12, $13, $14, $15)"
)


class PgBlockStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save_tree(self, deliverable_id: str, blocks: list[Block]) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM blocks WHERE deliverable_id = $1", deliverable_id
                )
                await conn.executemany(_INSERT_SQL, [_to_row(b) for b in blocks])
        finally:
            await conn.close()

    async def load_tree(self, deliverable_id: str) -> list[Block]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT * FROM blocks WHERE deliverable_id = $1 "
                "ORDER BY section_id, block_order",
                deliverable_id,
            )
        finally:
            await conn.close()
        return [_from_row(r) for r in rows]

    async def replace_block(self, block_id: str, updated: Block) -> Block:
        # 复合主键（0014）下 block_id 跨版本共存：以 updated.deliverable_id
        # 定位版本内该块
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM blocks WHERE block_id = $1 AND deliverable_id = $2",
                block_id, updated.deliverable_id,
            )
            if row is None:
                raise KeyError(f"unknown block: {block_id}")
            current = _from_row(row)
            if is_protected(current):
                raise PermissionError(
                    f"block {block_id} is protected "
                    "(locked or author=user or user_modified) and never rewritten"
                )
            bumped = replace(updated, revision=current.revision + 1)
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM blocks WHERE block_id = $1 AND deliverable_id = $2",
                    block_id, updated.deliverable_id,
                )
                await conn.execute(_INSERT_SQL, *_to_row(bumped))
            return bumped
        finally:
            await conn.close()
