"""AUTH-03：身份入口——**一处**受信头，**三种**拒绝各说各的。

## 一处入口

身份来源是 `X-User-Id` 受信头（`BE-05` 已按此实现，工单 §8-④ 延续这条口径）。
全仓只此一个入口：多一个入口就多一条绕过它的路，而绕过去的那条路上没有这三道判断。

**受信头的前提**：它前面 MUST 有一层网关来签发与校验。那属部署面，不在本仓——
但**这句话必须写在这里**，否则「受信」二字会被读成「不用校验」。

## 三种拒绝，NEVER 混成一个响应

| 情况 | 状态 | code | 要人做的事 |
|---|---|---|---|
| 请求里没有那个头 | 401 | `IDENTITY_MISSING` | **加上头**（多半是调用方漏了） |
| 头里的 user_id 在 `users` 表查不到 | 401 | `IDENTITY_UNKNOWN` | **换一个身份**（这个 id 不是任何人） |
| 查得到，但对这个资源没有角色 | 403 | `PERMISSION_DENIED` | **去要权限**（你是谁没问题，你不能干这件事） |

混成一句话的代价：前两种是「你是谁」的问题，第三种是「你能干什么」的问题。
读到一句通用的「无权访问」时，调用方**分不出该改请求还是该找人开权限**。

两个 401 也分开：一个是调用方自己漏了头，一个是这个身份不存在——
前者是 bug，后者是数据。**同一个状态码下，code 是唯一能区分它们的位。**

## 404 与 403 的边界

资源不存在 → 404；资源存在但无权 → 403。**NEVER 用 404 去盖 403**：
那样调用方永远不知道自己是「找不到」还是「不该看」，而这两件事的下一步不同。
（`deref` 那一族是**有意**的例外：那里查不到与不该看到共用 404，
因为状态码本身会泄露存在性——那条口径写在 `flint/api/deref.py` 的 `_not_found()` 上，
本模块 NEVER 把它推翻。）
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import JSON

IDENTITY_HEADER = "X-User-Id"

__all__ = [
    "IDENTITY_HEADER",
    "IdentityMissing",
    "IdentityUnknown",
    "RoleMissing",
    "build_user_check",
    "install_identity_handlers",
]


class IdentityMissing(RuntimeError):
    """请求里没有 `X-User-Id`。→ 401 `IDENTITY_MISSING`。"""


class IdentityUnknown(RuntimeError):
    """头里那个 user_id 不是任何人。→ 401 `IDENTITY_UNKNOWN`。"""

    def __init__(self, user_id: str) -> None:
        super().__init__(user_id)
        self.user_id = user_id


class RoleMissing(RuntimeError):
    """身份没问题，但对这个资源没有角色。→ 403 `PERMISSION_DENIED`。"""

    def __init__(self, user_id: str, scope_id: str) -> None:
        super().__init__(f"{user_id} @ {scope_id}")
        self.user_id = user_id
        self.scope_id = scope_id


async def _user_exists(dsn: str, user_id: str) -> bool:
    conn = await asyncpg.connect(dsn)
    try:
        found: bool = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM users WHERE user_id = $1)", user_id)
    finally:
        await conn.close()
    return found


def build_user_check(dsn: str) -> Callable[[str | None], Awaitable[str]]:
    """`X-User-Id 的值 -> user_id`。缺头抛 `IdentityMissing`，查不到抛 `IdentityUnknown`。

    **是 async**：这一检查跑在端点里，端点本来就是异步的——
    `flint/authz` 那座同步桥只为**冻结的同步 `RoleResolver` 签名**存在，
    这里没有那个约束，NEVER 顺手借它（借了就是白占一次线程）。

    **NEVER 返回一个默认身份**：一个「查不到就当 demo-user」的兜底，
    会让所有匿名请求以同一个人的名义写数据。
    """
    async def check(header_value: str | None) -> str:
        if header_value is None or not header_value.strip():
            raise IdentityMissing(IDENTITY_HEADER)
        user_id = header_value.strip()
        if not await _user_exists(dsn, user_id):
            raise IdentityUnknown(user_id)
        return user_id

    return check


def _body(
    code: ErrorCode, message: str, detail: JSON | None = None,
) -> dict[str, object]:
    return ErrorBody(code=code, message=message, detail=detail).model_dump(
        exclude_none=True)


def install_identity_handlers(app: FastAPI) -> None:
    """把三种拒绝翻成三种响应。**形状与既有 `ErrorBody` 一致**（code · message）。"""
    @app.exception_handler(IdentityMissing)
    async def _missing(_request: Request, _exc: IdentityMissing) -> JSONResponse:
        return JSONResponse(status_code=401, content=_body(
            "IDENTITY_MISSING",
            f"请求里没有 {IDENTITY_HEADER}——这一条不是权限问题，是调用方漏了身份头。"))

    @app.exception_handler(IdentityUnknown)
    async def _unknown(_request: Request, exc: IdentityUnknown) -> JSONResponse:
        return JSONResponse(status_code=401, content=_body(
            "IDENTITY_UNKNOWN",
            "这个身份不存在——它不是任何一个已登记的用户。",
            {"user_id": exc.user_id}))

    @app.exception_handler(RoleMissing)
    async def _role(_request: Request, exc: RoleMissing) -> JSONResponse:
        return JSONResponse(status_code=403, content=_body(
            "PERMISSION_DENIED",
            "你是谁没有问题，但你对这个资源没有角色。",
            {"user_id": exc.user_id, "scope_id": exc.scope_id}))
