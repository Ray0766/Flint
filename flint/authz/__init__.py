"""AUTH-02：真的角色解析与项目归属——`RoleResolver` 的 SQL 实现。

`flint/jobs/runner.py` 文件头第 9 行原话：

> 角色解析经注入 `RoleResolver`（**memberships 表随身份任务落库后接 SQL 实现**）

`AUTH-01` 落了表，本模块就是那句话的兑现。它替掉的是三处
`lambda _u, _o: "owner"`——**谁问都答 owner**。在 demo 里那是明知故犯的口径；
进了可部署应用就等于每一条写操作对任何调用者开放。

## 查不到就是 `None`，NEVER 兜底

一个兜底角色会把两件相反的事揉成一件：「这个人没有授权」与「这个人有 viewer 权」。
调用方拿到 `None` 才有机会分开处理（`AUTH-03` 的 401 与 403 就靠这个分）。

## 归属查 `projects.owner`，NEVER 另建一张表

那一列（JSONB）从 `0001` 起存的就是 `Principal`。另建一张「项目归属」表 =
同一个事实两处存，迟早各说各的，而读的人分不出哪份是真的。
项目不存在时**抛错**（端点转 404）：编一个归属出来，
会让下一步的鉴权在一个不存在的项目上「通过」。

## 为什么这里有一座「同步调异步」的桥

`RoleResolver = Callable[[str, str], str | None]` 是**同步**签名，
三个调用点（`may_view` / `may_intervene` / `PgJobRunner.cancel`）都同步调它，
而它们自己跑在 FastAPI 的事件循环里。库这一侧只有 `asyncpg`（异步专用），
仓里**没有**任何同步 PG 驱动，而本批 NEVER 新增依赖。

所以：没有正在跑的循环时直接 `asyncio.run`；已经在循环里时，把这次查询交给
**一个专用的后台循环**并等它回来。代价写在这里，NEVER 藏着：
**这一等会占住调用方那条线程几毫秒**（一次主键命中的查询）。

真正的修法是把 `RoleResolver` 变成 async——那要改签名与三个调用点，
在 `AUTH-02` 的 outputs 之外，已登记在 `docs/trace/AUTH-02.md`。
"""
from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from typing import Any, TypeVar

import asyncpg

# 用 `flint.domain.models` 那一份：`flint/api/*` 全族都引它，
# 而 `contracts.models` 是同名同形的另一份定义——两份混用时 mypy 会把
# `Callable[[str], Principal]` 判成类型不符（`WIRE-07` 接线时当场撞到）。
from flint.domain.models import Principal

__all__ = [
    "ProjectNotFound",
    "build_owner_scope_for_project",
    "build_role_resolver",
]

_T = TypeVar("_T")


class ProjectNotFound(LookupError):
    """项目不存在。端点据此回 404，**NEVER 就地编一个归属**。"""


class _Bridge:
    """一条后台事件循环：给同步调用方跑异步查询用。

    懒起、守护线程、进程内单例——**NEVER 每次查询新起一条循环**
    （那会把连接与线程的开销乘上请求数）。
    """

    _lock = threading.Lock()
    _loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def submit(cls, coro: Coroutine[Any, Any, _T]) -> _T:
        with cls._lock:
            if cls._loop is None:
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=loop.run_forever, name="flint-authz", daemon=True)
                thread.start()
                cls._loop = loop
            loop = cls._loop
        future: Future[_T] = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()


def _blocking[T](coro: Coroutine[Any, Any, T]) -> T:
    """同步地拿到一个协程的结果，无论当前有没有循环在跑。"""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return _Bridge.submit(coro)


async def _fetch_role(dsn: str, user_id: str, org_id: str) -> str | None:
    conn = await asyncpg.connect(dsn)
    try:
        role: str | None = await conn.fetchval(
            "SELECT role FROM memberships WHERE user_id = $1 AND org_id = $2",
            user_id, org_id)
    finally:
        await conn.close()
    return role


async def _fetch_owner(dsn: str, project_id: str) -> Principal:
    conn = await asyncpg.connect(dsn)
    try:
        raw: str | None = await conn.fetchval(
            "SELECT owner FROM projects WHERE project_id = $1", project_id)
    finally:
        await conn.close()
    if raw is None:
        raise ProjectNotFound(project_id)
    stored = json.loads(raw)
    kind = stored["kind"]
    if kind not in ("user", "org"):
        # 库里存着一个冻结件不认识的归属类别——**NEVER 猜**，让它炸在这里，
        # 比让一次鉴权在一个说不清归属的项目上通过要好。
        raise ValueError(f"{project_id} 的 owner.kind 不是 user/org：{kind!r}")
    return Principal(kind=kind, id=str(stored["id"]))


def build_role_resolver(dsn: str) -> Callable[[str, str], str | None]:
    """`(user_id, org_id) -> role | None`。查得到就是那一行的角色，查不到就是 `None`。"""
    def resolve(user_id: str, org_id: str) -> str | None:
        return _blocking(_fetch_role(dsn, user_id, org_id))

    return resolve


def build_owner_scope_for_project(dsn: str) -> Callable[[str], Principal]:
    """`project_id -> Principal`。项目不存在时抛 `ProjectNotFound`。"""
    def owner_of(project_id: str) -> Principal:
        return _blocking(_fetch_owner(dsn, project_id))

    return owner_of
