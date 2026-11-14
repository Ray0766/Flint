"""WIRE-07 · analysis 族三条路由接通。

## 为什么这张卡到第 4 批才做得了

`WIRE-01` 拒绝挂它，理由是缺 `role_resolver`——而库里没有 `memberships`，
「这个人对这个项目是什么角色」没有事实可查。`AUTH-01~05` 把那块地基补上了，
所以现在挂得上，并且挂上的是**真的鉴权**。

## 逐条探活，NEVER 断言 `include_router` 存在

`WIRE-01` 那次漏掉 51 条路由，靠的正是「断言语句存在」这种写法：
造得出 `create_analysis_app` ≠ 挂上了。所以这里发**真请求**：

- 打过去**不是 404**（路由在）；
- 用没有权限的身份打过去**是 403**（鉴权真的在起作用，不是摆设）。

第二条尤其要紧：只判「不是 404」的话，一个把所有请求都放行的装配也会绿。

## 队列是一条**显式的缝**

`create_app(dsn, redis_url=None)` 时，入队走 `_unconfigured("analysis")`——
路由挂着，提交打过去回 **503 + 点名是哪一族**。
**NEVER 让它默默地不入队**：那样作业永远停在 `queued`，
而「队列没配」与「worker 没起来」在 `jobs` 表上长得一模一样。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.app import UNWIRED_FAMILIES, create_app, mounted_route_table

pytestmark = pytest.mark.compose

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "wire07-"
ANALYSIS_PATHS = (
    "/projects/{project_id}/analysis", "/jobs/{job_id}", "/jobs/{job_id}/events")
NOW = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def seeded() -> Any:
    """一个项目（org 归属）、一个有角色的人、一个没角色的人、一条别人发起的作业。"""
    wipe = [
        f"DELETE FROM jobs WHERE job_id LIKE '{PREFIX}%'",
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
        f"DELETE FROM projects WHERE project_id LIKE '{PREFIX}%'",
    ]
    run(_sql(wipe))
    scope = json.dumps({"kind": "org", "id": f"{PREFIX}org"})
    run(_sql([
        (f"INSERT INTO orgs (org_id, name, created_at) "
         f"VALUES ('{PREFIX}org', 'WIRE-07 组织', now())"),
        (f"INSERT INTO users (user_id, email, display_name, created_at) VALUES "
         f"('{PREFIX}member', 'm@wire07.invalid', 'M', now()), "
         f"('{PREFIX}outsider', 'o@wire07.invalid', 'O', now())"),
        (f"INSERT INTO memberships (user_id, org_id, role) "
         f"VALUES ('{PREFIX}member', '{PREFIX}org', 'member')"),
        (f"INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
         f"chosen_topic_id, deliverable_ids, change_log, status, created_at) "
         f"VALUES ('{PREFIX}p', '{scope}'::jsonb, 'o', '[]'::jsonb, NULL, "
         f"'[]'::jsonb, '[]'::jsonb, 'active', now())"),
        (f"INSERT INTO jobs (job_id, kind, owner_scope, state, progress, budget, "
         f"cost_accum, cancel_requested, initiated_by, created_at, updated_at) "
         f"VALUES ('{PREFIX}job', 'gate1_analysis', '{scope}'::jsonb, 'done', 1, "
         f"1, 0, false, '{PREFIX}member', now(), now())"),
    ]))
    yield
    run(_sql(wipe))


@pytest.fixture
def client() -> Any:
    with TestClient(create_app(DSN)) as test_client:
        yield test_client


def _get(client: TestClient, path: str, user: str) -> Any:
    return client.get(path, headers={"X-User-Id": user})


def _probe_sse(client: TestClient, user: str) -> int:
    """探 SSE 那条路由。**夹具里那条作业是终态（`done`）——所以流会自己结束。**

    三件实测撞出来的事，按顺序：

    1. 第一版拿一条 `queued` 的作业去探：流不会结束，整个用例挂住不返回；
    2. 改成「只探被拒的那一路」：变异考里「用假手放行所有人」那一条把它挂了 600 秒——
       判据在那条变异下不是变红，是**吊死**。**会吊死的判据比红的更坏**：
       CI 上看不出是断言不过还是环境卡住；
    3. 给 `timeout=` 也没用：`TestClient` 的传输在 portal 线程里跑应用，
       读超时管不到它。

    真正的解法是让**流本身有终点**：`analysis.py` 在作业进入 `_TERMINAL`
    （done / failed / cancelled）后收尾。夹具把作业种成 `done`，
    于是无论放行还是拒绝，这次探活都会返回。
    """
    return client.get(
        f"/jobs/{PREFIX}job/events", headers={"X-User-Id": user}).status_code


# ───────────────────────── acceptance①④：三条挂上，登记里删掉


def test_the_three_paths_are_mounted() -> None:
    """三条路由在装配后的路由表里。"""
    mounted = {r.path for r in mounted_route_table(
        create_app("postgresql://x@127.0.0.1:1/y"))}

    for path in ANALYSIS_PATHS:
        assert path in mounted, path


def test_analysis_is_gone_from_the_unwired_register() -> None:
    """`UNWIRED_FAMILIES` 里没有 analysis 了——**登记与实况 MUST 一致**。

    留着的话，对账器会把三条已挂的路由继续算成「没挂」，
    而出口判据永远归不了零。
    """
    modules = {family.module for family in UNWIRED_FAMILIES}

    assert "analysis.py" not in modules
    # `WIRE-08` 之后 compose 也走了——**这个集合每接通一族就要改一次**。
    # `WIRE-09` 之后 interventions 也走了——只剩 combo。
    assert modules == set(), modules   # WIRE-10 之后四族全接通


# ───────────────────────── acceptance②：逐条探活


def test_every_path_answers_something_other_than_404(client: TestClient) -> None:
    """三条路由**打得通**——不是 404。

    这是「挂上了」的最低证据：`WIRE-01` 那次漏 51 条，全部表现为 404。
    """
    codes = [
        client.post(f"/projects/{PREFIX}p/analysis",
                    json={"keywords": ["x"], "locale": "en", "budget_cny": 1.0},
                    headers={"X-User-Id": f"{PREFIX}member"}).status_code,
        _get(client, f"/jobs/{PREFIX}job", f"{PREFIX}member").status_code,
        # SSE 用**被拒**那一路探（见 `_probe_sse_rejection` 的说明）。
        _probe_sse(client, f"{PREFIX}outsider"),
    ]

    for path, code in zip(ANALYSIS_PATHS, codes, strict=True):
        assert code != 404, f"{path} 还是 404（code={code}）"


def test_a_user_without_a_role_is_refused_with_403(client: TestClient) -> None:
    """**没有权限的身份打过去是 403**——鉴权真的在起作用。

    只判「不是 404」的话，一个把所有请求都放行的装配也会绿。
    这一条是 `AUTH-02` 那只真手在装配后的应用上第一次被用到。
    """
    got = _get(client, f"/jobs/{PREFIX}job", f"{PREFIX}outsider")
    assert got.status_code == 403, f"读作业放行了没权限的人：{got.status_code}"
    assert got.json()["code"] == "PERMISSION_DENIED"

    assert _probe_sse(client, f"{PREFIX}outsider") == 403, "SSE 把没权限的人放进了流里"


def test_the_member_can_subscribe_to_the_stream(client: TestClient) -> None:
    """**正例**：有角色的人订得上 SSE（终态作业 → 流发完就收）。

    没有它，上面那条 403 可能是「这条流对谁都拒」换来的。
    """
    assert _probe_sse(client, f"{PREFIX}member") == 200


def test_the_member_can_read_the_job(client: TestClient) -> None:
    """**正例**：有角色的人读得到。

    没有它，上面那些 403 可能是「这条路对谁都拒」换来的。
    """
    got = _get(client, f"/jobs/{PREFIX}job", f"{PREFIX}member")

    assert got.status_code == 200, got.text
    assert got.json()["job_id"] == f"{PREFIX}job"


def test_an_unknown_job_is_404_not_403(client: TestClient) -> None:
    """作业不存在 → 404；存在但无权 → 403。两者 NEVER 混。"""
    got = _get(client, f"/jobs/{PREFIX}nope", f"{PREFIX}member")

    assert got.status_code == 404
    assert got.json()["code"] == "NOT_FOUND"


# ───────────────────────── 队列那条缝


def test_submitting_without_a_queue_says_which_family_is_unconfigured(
    client: TestClient,
) -> None:
    """`redis_url` 没给 → 提交回 **503 且点名 analysis**，NEVER 默默不入队。

    默默不入队的话，作业会永远停在 `queued`——
    而「队列没配」与「worker 没起来」在 `jobs` 表上长得一模一样。
    """
    got = client.post(
        f"/projects/{PREFIX}p/analysis",
        json={"keywords": ["x"], "locale": "en", "budget_cny": 1.0},
        headers={"X-User-Id": f"{PREFIX}member"})

    assert got.status_code == 503, got.text
    body = got.json()
    assert body["code"] == "FAMILY_NOT_CONFIGURED"
    assert body["family"] == "analysis"


def test_a_redis_url_turns_the_seam_into_a_real_queue_hook() -> None:
    """给了 `redis_url` 就换成真入队钩子——**这条缝两侧都要有实例**。

    只验「没给时 503」的话，那条缝可能永远是 503。
    """
    from flint.api.app import _queue_hook

    assert _queue_hook(None).__name__ != "enqueue"
    assert _queue_hook("redis://localhost:56379/0").__name__ == "enqueue"


# ───────────────────────── acceptance③：建应用仍不连库


def test_building_the_app_still_touches_no_database() -> None:
    """`WIRE-01` acceptance④ 不倒：建应用期间一次库都不连。

    真手是**懒的**——`build_role_resolver(dsn)` 只把 dsn 包进闭包，
    第一次查询发生在请求里。这一条把它钉住：哪天有人在装配期先查一次
    「这个人是谁」，库不可达时整个应用就起不来了。
    """
    from unittest.mock import patch

    def _boom(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("create_app() 期间连了库")

    with patch("asyncpg.connect", new=_boom):
        app = create_app("postgresql://x@127.0.0.1:1/y")

    assert len(app.router.routes) > 40
