"""REPORT-SRC-01 · 成文端点收分析作业号，服务端换算（`DEC-061`）。

## 断的是哪一段

`POST /projects/{id}/report` 要 `analysis_id`——它是一批 claim 的 `deliverable_id`，
形状是 `"analysis-" + 分析作业号`（`flint/jobs/gate1.py#analysis_product_id`）。
发起分析回给前端的只有作业号，于是屏上没有一条路能凑出这一格
（`docs/blocked/ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md`）。

## 本卡的口径（owner 选甲）

端点多收一格 `analysis_job_id`，**服务端**调 `analysis_product_id()` 换算——
规则只活在那一处，前端只传它本来就有的作业号。

既有的 `analysis_id` **保留**：夹具那条路（`tests/v041/test_compose_e2e.py`）
拿一份既有交付物当来源，它没有分析作业可给。两格**二选一**：
都不给 / 都给 → 422。都给时 NEVER 「挑一个用」——那等于替调用方猜它想要哪一份来源。

## 换算之前先核作业（不核的代价）

填错一个作业号，`freeze_ledger` 查到 0 条 claim——**不报错**，出一份全是
`gap_notice` 的报告，看起来像模型不给力。所以换算前逐条核：
作业在、属于这个项目、是一次分析、跑完了。任何一条不成立都当场拒，并说清是哪一条。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from uuid import uuid4

import asyncpg
import httpx
import pytest

from flint.api.compose import ComposeApiDeps, create_compose_app
from flint.domain.models import Principal
from flint.jobs.gate1 import analysis_product_id
from flint.jobs.runner import PgJobRunner

pytestmark = pytest.mark.compose

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "rsrc01-"
PROJECT = f"{PREFIX}p"
OTHER_PROJECT = f"{PREFIX}p-other"
USER = f"{PREFIX}u"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def _job_row(job_id: str, kind: str, project_id: str, state: str) -> str:
    scope = json.dumps({"kind": "user", "id": USER})
    return (
        "INSERT INTO jobs (job_id, kind, project_id, owner_scope, state, progress, "
        "partial_output_ref, budget, cost_accum, cancel_requested, error, "
        "initiated_by, created_at, updated_at) VALUES "
        f"('{job_id}', '{kind}', '{project_id}', '{scope}'::jsonb, '{state}', 0, "
        f"NULL, 0, 0, false, NULL, '{USER}', now(), now())"
    )


DONE_ANALYSIS = f"{PREFIX}job-done"
QUEUED_ANALYSIS = f"{PREFIX}job-queued"
FAILED_ANALYSIS = f"{PREFIX}job-failed"
OTHER_PROJECT_ANALYSIS = f"{PREFIX}job-elsewhere"
A_REPORT_JOB = f"{PREFIX}job-report"


@pytest.fixture(autouse=True)
def seeded() -> Any:
    wipe = [
        "DELETE FROM idempotency_keys",
        f"DELETE FROM jobs WHERE job_id LIKE '{PREFIX}%'",
    ]
    run(_sql(wipe))
    run(_sql([
        _job_row(DONE_ANALYSIS, "gate1_analysis", PROJECT, "done"),
        _job_row(QUEUED_ANALYSIS, "gate1_analysis", PROJECT, "queued"),
        _job_row(FAILED_ANALYSIS, "gate1_analysis", PROJECT, "failed"),
        _job_row(OTHER_PROJECT_ANALYSIS, "gate1_analysis", OTHER_PROJECT, "done"),
        _job_row(A_REPORT_JOB, "report", PROJECT, "done"),
    ]))
    yield
    run(_sql(wipe))


class _Captured:
    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def __call__(self, job_id: str, kind: str, payload: dict[str, Any]) -> None:
        self.payloads.append({"job_id": job_id, "kind": kind, **payload})


def _app(captured: _Captured) -> Any:
    deps = ComposeApiDeps(
        dsn=DSN,
        runner=PgJobRunner(
            dsn=DSN, role_resolver=lambda _user, _org: None,
            id_factory=lambda: f"{PREFIX}new-{uuid4().hex[:10]}",
            enqueue=captured,
        ),
        owner_scope_for_project=lambda _pid: Principal(kind="user", id=USER),
        role_resolver=lambda _user, _org: None,
    )
    return create_compose_app(deps)


def _post(body: dict[str, Any], project: str = PROJECT) -> tuple[httpx.Response, _Captured]:
    captured = _Captured()

    async def go() -> httpx.Response:
        transport = httpx.ASGITransport(app=_app(captured))
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            return await client.post(
                f"/projects/{project}/report", json=body,
                headers={"X-User-Id": USER})

    return run(go()), captured


# ───────────────────────── 正路：作业号进、换算好的来源 id 出


def test_a_finished_analysis_job_becomes_its_product_id_on_the_queue() -> None:
    got, captured = _post({"analysis_job_id": DONE_ANALYSIS})

    assert got.status_code == 200, got.text
    assert len(captured.payloads) == 1
    sent = captured.payloads[0]
    assert sent["kind"] == "report"
    # 两种写法各断一次：换算走的是**那一个函数**，且那个函数今天给的就是这个前缀。
    # 只断函数的话，函数改了这条照旧绿；只断字面量的话，端点自己拼一份也能绿。
    assert sent["analysis_id"] == analysis_product_id(DONE_ANALYSIS)
    assert sent["analysis_id"] == f"analysis-{DONE_ANALYSIS}"
    assert got.json()["job_id"] == sent["job_id"]


def test_the_fixture_path_still_passes_a_source_id_through_untouched() -> None:
    """既有 `analysis_id` 那一格原样透传——夹具那条路没有分析作业可给。"""
    got, captured = _post({"analysis_id": "del-demo-fixture-report"})

    assert got.status_code == 200, got.text
    assert captured.payloads[0]["analysis_id"] == "del-demo-fixture-report"


# ───────────────────────── 二选一


@pytest.mark.parametrize("body", [
    {},
    {"template_id": "generic"},
    {"analysis_id": "del-x", "analysis_job_id": DONE_ANALYSIS},
])
def test_exactly_one_source_field_or_422(body: dict[str, Any]) -> None:
    got, captured = _post(body)

    assert got.status_code == 422, got.text
    assert got.json()["code"] == "VALIDATION_FAILED"
    assert captured.payloads == [], "拒绝之前 NEVER 入队"


# ───────────────────────── 换算之前逐条核作业


@pytest.mark.parametrize("job_id", [f"{PREFIX}job-nope", OTHER_PROJECT_ANALYSIS])
def test_an_unknown_job_and_another_projects_job_look_the_same(job_id: str) -> None:
    """别的项目的作业与不存在的作业**对外长得一样**（404，同一个码）——
    差一个字就能被用来枚举别人的作业号（与 `project_overview` 同一条口径）。"""
    got, captured = _post({"analysis_job_id": job_id})

    assert got.status_code == 404, got.text
    assert got.json()["code"] == "NOT_FOUND"
    assert captured.payloads == []


def test_a_job_that_is_not_an_analysis_is_refused_and_named() -> None:
    got, captured = _post({"analysis_job_id": A_REPORT_JOB})

    assert got.status_code == 422, got.text
    assert got.json()["code"] == "VALIDATION_FAILED"
    assert "report" in got.json()["message"], "要说清它是什么作业"
    assert captured.payloads == []


@pytest.mark.parametrize(("job_id", "state"), [
    (QUEUED_ANALYSIS, "queued"), (FAILED_ANALYSIS, "failed"),
])
def test_an_analysis_that_has_not_finished_is_refused_and_says_its_state(
    job_id: str, state: str,
) -> None:
    """没跑完的分析底下没有 claim——拿它成文就是那份「全是缺口」的报告。"""
    got, captured = _post({"analysis_job_id": job_id})

    assert got.status_code == 422, got.text
    assert got.json()["code"] == "VALIDATION_FAILED"
    assert state in got.json()["message"]
    assert captured.payloads == []
