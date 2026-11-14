"""WIRE-08 · compose 族两条路由接通。

## 挂之前先发现一件事：**这两条端点一次权限都不判**

`WIRE-01` 拒绝挂这一族时给的理由是「缺 `role_resolver`」。实况比那更进一步——
`ComposeApiDeps` 里**根本没有 resolver 这个字段**，两条提交端点从头到尾
没有任何权限判断：**任何 `x_user_id` 都能给任意项目提交一份要花钱的组稿作业**。

所以本卡不是「把 deps 填上就挂」，而是先给 compose 补上那道门
（口径与 `interventions` 逐字同一道：`_INTERVENE_ROLES = {owner, admin}`，
提交组稿是**写**），再挂。

`role_resolver` 在 `ComposeApiDeps` 里是**必填**——NEVER 给 `None` 默认值：
「默认不检查」就是「默认开洞」，而这一族此前挂不上的理由正是「挂上等于人人可写」。

## 两族共用一个 runner

`analysis`（`WIRE-07`）与 `compose` 用同一个 `PgJobRunner`。
各造一个就是两条入队路径，而「作业进了哪条队列」会因此说不清。
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from flint.api.app import UNWIRED_FAMILIES, create_app, mounted_route_table

pytestmark = pytest.mark.compose

DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "wire08-"
COMPOSE_PATHS = ("/projects/{project_id}/report", "/projects/{project_id}/proposal")


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
    """一个 org 归属的项目：owner / member / 外人各一。"""
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
         f"VALUES ('{PREFIX}org', 'WIRE-08 组织', now())"),
        (f"INSERT INTO users (user_id, email, display_name, created_at) VALUES "
         f"('{PREFIX}owner', 'ow@wire08.invalid', 'OW', now()), "
         f"('{PREFIX}member', 'me@wire08.invalid', 'ME', now()), "
         f"('{PREFIX}outsider', 'ou@wire08.invalid', 'OU', now())"),
        (f"INSERT INTO memberships (user_id, org_id, role) VALUES "
         f"('{PREFIX}owner', '{PREFIX}org', 'owner'), "
         f"('{PREFIX}member', '{PREFIX}org', 'member')"),
        (f"INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
         f"chosen_topic_id, deliverable_ids, change_log, status, created_at) "
         f"VALUES ('{PREFIX}p', '{scope}'::jsonb, 'o', '[]'::jsonb, NULL, "
         f"'[]'::jsonb, '[]'::jsonb, 'active', now())"),
    ]))
    yield
    run(_sql(wipe))


@pytest.fixture
def client() -> Any:
    with TestClient(create_app(DSN)) as test_client:
        yield test_client


def _report(client: TestClient, user: str) -> Any:
    return client.post(
        f"/projects/{PREFIX}p/report",
        json={"analysis_id": f"{PREFIX}src", "template_id": "generic"},
        headers={"X-User-Id": user})


def _proposal(client: TestClient, user: str) -> Any:
    return client.post(
        f"/projects/{PREFIX}p/proposal",
        json={"audience": "human_reader", "report_id": f"{PREFIX}rep"},
        headers={"X-User-Id": user})


# ───────────────────────── acceptance①③：挂上、登记里删掉


def test_the_two_paths_are_mounted() -> None:
    mounted = {r.path for r in mounted_route_table(
        create_app("postgresql://x@127.0.0.1:1/y"))}

    for path in COMPOSE_PATHS:
        assert path in mounted, path


def test_compose_is_gone_from_the_unwired_register() -> None:
    """登记与实况 MUST 一致——**判等值**，剩下正好两族。"""
    modules = {family.module for family in UNWIRED_FAMILIES}

    assert "compose.py" not in modules
    # `WIRE-09` 之后只剩 combo。
    assert modules == set(), modules   # WIRE-10 之后四族全接通


# ───────────────────────── acceptance③：逐条探活 + 403


def test_neither_path_is_404(client: TestClient) -> None:
    """两条都打得通——不是 404。"""
    for got, path in ((_report(client, f"{PREFIX}owner"), COMPOSE_PATHS[0]),
                      (_proposal(client, f"{PREFIX}owner"), COMPOSE_PATHS[1])):
        assert got.status_code != 404, f"{path} 还是 404：{got.text[:120]}"


def test_an_outsider_is_refused_on_both_paths(client: TestClient) -> None:
    """**外人 403**：改前这两条端点一次权限都不判，谁都能提交。"""
    for got in (_report(client, f"{PREFIX}outsider"),
                _proposal(client, f"{PREFIX}outsider")):
        assert got.status_code == 403, got.text
        assert got.json()["code"] == "PERMISSION_DENIED"


def test_a_member_is_refused_because_composing_is_a_write(
    client: TestClient,
) -> None:
    """`member` 也被拒——提交组稿是**写**，走 `{owner, admin}` 那道门。

    这一条把口径钉死：与 `interventions` 同一道门，
    NEVER 让「读得到的人都能提交一份要花钱的作业」。
    """
    got = _report(client, f"{PREFIX}member")

    assert got.status_code == 403, got.text


def test_the_owner_gets_past_the_gate(client: TestClient) -> None:
    """**正例**：owner 过得了权限门。

    没有它，上面那些 403 可能是「这条路对谁都拒」换来的。
    过门之后停在 503（队列没配，`WIRE-07` 那条缝）——**那也不是 403**。
    """
    got = _report(client, f"{PREFIX}owner")

    assert got.status_code != 403, got.text
    assert got.status_code == 503, got.text
    assert got.json()["family"] == "analysis"


def test_an_unknown_project_is_404_not_403(client: TestClient) -> None:
    """项目不存在 → 404（`ProjectNotFound` 转的），NEVER 用 403 盖住。"""
    got = client.post(
        f"/projects/{PREFIX}nope/report",
        json={"analysis_id": "x", "template_id": "generic"},
        headers={"X-User-Id": f"{PREFIX}owner"})

    assert got.status_code == 404, got.text


# ───────────────────────── acceptance②：真件注入，两族共用一个 runner


def test_the_resolver_is_a_required_field_not_an_optional_one() -> None:
    """`ComposeApiDeps.role_resolver` **必填**。

    给它一个 `None` 默认值的话，任何旧调用点都会**静默地**回到「不检查」——
    而那正是这一族此前挂不上的理由。
    """
    from dataclasses import MISSING, fields

    from flint.api.compose import ComposeApiDeps

    field = next(f for f in fields(ComposeApiDeps) if f.name == "role_resolver")

    assert field.default is MISSING and field.default_factory is MISSING


def test_both_families_share_one_runner() -> None:
    """`analysis` 与 `compose` 用**同一个** runner。

    各造一个就是两条入队路径，而「作业进了哪条队列」会因此说不清。
    这里判源码里只构造了一次 `PgJobRunner`。
    """
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "flint" / "api" / "app.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    built = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "PgJobRunner"
    ]

    assert len(built) == 1, f"app.py 里造了 {len(built)} 个 runner"
