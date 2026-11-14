"""UIR-02：作业失败了，订阅的那一头要收得到。

## 改前（`docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md`，最要紧的那一处）

worker 派发作业、handler 抛了，`dispatch_job` 调 `mark_failed`。`mark_failed` 做的是

```sql
UPDATE jobs SET state = 'failed', error = … WHERE job_id = … AND state NOT IN ('done','cancelled')
```

**只改库，不写事件流。** 作业屏订阅的是 `/jobs/{id}/events`：它收到过 `drafting`，
之后什么都收不到，屏上一直是「在写」。2026-11-14 在真栈上见到：一条成文作业因为模型端点连不上
失败了，库里 `state=failed`、`error` 有文本，屏上停在 `drafting`，没有任何失败提示。

## 本文件守什么

1. 失败时两个记号一起写：`jobs.state` 到 `failed`，事件流里先一条带原因的 `failed`、再一条终态；
2. `jobs.error` 照旧落文本；
3. 已经是终态的作业不动：`done` / `cancelled` 一个字不改；已经 `failed` 且说过话的
   （重写作业自己会写，见 `REGEN-EVT-01`）只补 `error`，NEVER 再说一遍；
4. 推进状态走 `flint/jobs/state.py#enter_state` 那一处真相——`worker_main.py` 里不再有自己的那句 UPDATE。
"""
from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.jobs.worker_main import make_mark_failed
from tests.conftest import TEST_DSN

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "flint" / "jobs" / "worker_main.py"
SHEET = REPO / "docs" / "blocked" / "SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md"
REASON = "LocalProviderUnavailable: local endpoint unreachable"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _job(job_id: str, state: str, events: list[dict[str, str]] | None = None) -> None:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        await conn.execute(
            "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
            "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
            "VALUES ($1, 'report', $2::jsonb, $3, 0, 0, 0, false, 'u', now(), now())",
            job_id, json.dumps({"kind": "user", "id": "u"}), state)
        for seq, payload in enumerate(events or [], start=1):
            await conn.execute(
                "INSERT INTO job_events (job_id, seq, ts, payload) "
                "VALUES ($1, $2, now(), $3::jsonb)", job_id, seq, json.dumps(payload))
    finally:
        await conn.close()


async def _read(job_id: str) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        row = await conn.fetchrow("SELECT state, error FROM jobs WHERE job_id = $1", job_id)
        rows = await conn.fetch(
            "SELECT payload FROM job_events WHERE job_id = $1 ORDER BY seq", job_id)
    finally:
        await conn.close()
    events = [json.loads(r["payload"]) for r in rows]
    return (row["state"], row["error"], events) if row else (None, None, events)


async def _wipe() -> None:
    conn = await asyncpg.connect(TEST_DSN)
    try:
        await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'uir02-%'")
        await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'uir02-%'")
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _isolated() -> Any:
    _run(_wipe())
    yield
    _run(_wipe())


# ───────────────────────── 一、失败：两个记号一起写，原因在前、终态在后


@pytest.mark.parametrize("state", ["queued", "drafting"])
def test_a_failure_reaches_the_event_stream_with_its_reason(state: str) -> None:
    _run(_job("uir02-a", state))

    _run(make_mark_failed(TEST_DSN)("uir02-a", REASON))
    now_state, error, events = _run(_read("uir02-a"))

    assert now_state == "failed"
    assert error == REASON, "jobs.error 没落文本"
    assert events == [
        {"kind": "failed", "reason": REASON},
        {"kind": "status", "state": "failed"},
    ], "订阅的那一头收不到失败，或者顺序不对（最后一条必须是终态）"


# ───────────────────────── 二、已经是终态的不动


@pytest.mark.parametrize("state", ["done", "cancelled"])
def test_a_finished_or_cancelled_job_is_left_alone(state: str) -> None:
    _run(_job("uir02-b", state))

    _run(make_mark_failed(TEST_DSN)("uir02-b", REASON))

    assert _run(_read("uir02-b")) == (state, None, [])


def test_a_job_that_already_said_it_failed_is_not_told_twice() -> None:
    """重写作业自己会写失败事件（`REGEN-EVT-01`），随后异常抛到 worker，`mark_failed` 再来一次。

    这一次只该补上 `jobs.error`——屏上出现两条一样的「失败」，读起来像失败了两回。
    """
    spoken = [{"kind": "failed", "reason": REASON}, {"kind": "status", "state": "failed"}]
    _run(_job("uir02-c", "failed", spoken))

    _run(make_mark_failed(TEST_DSN)("uir02-c", REASON))
    state, error, events = _run(_read("uir02-c"))

    assert state == "failed"
    assert error == REASON, "已经 failed 的作业也要落下错误文本"
    assert events == spoken, "失败被说了两遍"


def test_an_unknown_job_id_is_a_no_op() -> None:
    """没有这一行就什么都不写——事件流的外键指着 `jobs`，硬写会抛，而抛了会盖掉原来那个错。"""
    _run(make_mark_failed(TEST_DSN)("uir02-nobody", REASON))

    assert _run(_read("uir02-nobody")) == (None, None, [])


# ───────────────────────── 三、源码面：只走那一处真相


def test_the_worker_no_longer_has_its_own_advancer() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    sql = [n.value for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        and node.module == "flint.jobs.state" for alias in node.names}

    assert not [s for s in sql if "UPDATE jobs SET state" in s], (
        "worker_main.py 里还有自己那句推状态的 UPDATE")
    assert "enter_state" in imported


def test_the_sheet_crosses_this_one_off_and_stays_open_for_the_rest() -> None:
    text = SHEET.read_text(encoding="utf-8")

    assert "**状态** open" in text, "另外五处还没接，单子不能关"
    assert "UIR-02" in text, "单子里没记下 mark_failed 这一处已经接上"
