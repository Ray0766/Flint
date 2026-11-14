"""M1-016 acceptance tests: throttle + compliance layer.

Acceptance (tasks.json M1-016):
  - token bucket takes effect independently per source
  - a spot-check of stored tables finds no full-text body columns
    (metadata + links only, PDD v0.2 SS3.5)
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import asyncpg
import pytest

from flint.sources.throttle import (
    SourceThrottle,
    TokenBucket,
    check_metadata_only,
)

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ── token bucket semantics (fake clock) ───────────────────


def test_bucket_exhausts_and_refills() -> None:
    clock = [0.0]
    bucket = TokenBucket(capacity=2, refill_per_second=1.0, now=lambda: clock[0])
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False, "empty bucket must reject"
    clock[0] += 1.0
    assert bucket.try_acquire() is True, "one token refilled after 1s"
    assert bucket.try_acquire() is False
    clock[0] += 10.0
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False, "refill is capped at capacity"


def test_buckets_are_independent_per_source() -> None:
    clock = [0.0]
    throttle = SourceThrottle(now=lambda: clock[0])
    throttle.configure("weibo", capacity=1, refill_per_second=0.1)
    throttle.configure("gtrends", capacity=3, refill_per_second=0.1)

    assert throttle.try_acquire("weibo") is True
    assert throttle.try_acquire("weibo") is False, "weibo bucket exhausted"
    # gtrends keeps its own budget untouched by weibo's exhaustion
    assert throttle.try_acquire("gtrends") is True
    assert throttle.try_acquire("gtrends") is True
    assert throttle.try_acquire("gtrends") is True
    assert throttle.try_acquire("gtrends") is False


def test_unconfigured_source_rejected() -> None:
    throttle = SourceThrottle(now=lambda: 0.0)
    with pytest.raises(KeyError, match="tiktok"):
        throttle.try_acquire("tiktok")


# ── metadata-only compliance (DB spot check) ──────────────


@pytest.mark.compose
def test_live_schema_has_no_fulltext_columns() -> None:
    violations = run(check_metadata_only(DSN))
    assert violations == [], f"full-text columns found: {violations}"


@pytest.mark.compose
def test_checker_flags_synthetic_fulltext_column() -> None:
    async def scenario() -> list[tuple[str, str]]:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DROP TABLE IF EXISTS m1016_bad_docs")
            await conn.execute(
                "CREATE TABLE m1016_bad_docs (doc_id text PRIMARY KEY, "
                "url text, full_text text)"
            )
            try:
                return await check_metadata_only(DSN)
            finally:
                await conn.execute("DROP TABLE m1016_bad_docs")
        finally:
            await conn.close()

    violations = run(scenario())
    assert ("m1016_bad_docs", "full_text") in violations
