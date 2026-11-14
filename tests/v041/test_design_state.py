"""DESIGN-STATE：作业跑完没有——**这件事只能有一个答案**。

## 实况（`SMOKE-01` 2026-08-11 实测）

`design_generate` 那一跑**真的产出了 192 个片段的设计稿**，
事件流最后一条是 `{"kind":"status","state":"done"}`——
**而 `jobs.state` 停在 `queued`**。

| 看哪里 | 说什么 |
|---|---|
| `job_events`（SSE 那一路） | 已完成 |
| `jobs.state`（轮询那一路） | **排队中** |

> 用户侧症状：「点了生成，转圈不停，而内容其实已经出来了」。
> 看起来像卡死，实际是两块表没对上。

`compose` 那一族是对的，所以这不是状态机整体没接，是设计生成**漏了收尾那一步**。

## 修法：走同一条路，NEVER 另写一套

owner 逐字：「修它 MUST 走与 compose 同一条收尾路径，
NEVER 另写一套推进状态的代码——两套推进器会让『作业跑完没有』再长出第三个真相」。

改前 `_enter_state` 在**三处**各有一份（`compose` · `gate1` · `spec_export`），
逻辑逐字相同；而 `design_generate` **一份都没有**。
现在只有 `flint/jobs/state.py#enter_state` 一处，四族都引用它。

## 为什么它当初写不了那一半

`DesignGenerateDeps` 里**没有任何库句柄**——手上没有连接，那一半就写不了。
本卡加了 `dsn`，并且 `dsn is None` 时**照实什么都不做**，NEVER 假装推过了。
"""
from __future__ import annotations

import asyncio
import inspect
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.jobs.design_generate import DesignGenerateDeps, run_design_generate
from flint.jobs.state import enter_state

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


# ───────────────────────── 一、推进状态只有一处


def test_every_family_uses_the_one_advancer() -> None:
    """四族**指向同一个函数对象**，不是四份长得一样的。

    四份内容相同的实现在今天分不出来，而它们会各自漂移——
    而漂移的症状是「有的族推了状态，有的族没推」，
    在盘上表现为「作业跑完没有」这件事有两个答案。
    """
    from flint.jobs import compose, gate1, spec_export

    for module in (compose, gate1, spec_export):
        assert module._enter_state is enter_state, (
            f"{module.__name__} 又自己写了一份推进器")


#: 改 `jobs.state` 而**不写事件流**的那六处（`DESIGN-STATE` 扫全仓实测）。
#:
#: 它们是本卡这条病的**镜像**：design 只写事件流（轮询的屏看不见），
#: 这六处只写库（订阅 SSE 的屏看不见）。**已知、已开单、不在本卡射程**——
#: `docs/blocked/SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md`。
#:
#: 写成清单而不是「跳过全部」：**多出一个就会红**，
#: 那正是「还没出现的第七处」要被拦下的地方。
_KNOWN_WITHOUT_EVENTS = {
    "flint/api/hardening.py",
    "flint/jobs/ingest.py",
    "flint/jobs/pricebook_scan.py",
    "flint/jobs/revalidation.py",
    "flint/jobs/runner.py",
    # `flint/jobs/worker_main.py`（`mark_failed`）2026-11-14 由 `UIR-02` 接上了：
    # 它不再自己 UPDATE，改走 `enter_state`。清单从六处减到五处。
}


def test_no_new_advancer_appears_outside_the_one_truth() -> None:
    """全仓 NEVER 出现**新的**一处 `UPDATE jobs SET state`。

    第一版写的是「除 `state.py` 外一处都不许有」——**那判过头了**：
    库里另有六处合法的状态推进（`failed` / `cancelled` / 中间态），
    它们的问题不是「存在」，是**不写事件流**（另开一单）。

    所以这里钉的是**清单不增长**：多出一个就红，
    而那个新的会在没人注意时又长出一个「作业跑完没有」的答案。
    """
    offenders: list[str] = []
    truth = REPO / "flint" / "jobs" / "state.py"
    for path in sorted((REPO / "flint").rglob("*.py")):
        if path == truth or "__pycache__" in path.parts:
            continue
        code = "\n".join(ln for ln in path.read_text(encoding="utf-8").splitlines()
                         if not ln.strip().startswith("#"))
        if "UPDATE jobs SET state" in code:
            offenders.append(path.relative_to(REPO).as_posix())

    appeared = sorted(set(offenders) - _KNOWN_WITHOUT_EVENTS)
    assert appeared == [], (
        f"这些文件里出现了新的一套推进器：{appeared}——"
        f"推进状态只有一处真相（flint/jobs/state.py#enter_state）")
    gone = sorted(_KNOWN_WITHOUT_EVENTS - set(offenders))
    assert gone == [], (
        f"这些已经接上了：{gone}——去 SIX-FAMILIES 那张单里划掉它们")


