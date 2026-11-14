"""限频与合规层（M1-016，技术方案 E4 / PDD v0.2 §3.5）。

- 令牌桶按源独立：每源一桶（capacity + refill_per_second），互不占用配额；
  时钟注入可测。RequestPacer（M1-011）管请求间隔，本层管配额总量，二者叠加。
- 合规面（只存元数据+链接，§3.5）：check_metadata_only 巡检 public schema
  全部表，检出正文全文类列名即违规——采集层永不落原文正文。
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Final

import asyncpg

FULLTEXT_COLUMN_NAMES: Final[frozenset[str]] = frozenset(
    {
        "content", "body", "fulltext", "full_text", "raw_text",
        "raw_html", "html", "article_text", "page_content",
    }
)

# §3.5 合规面针对**采集数据**（外站全文不落库）；系统自产内容不在管辖：
# blocks.content 是本系统生成的 Block 树判别联合（M3-008），非抓取正文。
#
# ## doc_contents.content 是**被裁决放行的**，不是被漏掉的
#
# owner 2026-08-04 裁决方案 A（DOC-01 卡面原话）：证据正文进库。
# 那条裁决**覆盖**了 §3.5 原先「外站全文一律不落库」的口径——不是执行侧自己松的。
# 落点单独一张 `doc_contents`（DOC-02 / 迁移 0019），`docs` 表本身**仍然没有正文列**，
# §3.5 那句「Doc 无 content 字段」逐字仍然成立。
#
# **这条白名单只放行这一处**：别的表再长出 content / full_text / raw_html，
# 这把尺子照旧判红。放行一处与拆掉尺子是两件事。
#
# 上线前的合规手续见 `docs/上线前合规手续清单.md`（COMP-01）——
# 正文进库改变的是**存什么**，改不了**准不准抓**，后者仍由那张清单管。
#
# ## `templates.html` 走的是 `blocks.content` 那一档，不是 `doc_contents` 那一档
#
# `PERSIST-03`（迁移 0024）建的 `templates` 表存的是**固化后的模板 HTML**。
# 它与外站全文没有任何关系：那份 HTML 由用户自己的样板经
# `flint/design/solidify.py#to_slots` 变换而来——标记区域换成 `{{block:id}}`、
# 水印剥掉、**示例正文与示例数字一律拒绝放行**（残留即 `SolidifyBlocked`）。
# 换句话说，落进这一列的东西**只剩形状**，而「形状」正是本系统自产的部分。
#
# 所以它命中的是这条白名单开头那句「系统自产内容不在管辖」，
# 与 `blocks.content`（本系统生成的 Block 树）同档；
# **不**需要像 `doc_contents.content` 那样援引 owner 的 `DOC-01` 裁决——
# 那一条放行的是「外站正文进库」，是另一件事。
#
# 这一条同样只放行这一处：`templates` 表再长出别的正文类列，这把尺子照旧判红。
SYSTEM_GENERATED_ALLOWLIST: Final[frozenset[tuple[str, str]]] = frozenset(
    {("blocks", "content"), ("doc_contents", "content"), ("templates", "html")}
)


class TokenBucket:
    def __init__(
        self,
        capacity: int,
        refill_per_second: float,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity <= 0 or refill_per_second <= 0:
            raise ValueError("capacity and refill_per_second must be positive")
        self._capacity = float(capacity)
        self._rate = refill_per_second
        self._now = now
        self._tokens = float(capacity)
        self._updated = now()

    def _refill(self) -> None:
        current = self._now()
        elapsed = current - self._updated
        if elapsed > 0:
            self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
            self._updated = current

    def try_acquire(self) -> bool:
        self._refill()
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


class SourceThrottle:
    """Per-source bucket registry; sources never share quota."""

    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self._buckets: dict[str, TokenBucket] = {}

    def configure(
        self, source_id: str, capacity: int, refill_per_second: float
    ) -> None:
        self._buckets[source_id] = TokenBucket(
            capacity=capacity, refill_per_second=refill_per_second, now=self._now
        )

    def try_acquire(self, source_id: str) -> bool:
        bucket = self._buckets.get(source_id)
        if bucket is None:
            raise KeyError(f"no throttle configured for source: {source_id}")
        return bucket.try_acquire()


async def check_metadata_only(dsn: str) -> list[tuple[str, str]]:
    """Spot-check every public table for full-text body columns.
    Returns (table, column) violations; empty list = compliant."""
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )
    finally:
        await conn.close()
    return sorted(
        (r["table_name"], r["column_name"])
        for r in rows
        if r["column_name"].lower() in FULLTEXT_COLUMN_NAMES
        and (r["table_name"], r["column_name"]) not in SYSTEM_GENERATED_ALLOWLIST
    )
