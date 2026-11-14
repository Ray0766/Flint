"""DEMO-NONBLOCK：合并 demo 后端 async handler 内 NEVER 有裸同步阻塞（LLM/网络）调用。

根因回归：LocalProvider 是同步（冻结 LLMProvider 协议本就同步，httpx.Client）。一次 combo
生成 ~75s 若直接在 async handler 里跑，会阻塞整个事件循环 → 并发请求（/plaza 等）全挂 →
前端 Failed to fetch。修法：把同步 provider 调用挪出事件循环（run_in_threadpool）。

本测用「慢同步 provider」（每次 generate_structured sleep）+ 心跳协程测事件循环最长停顿：
- 阻塞（修前）：orchestrate_combo 在 loop 上跑，心跳被憋住一次 ≈ 全部同步耗时（远超阈值）→ 失败。
- 非阻塞（修后）：同步活在线程池，loop 空闲，心跳最长间隔 << 阈值 → 通过。

复用 TS-010 既有合成 provider/DB 装置（真机 qwen NEVER 触）；需 compose 本地 PG。
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

import asyncpg
import httpx
import pytest

from flint.api.combo import ComboApiDeps, create_combo_app
from flint.domain.models import JSON
from flint.embed import DeterministicHashBackend, EmbeddingService
from tests.topic.test_ts_010_combo_api import _payload, _pick_cross_cluster

pytestmark = pytest.mark.compose

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_nb() -> Any:
    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for stmt in (
                "DELETE FROM projects WHERE project_id LIKE 'proj-ts010nb%'",
                "DELETE FROM topics WHERE topic_id LIKE 'topic-ts010nb%'",
                "DELETE FROM generation_records WHERE record_id LIKE 'gr-ts010nb%'",
                "DELETE FROM topic_seeds WHERE seed_id LIKE 'seed-ts010nb%'",
                "DELETE FROM origins WHERE origin_id LIKE 'origin-ts010nb%'",
            ):
                await conn.execute(stmt)
        finally:
            await conn.close()
    asyncio.run(wipe())
    yield
    asyncio.run(wipe())


_PER_CALL_SLEEP = 0.12          # 每次同步 LLM 调用的模拟延迟（真机 ~秒级/更长）
_MAX_STALL = 0.25               # 事件循环单次最长可容忍停顿；阻塞态会远超此值


class SlowSyncProvider:
    """同步 provider，每次 generate_structured 裸 time.sleep —— 模拟真机同步 LLM 长耗时。"""

    def __init__(self) -> None:
        self._i = 0
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        time.sleep(_PER_CALL_SLEEP)          # 裸同步阻塞（修前会憋住整个 loop）
        payload = _payload(self._i)
        self._i += 1
        self.calls += 1
        return payload


def _combo_app(provider: Any) -> Any:
    counter = {"n": 0}

    def id_factory() -> str:
        counter["n"] += 1
        return f"ts010nb{counter['n']}"

    return create_combo_app(ComboApiDeps(
        dsn=DSN, provider=provider,
        embed_service=EmbeddingService(DeterministicHashBackend(dim=1024)),
        model="qwen3.6", id_factory=id_factory, now=lambda: NOW, target=6))


def test_combo_does_not_block_event_loop() -> None:
    cards = asyncio.run(_pick_cross_cluster(2))
    provider = SlowSyncProvider()
    app = _combo_app(provider)

    async def scenario() -> float:
        stamps: list[float] = []
        stop = asyncio.Event()

        async def heartbeat() -> None:
            # 每 ~10ms 记一拍；事件循环若被同步调用憋住，相邻拍间隔 = 停顿时长
            while not stop.is_set():
                stamps.append(time.monotonic())
                await asyncio.sleep(0.01)

        hb = asyncio.create_task(heartbeat())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            resp = await c.post(
                "/projects/combo",
                json={"card_ids": cards, "hypothesis": "并发非阻塞回归"},
                headers={"X-User-Id": "u-nb"})
        stop.set()
        await hb
        assert resp.status_code == 200, resp.text
        return max((b - a for a, b in pairwise(stamps)), default=0.0)

    max_gap = asyncio.run(scenario())
    # 生成确实发生了（多次同步调用），且事件循环全程未被憋住超过阈值
    assert provider.calls >= 5, f"combo 未触发预期次数同步生成：calls={provider.calls}"
    assert max_gap < _MAX_STALL, (
        f"事件循环被同步 LLM 调用阻塞：最长停顿 {max_gap:.3f}s ≥ {_MAX_STALL}s "
        f"（同步生成总耗时约 {provider.calls * _PER_CALL_SLEEP:.2f}s 全砸在 loop 上）")