def test_the_mirror_bug_is_on_the_record() -> None:
    """那六处**只写库不写事件**这件事，有单据、有证据。

    没有单据的话，下一个人扫到同一批文件会以为它们本来就该那样。
    """
    sheet = (REPO / "docs" / "blocked"
             / "SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT.md")

    assert sheet.exists()
    text = sheet.read_text(encoding="utf-8")
    assert "**状态** open" in text
    assert "mark_failed" in text, "没点名最要紧的那一处"
    for path in _KNOWN_WITHOUT_EVENTS:
        assert path.split("/")[-1] in text, f"单据里没写 {path}"


def test_the_advancer_writes_both_marks() -> None:
    """一次推进 MUST **同时**写库里那一行与事件流。

    只写一个正是本卡要治的病——判源码里两句都在，
    且 `enter_state` 是**同一个函数**里做的，不是两个可以分别忘记的步骤。
    """
    source = inspect.getsource(enter_state)

    assert "UPDATE jobs SET state" in source
    assert "StatusChanged" in source
    assert "if current == target:" in source, "幂等那一支没了——同一状态会推两条事件"


# ───────────────────────── 二、design 真的会推了（打真库）


class _Provider:
    def generate(self, prompt: str, tools: Any = None) -> Any:
        class _R:
            text = "这是一段完整的中文设计稿，用来证明作业真的产出了东西。"

        return _R()


class _Events:
    """真事件流的替身：只记不落库（`jobs.state` 那一半由真库判）。"""

    def __init__(self) -> None:
        self.appended: list[Any] = []

    async def append(self, job_id: str, payload: Any, ts: datetime) -> Any:
        self.appended.append(payload)
        return payload

    async def replay(self, job_id: str, after_seq: int) -> list[Any]:
        return []


def _rows(sql: str, *args: Any) -> list[Any]:
    async def _go() -> list[Any]:
        conn = await asyncpg.connect(DSN)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_go())


def _exec(sql: str, *args: Any) -> None:
    async def _go() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(sql, *args)
        finally:
            await conn.close()

    asyncio.run(_go())


@pytest.fixture()
def a_queued_job() -> Any:
    """一条 `queued` 的设计作业，用完删干净（按外键顺序）。"""
    import json

    job_id = f"job-ds-{uuid.uuid4().hex[:8]}"

    def _erase() -> None:
        for child in ("job_steps", "job_events", "cluster_verdicts",
                      "idempotency_keys"):
            _exec(f"DELETE FROM {child} WHERE job_id = $1", job_id)
        _exec("DELETE FROM jobs WHERE job_id = $1", job_id)

    _erase()
    _exec(
        "INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
        "cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
        "VALUES ($1, 'design_generate', $2::jsonb, 'queued', 0.0, 0.0, 0.0, "
        "false, 'u-owner', $3, $3)",
        job_id, json.dumps({"kind": "user", "id": "u-owner"}), NOW)
    try:
        yield job_id
    finally:
        _erase()


@pytest.mark.compose
def test_a_finished_design_job_leaves_queued(a_queued_job: str) -> None:
    """**本卡的产品**：跑完之后 `jobs.state` 不再是 `queued`。

    这一条量的是**用户看到的那一半**——轮询 `GET /jobs/{id}` 的屏读的就是它。
    只判事件流的话，改前那一跑也全绿。
    """
    job_id = a_queued_job
    events = _Events()
    deps = DesignGenerateDeps(provider=_Provider(), events=events,
                              now=lambda: NOW, dsn=DSN)

    asyncio.run(run_design_generate(job_id, {"prompt": "一张热点卡片"}, deps))

    state = _rows("SELECT state FROM jobs WHERE job_id = $1", job_id)[0]["state"]
    assert state == "done", f"作业跑完了而 jobs.state 还是 {state!r}"


