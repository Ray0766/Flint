"""BE-09：分享端点（暴露 `flint/share` · v2 屏 2.18 外链只读页）。

三个动作：创建分享链接 / 按 token 只读取内容 / 撤销分享。
门禁**全部转调** `flint/share/links.py`（三个状态码的分法、判断顺序、
口令 hash 比对都在那里），本模块只做出口。

## 两条路，两种身份

- **管理那条**（`POST /shares` · `GET /shares` · `DELETE /shares/{token}`）：
  要 `X-User-Id`，只看得见自己的链接。
- **外链那条**（`GET /public/shares/{token}`）：**不要身份**——
  外链就是给没账号的人看的。所以这条路上：
  NEVER 回 owner、NEVER 回未分享的兄弟资源、NEVER 接受任何写操作。

## token 由服务端生成

`secrets.token_urlsafe(32)`。客户端**递不进来**一个 token（`extra="forbid"`）：
递得进来就等于让调用方自己挑一条别人猜得到的链接。
NEVER 用 `random`——它可预测，而这是一条不需要身份就能读内容的路。

## 撤销不是删除

冻结件原话：「过期可续期，撤销不可逆」。撤销是把 `revoked` 置 True 并**留着那行**：

- 删掉的话，持链人拿到的是 404「没这条」，他会以为自己拿错了链接；
- 留着才能回 410「你没走错，它到期了」——他据此去找人续期。

## 口令走头不走查询串

查询串会进访问日志、进 Referer。口令因此走 `X-Share-Password` 头。
错误文本 NEVER 回显口令本身（`links.py` 已经把这条写死，本模块不重复比对逻辑）。

## `PERSIST-01`：处理函数从 `async def` 改成 `def`

本族的 store 换成 SQL 实现（`flint/share/pgstore.py`）之后，
store 的方法是**阻塞**调用——本仓只有 asyncpg 一个驱动，
同步接口与异步驱动之间那座桥（`flint/db/sync_bridge.py`）要阻塞调用它的线程。

FastAPI 的 `async def` 处理函数跑在**事件循环线程**上，在那里阻塞会把
**所有并发请求一起卡住**，而症状只是「服务偶尔很慢」，没有任何一条错误日志。
`def`（同步）处理函数由 FastAPI 放进**它自己的线程池**跑，阻塞只影响这一个请求。

所以这里去掉了 `async`。**处理函数体一行未动**——它们本来就没有 `await`
（改之前每一个都是「async 但从不 await」，那是 `BE-0x` 建族时的默认写法）。
"""
from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Final, Protocol

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import Principal
from flint.share.links import ShareAccessError, hash_password, resolve_share, verify_write_forbidden

# 冻结件 `ShareTarget` 的三个值。**唯一真相在 contracts_v04**，
# 这里只列在判据里比对（见 tests 的 allowed 断言）。
TARGET_KINDS: Final[tuple[str, ...]] = ("deliverable", "graph", "topic")
_TOKEN_BYTES: Final[int] = 32

ContentLoader = Callable[[str, str], Awaitable[dict[str, Any] | None]]


@dataclass
class ShareLink:
    """一条外链。字段逐字对齐冻结件 `ShareLink`（I11）。

    内存实现；SQL 实现随 E2 接入（与 `SnapshotHistoryStore` 同一房规）。
    """

    token: str
    target_kind: str
    target_id: str
    created_by: Principal
    expires_at: datetime | None
    revoked: bool
    created_at: datetime
    password_hash: str | None = None


class ShareLinkStoreLike(Protocol):
    """外链存储的**形状**。内存件与 SQL 件（`flint/share/pgstore.py`）各实现一份。

    `PERSIST-01` 加的，理由与 `FavoriteStoreLike` 同：
    这个文件 61 行自己写着「SQL 实现随 E2 接入」，
    那么 `ShareApiDeps.store` 本来就该声明成形状而不是内存件那一个类。
    """

    def put(self, link: ShareLink) -> None: ...

    def get(self, token: str) -> ShareLink | None: ...

    def for_owner(self, owner: Principal) -> list[ShareLink]: ...


@dataclass
class ShareLinkStore:
    _rows: dict[str, ShareLink] = field(default_factory=dict)

    def put(self, link: ShareLink) -> None:
        self._rows[link.token] = link

    def get(self, token: str) -> ShareLink | None:
        return self._rows.get(token)

    def for_owner(self, owner: Principal) -> list[ShareLink]:
        return [
            row for row in self._rows.values()
            if row.created_by.kind == owner.kind and row.created_by.id == owner.id
        ]


