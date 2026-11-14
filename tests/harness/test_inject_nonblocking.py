"""inject_evidence 不得憋死事件循环（坑一回归测试）。

背景：`CitationAligner.align` 是**同步**的（冻结 LLMProvider 协议本就同步；
LocalProvider 底层同步 httpx，一次判定可达数十秒）。它曾直接跑在 async 的
`inject_evidence` 里 → 阻塞整个事件循环，期间所有并发请求挂住。
这与 DEMO-NONBLOCK 修过的是同一个 bug 类（tests/harness/test_demo_nonblocking.py 同构）。

本测试的做法与当初一致：用一个「慢同步 aligner」顶替真 LLM（只替延迟，不替语义），
同时跑一个每 10ms 一拍的心跳协程，量**事件循环单次最长停顿**。
- 修前（aligner.align 裸跑在 async 里）：停顿 ≈ 慢调用总时长 → 远超阈值，FAIL。
- 修后（run_in_threadpool 挪出）：停顿 < 阈值，PASS。

零外部依赖：不连 DB、不连 LLM、不联网——store 用内存假件，只验并发行为。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import pytest

from flint.domain.models import Doc, EvidenceScore, Principal, UserEvidence
from flint.intervene.inject import inject_evidence

# 单次同步调用的模拟耗时；总阻塞量 = SLOW_SECONDS（只调一次 align）
SLOW_SECONDS = 0.6
# 心跳允许的单次最长停顿。修前会到 ~SLOW_SECONDS，修后应远低于此。
MAX_STALL_SECONDS = 0.25
HEARTBEAT_INTERVAL = 0.01


class SlowAligner:
    """慢**同步** aligner：语义同真件（返回一个 Alignment），只把耗时压进去。"""

    def align(
        self, claim: str, evidence: Doc, stage: Literal["verdict", "draft"]
    ) -> str:
        time.sleep(SLOW_SECONDS)  # 同步阻塞，模拟真 LLM 的几十秒
        return "unsupported"      # 不入账路径：不触碰 store.derive


class StubScorer:
    def strength(self, doc: Doc) -> EvidenceScore:
        # 逐字照冻结件 EvidenceScore（strength / axis / components），NEVER 自造字段
        return EvidenceScore(
            strength=50, axis="user_provided",
            components={"verifiable": 0.5, "firsthand": 0.5},
        )


@dataclass
class StubLedger:
    version: int = 1
    facts: tuple[Any, ...] = ()


class StubStore:
    """只需支持 unsupported 分支所走的读路径；不连 DB。"""

    dsn = "stub://no-db"

    async def load(self, project_id: str) -> StubLedger:
        return StubLedger()


async def _heartbeat(stop: asyncio.Event, stalls: list[float]) -> None:
    last = time.perf_counter()
    while not stop.is_set():
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        now = time.perf_counter()
        stalls.append(now - last)
        last = now


def test_inject_evidence_does_not_stall_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """事件循环单次最长停顿 MUST < MAX_STALL_SECONDS。

    本仓约定：同步测试函数内部走 asyncio.run（与 test_demo_nonblocking.py 同构），
    不依赖 pytest-asyncio 标记。
    """
    # unsupported 分支会读账本；用内存假件顶掉真 DB 读。
    import flint.intervene.inject as inject_mod

    async def _fake_get_ledger(dsn: str, project_id: str, version: int) -> StubLedger:
        return StubLedger()

    monkeypatch.setattr(inject_mod, "get_ledger", _fake_get_ledger, raising=False)

    ev = UserEvidence(
        evidence_id="ue-test",
        owner=Principal(kind="user", id="tester"),
        kind="link",
        content_ref="https://example.invalid/x",
        note="n",
        created_at=datetime(2026, 8, 2, tzinfo=UTC),
    )

    async def scenario() -> float:
        stalls: list[float] = []
        stop = asyncio.Event()
        hb = asyncio.create_task(_heartbeat(stop, stalls))
        # **必须先让心跳真正跑起来**：create_task 只是排程。
        # inject_evidence 在触到阻塞调用前没有任何 await，若不在此处让出一次，
        # 心跳的第一拍会排在阻塞**之后**才执行，基线时间戳因此错过整段阻塞
        # ——测试就会在有 bug 的代码上照样通过（本测试初版真的这样空转过一次）。
        await asyncio.sleep(HEARTBEAT_INTERVAL * 3)
        stalls.clear()  # 丢掉启动期的抖动，只量被测调用期间的停顿
        try:
            await inject_evidence(
                store=StubStore(),  # type: ignore[arg-type]
                project_id="proj-test",
                ev=ev,
                scorer=StubScorer(),  # type: ignore[arg-type]
                aligner=SlowAligner(),  # type: ignore[arg-type]
                claim_text="claim",
                expected_version=1,
            )
        finally:
            stop.set()
            await hb
        return max(stalls) if stalls else 0.0

    worst = asyncio.run(scenario())
    assert worst < MAX_STALL_SECONDS, (
        f"事件循环被憋住 {worst:.3f}s（阈值 {MAX_STALL_SECONDS}s）："
        "同步 aligner.align 又跑回事件循环上了，MUST 用 run_in_threadpool 挪出"
    )
