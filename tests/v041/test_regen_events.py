"""REGEN-EVT-01：单块重写作业推状态、写事件——成功与失败都写（`DEC-063`）。

## 改前实测（`docs/blocked/REGENERATE-JOB-WRITES-NO-EVENTS.md`，2026-08-12 真栈）

重写作业**真的跑完了**：新版本、换过的正文、生成记录都在库里。而这两处一个字没动：

```
jobs        state = 'queued'（提交后 10 分钟仍是 queued）
job_events  0 行
```

轮询 `GET /jobs/{id}` 的屏一直转，订阅 `/jobs/{id}/events` 的屏永远收不到终态。
失败时也一样没有事件——屏上分不出「还在跑」与「已经失败」。

## 本文件守什么

1. 成功：`jobs.state` 到 `done`，事件流最后一条是 `status/done`，两个记号一起写；
2. 失败：`jobs.state` 到 `failed`，事件流里有一条带原因的 `failed`，**而且没有半写的产物**；
3. 推进状态走的是 `flint/jobs/state.py#enter_state` 那一处真相，NEVER 另写一套；
4. 作业行不在（判据或脚本直调、没经队列提交）时照常产出，一条事件都不写——
   NEVER 为了有地方写事件而替调用方造一行作业。
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.compose.deliverable import PgDeliverableStore
from flint.domain.models import Principal, UserProfile
from flint.jobs.regenerate_job import RegenerateJobDeps, run_regenerate_job
from flint.llm.prompts import load_prompt
from tests.fe_core import test_regen_job_e2e as base

REPO = Path(__file__).resolve().parents[2]
MODULE = REPO / "flint" / "jobs" / "regenerate_job.py"
SHEET = REPO / "docs" / "blocked" / "REGENERATE-JOB-WRITES-NO-EVENTS.md"
DSN = base.DSN

JOB_OK = "regenevt-ok"
JOB_BAD = "regenevt-bad"
JOB_ABSENT = "regenevt-not-submitted"
PAYLOAD: dict[str, object] = {
    "action": "regenerate_block", "deliverable_id": base.DID, "section_id": "summary",
    "project_id": base.PID, "block_id": "b2", "guidance": "更简洁、只用有据事实",
}


class _BrokenProvider:
    """模型端点挂了：生成那一步直接抛。"""

    model = "broken"

    def generate(self, prompt: str, tools: Any) -> Any:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: Any, max_retries: int) -> Any:
        raise RuntimeError("model endpoint unreachable")


def _deps(provider: Any) -> RegenerateJobDeps:
    return RegenerateJobDeps(
        dsn=DSN, provider=provider,
        prompt_text=load_prompt(REPO / "prompts", "section_draft@1").text,
        profile=UserProfile(
            profile_id="p", owner=Principal(kind="user", id="u"), identity={}, research={},
            team=[], assets={}, constraints={}, track_record=[], locale="zh-CN",
            sensitivity_overrides={}, updated_at=base.NOW),
        template_path=REPO / "assets" / "templates" / "generic.yaml",
        now=lambda: base.NOW)


async def _submit(job_id: str) -> None:
    """照 API 提交时的样子放一行 `queued` 的作业——事件流的外键指着它。"""
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute(
            "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
            "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
            "VALUES ($1, 'report', $2::jsonb, 'queued', 0, 0, 0, false, 'u', $3, $3)",
            job_id, json.dumps({"kind": "user", "id": "u"}), base.NOW)
    finally:
        await conn.close()


async def _state_and_events(job_id: str) -> tuple[str | None, list[dict[str, Any]]]:
    conn = await asyncpg.connect(DSN)
    try:
        state = await conn.fetchval("SELECT state FROM jobs WHERE job_id = $1", job_id)
        rows = await conn.fetch(
            "SELECT seq, payload FROM job_events WHERE job_id = $1 ORDER BY seq", job_id)
    finally:
        await conn.close()
    return state, [{"seq": r["seq"], **json.loads(r["payload"])} for r in rows]


async def _wipe() -> None:
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute("DELETE FROM job_events WHERE job_id LIKE 'regenevt-%'")
        await conn.execute("DELETE FROM jobs WHERE job_id LIKE 'regenevt-%'")
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _isolated(request: pytest.FixtureRequest) -> Any:
    """`_clean` 是重写 e2e 那份判据的隔离件（清 `fecore-e2e-*`），这里把本文件的作业行也清掉。"""
    # NARROW-03: only the compose tests touch the database; CI's unit stage has none.
    if request.node.get_closest_marker("compose") is None:
        yield
        return
    base.run(_wipe())
    yield
    base.run(_wipe())


_clean = base._clean


# ───────────────────────── 一、成功：两个记号一起到 done


@pytest.mark.compose
def test_a_finished_rewrite_reaches_done_in_both_places() -> None:
    base.run(base._seed())
    base.run(_submit(JOB_OK))

    new_id = base.run(run_regenerate_job(
        JOB_OK, dict(PAYLOAD), _deps(base.ReplayProvider(base._recorded_output()))))
    state, events = base.run(_state_and_events(JOB_OK))

    assert base.run(PgDeliverableStore(dsn=DSN).load_deliverable(new_id)).version == 2
    assert state == "done", f"产物落库了而 jobs.state 停在 {state}——轮询的屏会一直转"
    assert events, "事件流是空的——订阅 SSE 的屏永远收不到终态"
    assert events[-1]["kind"] == "status" and events[-1]["state"] == "done", events
    assert [e["seq"] for e in events] == sorted({e["seq"] for e in events}), "seq 没有严格递增"
    assert [e for e in events if e["kind"] == "failed"] == []


@pytest.mark.compose
def test_the_screen_can_see_it_start_before_it_ends() -> None:
    """终态之前先有一条「在写了」：否则屏上从提交到完成之间一个字都没有。"""
    base.run(base._seed())
    base.run(_submit(JOB_OK))

    base.run(run_regenerate_job(
        JOB_OK, dict(PAYLOAD), _deps(base.ReplayProvider(base._recorded_output()))))
    _state, events = base.run(_state_and_events(JOB_OK))
    states = [e["state"] for e in events if e["kind"] == "status"]

    assert states == ["drafting", "done"], states


# ───────────────────────── 二、失败：同样落事件，且没有半写


@pytest.mark.compose
def test_a_failed_rewrite_says_so_in_both_places_and_keeps_the_reason() -> None:
    base.run(base._seed())
    base.run(_submit(JOB_BAD))

    with pytest.raises(RuntimeError, match="unreachable"):
        base.run(run_regenerate_job(JOB_BAD, dict(PAYLOAD), _deps(_BrokenProvider())))
    state, events = base.run(_state_and_events(JOB_BAD))

    assert state == "failed", f"作业失败了而 jobs.state 是 {state}"
    failed = [e for e in events if e["kind"] == "failed"]
    assert len(failed) == 1, f"失败事件应当恰好一条，实得 {len(failed)}"
    assert "RuntimeError" in failed[0]["reason"] and "unreachable" in failed[0]["reason"], (
        f"失败事件没带原因：{failed[0]}")
    assert events[-1] == {"seq": events[-1]["seq"], "kind": "status", "state": "failed"}, (
        "最后一条不是终态——屏上会停在「在写了」")


@pytest.mark.compose
def test_a_failed_rewrite_leaves_no_half_written_product() -> None:
    base.run(base._seed())
    base.run(_submit(JOB_BAD))

    with pytest.raises(RuntimeError):
        base.run(run_regenerate_job(JOB_BAD, dict(PAYLOAD), _deps(_BrokenProvider())))

    with pytest.raises(Exception):  # noqa: B017 —— 仓库各存储层对「查无此份」抛的类型不一
        base.run(PgDeliverableStore(dsn=DSN).load_deliverable(f"{base.DID}-r-{JOB_BAD}"))


# ───────────────────────── 三、没经队列提交的直调：照常产出，不造作业行


@pytest.mark.compose
def test_a_direct_call_without_a_job_row_still_works_and_invents_nothing() -> None:
    base.run(base._seed())

    new_id = base.run(run_regenerate_job(
        JOB_ABSENT, dict(PAYLOAD), _deps(base.ReplayProvider(base._recorded_output()))))
    state, events = base.run(_state_and_events(JOB_ABSENT))

    assert new_id == f"{base.DID}-r-{JOB_ABSENT}"
    assert state is None, "为了写事件替调用方造了一行作业"
    assert events == []


# ───────────────────────── 四、源码面：推进状态只走那一处真相


def test_it_advances_through_the_single_advancer() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        and node.module == "flint.jobs.state" for alias in node.names}
    sql = [n.value for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)]

    assert "enter_state" in imported, "没有引用 flint/jobs/state.py#enter_state"
    assert not [s for s in sql if "UPDATE jobs" in s], "自己又写了一套推进状态的 SQL"


# ───────────────────────── 五、单据


def test_the_sheet_records_what_landed_and_what_is_still_open() -> None:
    """事件与状态这一半落地了；块级 `revision` 那一格 `DEC-063` 明说不在范围，单子不关。"""
    status = next(line for line in SHEET.read_text(encoding="utf-8").splitlines()
                  if line.startswith("**状态**"))

    assert "REGEN-EVT-01" in status
    assert "open" in status, "单子被整张关掉了——revision 那一格还没有答复"
    assert "revision" in status