@pytest.mark.compose
def test_both_marks_agree_after_the_run(a_queued_job: str) -> None:
    """两块表**说同一句话**：事件流里有 `done`，库里也是 `done`。

    这一条是本卡的核心——它们分开时正是「转圈不停而内容已经出来了」。
    """
    job_id = a_queued_job
    events = _Events()
    deps = DesignGenerateDeps(provider=_Provider(), events=events,
                              now=lambda: NOW, dsn=DSN)

    asyncio.run(run_design_generate(job_id, {"prompt": "一张热点卡片"}, deps))

    said_done = [p for p in events.appended
                 if getattr(p, "kind", "") == "status"
                 and getattr(p, "state", "") == "done"]
    state = _rows("SELECT state FROM jobs WHERE job_id = $1", job_id)[0]["state"]

    assert said_done, "事件流里没有 done"
    assert state == "done"


@pytest.mark.compose
def test_running_it_twice_never_pushes_a_second_status_event(
    a_queued_job: str,
) -> None:
    """幂等：已经是 `done` 时再推进一次**不重复推事件**。

    重复推的话，屏上会出现两条一样的「已完成」。
    """
    job_id = a_queued_job

    async def _go() -> int:
        conn = await asyncpg.connect(DSN)
        events = _Events()
        try:
            await enter_state(conn, events, job_id, "done", NOW)
            first = len(events.appended)
            await enter_state(conn, events, job_id, "done", NOW)
            return len(events.appended) - first
        finally:
            await conn.close()

    assert asyncio.run(_go()) == 0, "同一个状态推了第二条事件"


# ───────────────────────── 三、阴性对照：把收尾那一步摘掉 → 红且点名两处对不上


@pytest.mark.compose
def test_removing_the_finish_step_makes_the_two_marks_disagree(
    a_queued_job: str,
) -> None:
    """**阴性对照**（卡面逐字）：摘掉收尾那一步 → 判据红，
    且**点名是哪两处状态对不上**。

    造法是把 `dsn` 拿掉——那正是改前的形状（deps 里没有库句柄，
    于是只写得了事件流那一半）。
    """
    job_id = a_queued_job
    events = _Events()
    crippled = DesignGenerateDeps(provider=_Provider(), events=events,
                                  now=lambda: NOW, dsn=None)

    asyncio.run(run_design_generate(job_id, {"prompt": "一张热点卡片"}, crippled))

    said_done = any(getattr(p, "kind", "") == "status"
                    and getattr(p, "state", "") == "done"
                    for p in events.appended)
    state = _rows("SELECT state FROM jobs WHERE job_id = $1", job_id)[0]["state"]

    # 摘掉之后**必然**分家：事件流说完成、库里还是排队
    assert said_done, "事件流那一半也没了——那这条对照量的就不是本卡的病"
    assert state == "queued", (
        f"摘掉收尾之后 jobs.state 居然是 {state!r}？那说明还有第二处在推它")

    # 红的话要点名是哪两处
    complaint = (f"作业 {job_id}：事件流说 done，而 jobs.state 是 {state!r}——"
                 f"「作业跑完没有」有两个答案")
    assert "事件流" in complaint and "jobs.state" in complaint


def test_no_dsn_never_pretends_it_advanced() -> None:
    """`dsn is None` 时**照实什么都不做**，NEVER 假装推过了。

    假装的话，离线判据会以为这一半被覆盖到了。
    """
    source = inspect.getsource(run_design_generate.__module__ and _finish_source())

    assert "if deps.dsn is None:" in source
    assert "NEVER 假装推过了" in source


def _finish_source() -> Any:
    from flint.jobs import design_generate

    return design_generate._finish


# ───────────────────────── 四、装配面真的把库给了它


def test_the_worker_hands_the_dsn_to_the_design_family() -> None:
    """`run_worker` MUST 把 `dsn` 注进去。

    不注的话，本卡改的那一半在真栈上**一次都走不到**——
    判据全绿而屏上照旧转圈（本批反复撞见的形状）。
    """
    from harness import run_worker

    deps = run_worker.build_deps()

    assert deps.design_generate_deps is not None
    assert deps.design_generate_deps.dsn, "设计那一族没拿到库连接"


def test_the_reason_is_written_next_to_the_seam() -> None:
    """为什么要这个 `dsn`，写在**字段旁边**，不只写在 trace 里。"""
    text = (REPO / "flint" / "jobs" / "design_generate.py").read_text(
        encoding="utf-8")

    assert "DESIGN-STATE" in text
    assert "jobs.state" in text
    assert "NEVER 在这里另写一套推进状态的代码" in text