class ShareCreate(BaseModel):
    """**没有 token 字段**：token 恒由服务端生成（`extra="forbid"` 把它挡在门外）。"""

    model_config = ConfigDict(extra="forbid")

    target_kind: str
    target_id: str
    expires_at: datetime | None = None
    password: str | None = None


@dataclass
class ShareApiDeps:
    store: ShareLinkStoreLike
    load_content: ContentLoader
    now: Callable[[], datetime]


def _error(status: int, code: ErrorCode, message: str,
           detail: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message, detail=detail).model_dump(
            exclude_none=True),
    )


def _not_found(token: str) -> JSONResponse:
    # 越权与不存在**同一行**：403 会用状态码本身泄露存在性。
    # （注意与 410 的分工：410 说的是「这条曾经有效」，那不是泄露，那是持链人该知道的事。）
    del token
    return _error(404, "NOT_FOUND", "unknown share link")


def link_json(link: ShareLink) -> dict[str, Any]:
    """给**创建者**看的一条链接。`password_hash` 不回——它是校验材料，不是内容。"""
    return {
        "token": link.token,
        "target_kind": link.target_kind,
        "target_id": link.target_id,
        # 过期与撤销**分开报**：过期可续期，撤销不可逆（冻结件原话）。
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "revoked": link.revoked,
        "created_at": link.created_at.isoformat(),
    }


def create_share_app(deps: ShareApiDeps) -> FastAPI:
    app = FastAPI(title="Flint share links (BE-09)")

    def _mine(token: str, owner: Principal) -> ShareLink | None:
        row = deps.store.get(token)
        if row is None:
            return None
        if row.created_by.kind != owner.kind or row.created_by.id != owner.id:
            return None
        return row

    @app.post("/shares")
    def create(body: ShareCreate, x_user_id: str = Header()) -> Response:
        if body.target_kind not in TARGET_KINDS:
            return _error(
                422, "VALIDATION_FAILED", "target_kind 不在冻结件声明的三种之内",
                {"field": "target_kind", "allowed": sorted(TARGET_KINDS)},
            )
        link = ShareLink(
            token=secrets.token_urlsafe(_TOKEN_BYTES),
            target_kind=body.target_kind,
            target_id=body.target_id,
            created_by=Principal(kind="user", id=x_user_id),
            expires_at=body.expires_at,
            revoked=False,
            created_at=deps.now(),
            # 明文 NEVER 落库：只留 hash（`links.py` 的口径）。
            password_hash=hash_password(body.password) if body.password else None,
        )
        deps.store.put(link)
        return JSONResponse(status_code=200, content=link_json(link))

    @app.get("/shares")
    def mine(x_user_id: str = Header()) -> Response:
        owner = Principal(kind="user", id=x_user_id)
        return JSONResponse(
            status_code=200,
            content={"items": [link_json(r) for r in deps.store.for_owner(owner)]},
        )

    @app.delete("/shares/{token}")
    def revoke(token: str, x_user_id: str = Header()) -> Response:
        owner = Principal(kind="user", id=x_user_id)
        row = _mine(token, owner)
        if row is None:
            return _not_found(token)
        # 撤销 = 置位 + **留着那行**（见模块 docstring）。
        deps.store.put(replace(row, revoked=True))
        return Response(status_code=204)

    @app.api_route(
        "/public/shares/{token}",
        methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"],
    )
    async def public_read(
        token: str, request: Request,
        x_share_password: str | None = Header(default=None),
    ) -> Response:
        try:
            # 写请求先拦：身份没问题、动作不允许 → 403（不是 405）。
            verify_write_forbidden(method=request.method)
            # 这一条**必须留在 async**（下面要 `await load_content`），
            # 而 `store.get` 换成 SQL 实现之后是一次**阻塞**调用
            # （`flint/db/sync_bridge.py`：本仓只有 asyncpg，桥要阻塞调用线程）。
            # 在事件循环上直接调它会把整条循环停住，所以挪进线程池。
            # 内存件走这条路也一样正确，只是多一次线程切换。
            row = await run_in_threadpool(deps.store.get, token)
            if row is None:
                # 「这个 token 存不存在」是唯一真正该藏的东西。
                return _not_found(token)
            resolve_share(row, now=deps.now(), password=x_share_password)
        except ShareAccessError as exc:
            return _error(exc.status, "PERMISSION_DENIED", str(exc))
        content = await deps.load_content(row.target_kind, row.target_id)
        if content is None:
            return _not_found(token)
        # 外链那条路上**没有身份**：不回 created_by，也不回任何别的 target。
        return JSONResponse(
            status_code=200,
            content={"target_kind": row.target_kind, "target_id": row.target_id,
                     "content": content},
        )

    return app
