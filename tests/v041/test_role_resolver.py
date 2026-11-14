"""AUTH-02 · 真 `role_resolver` 与 `owner_scope_for_project`——替掉那只假手。

## 那只假手是什么

`harness/demo_server.py` 里三处 `lambda _u, _o: "owner"`：**谁问都答 owner**。
在 demo 里它是明知故犯的口径；一旦进了可部署应用，它等于
**每一条写操作对任何调用者开放**——`WIRE-01` 因此拒绝挂那四族，
`SHIP-03` 因此没能收口。

本卡兑现 `flint/jobs/runner.py` 文件头第 9 行那句话：

> 角色解析经注入 `RoleResolver`（**memberships 表随身份任务落库后接 SQL 实现**）

## 判据分两层

**一层判行为**：查得到就返回那个角色，查不到返回 `None`——
**NEVER 返回一个兜底角色**。兜底的那一刻，「没有授权」与「有 viewer 权」就分不开了。

**一层判源码**：`flint/authz/` 里不许出现任何形如 `lambda _u, _o: "owner"` 的常量解析。
只判行为是不够的——今天的实现查库，明天有人为了让某个测试过而加一句
「查不到就当 owner」，行为判据里那条 `None` 用例确实会红，
但**如果那句兜底只在某个分支上**（比如「org 不存在时」），行为判据未必覆盖得到。
源码那一层挡的是这种。

## 越权矩阵留给 AUTH-04

本卡只证「解析器说的是真话」。四种角色 × 三类操作的逐格断言是 `AUTH-04`，
那张卡还有一条更值钱的阴性对照：**把解析器换回常量 owner 版本，
矩阵里的拒绝格 MUST 全部变红**。
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

# 与 `flint/authz` 用同一份 `Principal`（`flint.domain.models`）——
# 两份同名同形的定义混用时，`==` 会因为类型不同而不相等（WIRE-07 撞到过）。
from contracts.models import Job
from flint.api.analysis import may_view
from flint.api.interventions import may_intervene
from flint.authz import (
    ProjectNotFound,
    build_owner_scope_for_project,
    build_role_resolver,
)
from flint.domain.models import Principal

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
AUTHZ = REPO / "flint" / "authz"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "auth02-"
ROLES = frozenset({"owner", "admin", "member", "viewer"})


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


def _wipe() -> None:
    run(_sql([
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
        f"DELETE FROM projects WHERE project_id LIKE '{PREFIX}%'",
    ]))


@pytest.fixture(autouse=True)
def seeded() -> Any:
    """一个组织、四个人（四种角色各一）、一个没有任何 membership 的人。"""
    _wipe()
    owner = json.dumps({"kind": "org", "id": f"{PREFIX}org"})
    personal = json.dumps({"kind": "user", "id": f"{PREFIX}owner"})
    stmts = [
        (f"INSERT INTO orgs (org_id, name, created_at) "
         f"VALUES ('{PREFIX}org', 'AUTH-02 组织', now())"),
        (f"INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
         f"chosen_topic_id, deliverable_ids, change_log, status, created_at) "
         f"VALUES ('{PREFIX}p-org', '{owner}'::jsonb, 'o', '[]'::jsonb, NULL, "
         f"'[]'::jsonb, '[]'::jsonb, 'active', now())"),
        (f"INSERT INTO projects (project_id, owner, origin_id, topic_ids, "
         f"chosen_topic_id, deliverable_ids, change_log, status, created_at) "
         f"VALUES ('{PREFIX}p-user', '{personal}'::jsonb, 'o', '[]'::jsonb, NULL, "
         f"'[]'::jsonb, '[]'::jsonb, 'active', now())"),
    ]
    for role in ("owner", "admin", "member", "viewer"):
        stmts += [
            (f"INSERT INTO users (user_id, email, display_name, created_at) "
             f"VALUES ('{PREFIX}{role}', '{role}@auth02.invalid', "
             f"'{role}', now())"),
            (f"INSERT INTO memberships (user_id, org_id, role) "
             f"VALUES ('{PREFIX}{role}', '{PREFIX}org', '{role}')"),
        ]
    stmts.append(
        f"INSERT INTO users (user_id, email, display_name, created_at) "
        f"VALUES ('{PREFIX}stranger', 's@auth02.invalid', 'S', now())")
    run(_sql(stmts))
    yield
    _wipe()


def _job(scope: Principal, initiated_by: str) -> Job:
    stamp = datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC)
    return Job(
        job_id=f"{PREFIX}job", kind="gate1_analysis", project_id=None,
        owner_scope=scope, state="queued", steps=[], progress=0.0,
        partial_output_ref=None, budget=1.0, cost_accum=0.0,
        cancel_requested=False, error=None, initiated_by=initiated_by,
        created_at=stamp, updated_at=stamp)


# ───────────────────────── acceptance①：查得到就答，查不到就 None


def test_each_seeded_role_comes_back_verbatim() -> None:
    """四种角色各查一次，答的就是库里那一行。"""
    resolve = build_role_resolver(DSN)

    for role in ("owner", "admin", "member", "viewer"):
        assert resolve(f"{PREFIX}{role}", f"{PREFIX}org") == role


def test_a_user_with_no_membership_row_resolves_to_none() -> None:
    """**没有那一行就是 `None`**，NEVER 兜底成某个角色。

    兜底的那一刻，「没有授权」与「有 viewer 权」就分不开了——
    而这两件事对调用方的意义完全相反。
    """
    resolve = build_role_resolver(DSN)

    assert resolve(f"{PREFIX}stranger", f"{PREFIX}org") is None
    assert resolve(f"{PREFIX}owner", f"{PREFIX}no-such-org") is None
    assert resolve("who-is-this", "which-org") is None


# ───────────────────────── acceptance②：项目归属查 projects.owner


def test_owner_scope_reads_the_principal_stored_on_the_project() -> None:
    """`projects.owner` 那一列（JSONB，存的就是 `Principal`）查一次即可。

    NEVER 另建一张「项目归属」表：同一个事实两处存，迟早各说各的。
    """
    owner_of = build_owner_scope_for_project(DSN)

    assert owner_of(f"{PREFIX}p-org") == Principal(kind="org", id=f"{PREFIX}org")
    assert owner_of(f"{PREFIX}p-user") == Principal(
        kind="user", id=f"{PREFIX}owner")


def test_an_unknown_project_raises_instead_of_guessing() -> None:
    """项目不存在 → 抛错（端点转 404），**NEVER 编一个归属出来**。

    编出来的那个归属会让下一步的鉴权在一个不存在的项目上「通过」。
    """
    owner_of = build_owner_scope_for_project(DSN)

    with pytest.raises(ProjectNotFound):
        owner_of(f"{PREFIX}p-nope")


# ───────────────────────── acceptance③：源码里没有常量解析


def test_no_constant_role_lives_anywhere_in_the_authz_package() -> None:
    """`flint/authz/` 里不许有任何形如 `lambda _u, _o: "owner"` 的常量解析。

    只判行为不够：有人加一句「查不到就当 owner」时，
    如果那句兜底只在某个分支上（比如「org 不存在时」），
    行为判据未必覆盖得到。**源码这一层挡的是这种。**

    **判语法树，NEVER 判正文。** 第一版按行扫字符串，当场把模块 docstring 里
    那句「它替掉的是 `lambda _u, _o: "owner"`」判成了违规——
    **说明问题的那句话被当成了犯下问题**。这与 `GAUGE-10` 那张卡是同一个病：
    扫描器不剥注释，于是「写清楚一点」反而被判红。
    `ast` 走的是真节点：docstring 是 `Expr`，不是 `Return`，也不是 `Lambda`。
    """
    offenders: list[str] = []
    for path in sorted(AUTHZ.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            body: ast.expr | None = None
            if isinstance(node, ast.Lambda):
                body = node.body
            elif isinstance(node, ast.Return):
                body = node.value
            if isinstance(body, ast.Constant) and body.value in ROLES:
                offenders.append(f"{path.name}:{node.lineno}")

    assert offenders == [], f"这些行把角色写成了常量：{offenders}"


def test_the_role_it_returns_really_came_from_the_row() -> None:
    """**行为侧的同一件事**：改库里那一行，解析器跟着变。

    源码扫描证明「没有写死」，这一条证明「读的就是那一行」——
    两条合起来才排除「从别处拿了一个常量」。
    """
    resolve = build_role_resolver(DSN)
    assert resolve(f"{PREFIX}member", f"{PREFIX}org") == "member"

    run(_sql([(
        f"UPDATE memberships SET role = 'admin' "
        f"WHERE user_id = '{PREFIX}member' AND org_id = '{PREFIX}org'"
    )]))

    assert resolve(f"{PREFIX}member", f"{PREFIX}org") == "admin"


# ───────────────────────── acceptance④：三条阴性对照


def test_a_viewer_is_refused_a_write_operation() -> None:
    """`viewer` 在**写**操作上被拒（`may_intervene` 的既有语义）。"""
    resolve = build_role_resolver(DSN)
    scope = Principal(kind="org", id=f"{PREFIX}org")

    assert may_intervene(scope, f"{PREFIX}owner", resolve) is True
    assert may_intervene(scope, f"{PREFIX}admin", resolve) is True
    assert may_intervene(scope, f"{PREFIX}viewer", resolve) is False
    assert may_intervene(scope, f"{PREFIX}stranger", resolve) is False


def test_a_personal_scope_only_lets_that_person_through() -> None:
    """`owner_scope.kind == "user"` 时**只有本人**通过（`may_view` 的既有语义）。

    个人使用无需先建 Org（冻结件 `Principal` 原话），所以这条路上
    **一次 membership 都不查**——解析器在这里根本不该被问到。
    """
    resolve = build_role_resolver(DSN)
    mine = _job(Principal(kind="user", id=f"{PREFIX}owner"), f"{PREFIX}owner")

    assert may_view(mine, f"{PREFIX}owner", resolve) is True
    assert may_view(mine, f"{PREFIX}stranger", resolve) is False


def test_an_org_scope_lets_a_member_view_but_not_a_stranger() -> None:
    """org 归属下，有角色的能看、没角色的看不到。"""
    resolve = build_role_resolver(DSN)
    job = _job(Principal(kind="org", id=f"{PREFIX}org"), f"{PREFIX}owner")

    assert may_view(job, f"{PREFIX}member", resolve) is True
    assert may_view(job, f"{PREFIX}stranger", resolve) is False
