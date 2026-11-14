"""AUTH-03 · 身份入口：未知用户 NEVER 静默当成 owner。

## 三种拒绝要是三种响应

| 情况 | 状态 | code | 要人做的事 |
|---|---|---|---|
| 没有 `X-User-Id` | 401 | `IDENTITY_MISSING` | 加上头（调用方漏了） |
| 头里的 id 不是任何人 | 401 | `IDENTITY_UNKNOWN` | 换一个身份 |
| 是某个人，但对这资源没角色 | 403 | `PERMISSION_DENIED` | 去要权限 |

混成一句「无权访问」的代价：**调用方分不出该改请求还是该找人开权限**。
两个 401 也要分开——一个是 bug，一个是数据。

## 为什么这里自己搭一个小应用

`flint/api/identity.py` 是**库**：它给出检查、三个异常与三个处理器。
把它接进四族路由是 `WIRE-07~10` 的事（那四族此刻还没挂）。
所以这份判据用**真的模块**搭一个最小应用来验行为——
NEVER 等到四族挂上才有人验这三种拒绝分不分得开。
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient

from flint.api.identity import (
    IDENTITY_HEADER,
    RoleMissing,
    build_user_check,
    install_identity_handlers,
)
from flint.api.schemas import ERROR_CODES
from flint.authz import build_role_resolver

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
API = REPO / "flint" / "api"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "auth03-"
# 身份只从这一个头来。别的头名出现在 `flint/api/` 里 = 多了一条绕过这三道判断的路。
OTHER_IDENTITY_HEADERS = ("Authorization", "X-User", "X-Actor", "X-Caller")


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
    """一个组织、一个有角色的人、一个没角色的人。"""
    run(_sql([
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
    ]))
    run(_sql([
        (f"INSERT INTO orgs (org_id, name, created_at) "
         f"VALUES ('{PREFIX}org', 'AUTH-03 组织', now())"),
        (f"INSERT INTO users (user_id, email, display_name, created_at) VALUES "
         f"('{PREFIX}member', 'm@auth03.invalid', 'M', now()), "
         f"('{PREFIX}outsider', 'o@auth03.invalid', 'O', now())"),
        (f"INSERT INTO memberships (user_id, org_id, role) "
         f"VALUES ('{PREFIX}member', '{PREFIX}org', 'member')"),
    ]))
    yield
    run(_sql([
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
    ]))


@pytest.fixture
def client() -> Any:
    """用**真的模块**搭一个最小应用：一条受保护的读，一条不存在的资源。"""
    app = FastAPI()
    install_identity_handlers(app)
    check = build_user_check(DSN)
    roles = build_role_resolver(DSN)
    known = {f"{PREFIX}res": f"{PREFIX}org"}

    @app.get("/things/{thing_id}")
    async def read_thing(
        thing_id: str, x_user_id: str | None = Header(default=None),
    ) -> dict[str, str]:
        user_id = await check(x_user_id)          # 401 的两种在这里抛
        scope = known.get(thing_id)
        if scope is None:
            # 资源不存在 → 404，**在鉴权之后**：先证明你是谁，再告诉你有没有这东西。
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="no such thing")
        if roles(user_id, scope) is None:
            raise RoleMissing(user_id, scope)     # 403 在这里抛
        return {"thing_id": thing_id, "seen_by": user_id}

    with TestClient(app) as test_client:
        yield test_client


def _get(client: TestClient, path: str, user: str | None) -> Any:
    headers = {} if user is None else {IDENTITY_HEADER: user}
    return client.get(path, headers=headers)


# ───────────────────────── acceptance②：三种拒绝各说各的


def test_the_three_refusals_are_three_different_responses(client: TestClient) -> None:
    """三种情况 → 三个互不相同的 `(status, code)`。

    这一条判的是**互不相同**，不是各自的值：值在下面三条各自钉。
    并成两种的那天（比如两个 401 用同一个 code），这里当场红。
    """
    missing = _get(client, f"/things/{PREFIX}res", None)
    unknown = _get(client, f"/things/{PREFIX}res", "who-is-this")
    no_role = _get(client, f"/things/{PREFIX}res", f"{PREFIX}outsider")

    seen = [
        (r.status_code, r.json()["code"]) for r in (missing, unknown, no_role)
    ]
    assert len(set(seen)) == 3, f"三种拒绝没分开：{seen}"


def test_a_missing_header_is_401_and_says_the_header_is_missing(
    client: TestClient,
) -> None:
    got = _get(client, f"/things/{PREFIX}res", None)

    assert got.status_code == 401
    assert got.json()["code"] == "IDENTITY_MISSING"
    assert IDENTITY_HEADER in got.json()["message"]


def test_an_unknown_user_is_401_not_a_silent_owner(client: TestClient) -> None:
    """**这一条是卡名那句话**：未知用户 NEVER 静默当成 owner。

    改前那只假手（`lambda _u, _o: "owner"`）对这个请求会答 owner 并放行。
    """
    got = _get(client, f"/things/{PREFIX}res", "who-is-this")

    assert got.status_code == 401
    assert got.json()["code"] == "IDENTITY_UNKNOWN"
    assert got.json()["detail"]["user_id"] == "who-is-this"


def test_a_known_user_without_a_role_is_403(client: TestClient) -> None:
    got = _get(client, f"/things/{PREFIX}res", f"{PREFIX}outsider")

    assert got.status_code == 403
    assert got.json()["code"] == "PERMISSION_DENIED"


def test_the_person_with_a_role_gets_through(client: TestClient) -> None:
    """**正例**：没有它，上面三条可能是「这个端点对谁都拒」换来的。"""
    got = _get(client, f"/things/{PREFIX}res", f"{PREFIX}member")

    assert got.status_code == 200
    assert got.json()["seen_by"] == f"{PREFIX}member"


# ───────────────────────── acceptance③：404 与 403 的边界


def test_a_missing_resource_is_404_and_a_forbidden_one_is_403(
    client: TestClient,
) -> None:
    """资源不存在 → 404；存在但无权 → 403。**NEVER 用 404 去盖 403。**

    盖住的那天，调用方永远不知道自己是「找不到」还是「不该看」——
    而这两件事的下一步完全不同。
    """
    absent = _get(client, f"/things/{PREFIX}nope", f"{PREFIX}member")
    forbidden = _get(client, f"/things/{PREFIX}res", f"{PREFIX}outsider")

    assert absent.status_code == 404
    assert forbidden.status_code == 403


def test_identity_is_checked_before_existence(client: TestClient) -> None:
    """没有身份时，连「这东西存不存在」都不回答。

    先回 404 的话，**未认证的请求就能拿来探测哪些 id 存在**。
    """
    got = _get(client, f"/things/{PREFIX}nope", None)

    assert got.status_code == 401


# ───────────────────────── acceptance①④：一处入口 · 形状一致


def test_no_second_identity_header_exists_anywhere_in_the_api() -> None:
    """`flint/api/` 里只有 `X-User-Id` 这一个身份头。

    多一个入口就多一条绕过那三道判断的路——**判语法树里的字符串常量**，
    NEVER 扫正文（说明问题的注释会被当成犯下问题，`AUTH-02` 刚踩过）。
    """
    offenders: list[str] = []
    for path in sorted(API.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if node.value in OTHER_IDENTITY_HEADERS:
                offenders.append(f"{path.name}:{node.lineno} → {node.value}")

    assert offenders == [], f"这些地方引了第二个身份来源：{offenders}"


def test_the_two_new_codes_are_registered_in_the_frozen_literal() -> None:
    """两个新 code 进了 `ErrorCode`——前端照它分支，NEVER 靠 message 猜。"""
    assert "IDENTITY_MISSING" in ERROR_CODES
    assert "IDENTITY_UNKNOWN" in ERROR_CODES
    assert "PERMISSION_DENIED" in ERROR_CODES


def test_every_refusal_body_has_the_existing_error_shape(client: TestClient) -> None:
    """三种响应体都是既有 `ErrorBody` 的形状（`code` + `message`）。"""
    for user, status in ((None, 401), ("who-is-this", 401),
                         (f"{PREFIX}outsider", 403)):
        got = _get(client, f"/things/{PREFIX}res", user)
        body = got.json()

        assert got.status_code == status
        assert set(body) <= {"code", "message", "detail"}, body
        assert body["code"] in ERROR_CODES
        assert body["message"].strip()
        assert json.dumps(body, ensure_ascii=False)
