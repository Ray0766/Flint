"""主题一族的**写**端点：`POST /projects/{id}/chosen-topic`。

> 本模块由 v0.4.1 第 6 批的 `ENTRY-02` 建（`docs/steward/tasks-v041-b6.json`）。

## 改前

topic 一族三条**全是 GET**（`/topics/{id}` · `/projects/{id}/topics` ·
`/plaza/topics`）。屏上那个「选它」按钮点了没用，
`web/app/projects/[id]/topics/page.tsx` 逐字写着「点它时如实说这条还没接」。

## 为什么不塞进 `views.py`

那份文件的第一句是「**既有模型上的只读端点**」。往里加一个写，
等于让那句话从此不成立——而下一个人读到它时会信它。

## 一行判断都不重写

越界校验与 change_log 追加**转调** `flint/topic/project.py#choose_topic`。
重写一份的后果不是重复劳动，而是**两处对「越界」的定义迟早分叉**，
而它们守的是同一条不变量。

## 幂等在这一侧，不在域函数里

`choose_topic` 每调一次就追一条 change_log——**那对域函数是对的**：
它不知道调用方是不是重复点了同一个按钮。而「同一主题重复选」不该留下第二条：
那会让变更历史看起来像**用户改了两次主意**。所以短路判在这里。

**换**主题时第二条必须留下（判据里有一条阴性对照钉着）——
把幂等实现成「永远不追加」会把「改主意」这件事从历史里抹掉。

## 四种拒绝各说各的（`AUTH-03`）

缺头 401 `IDENTITY_MISSING` · 身份查不到 401 `IDENTITY_UNKNOWN` ·
有身份无角色 403 `PERMISSION_DENIED` · 项目不存在 404 `NOT_FOUND`。

顺序**先认人、再找项目、最后判角色**：先查项目的话，
一个没有身份的调用方也能靠 404/200 的差别探出「哪些项目 id 存在」。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from flint.api.identity import IDENTITY_HEADER, IdentityMissing, RoleMissing
from flint.api.schemas import ErrorBody, ErrorCode
from flint.authz import ProjectNotFound
from flint.domain.models import Principal
from flint.jobs.runner import RoleResolver
from flint.topic.project import ProjectValidationError, choose_topic
from flint.topic.store import PgProjectStore, ProjectVersionConflict

_WRITE_ROLES = frozenset({"owner", "admin", "member"})


class ChosenTopicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_id: str


@dataclass
class TopicsApiDeps:
    dsn: str
    owner_scope_for_project: Callable[[str], Principal]
    role_resolver: RoleResolver
    # `X-User-Id 的值 -> user_id`（`flint/api/identity.py#build_user_check`）。
    # None = 本部署还没接身份闸；那时沿用受信头口径，
    # **NEVER 兜一个默认身份**（兜一个，所有匿名请求都以同一个人的名义写数据）。
    user_check: Callable[[str | None], Awaitable[str]] | None = None


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message).model_dump(exclude_none=True))


def _trusted_header(x_user_id: str | None) -> str:
    if x_user_id is None or not x_user_id.strip():
        raise IdentityMissing(IDENTITY_HEADER)
    return x_user_id.strip()


def _may_write(user_id: str, scope: Principal, roles: RoleResolver) -> bool:
    if scope.kind == "org":
        return roles(user_id, scope.id) in _WRITE_ROLES
    return user_id == scope.id


def create_topics_app(deps: TopicsApiDeps) -> FastAPI:
    app = FastAPI(title="flint-topics-api")
    store = PgProjectStore(deps.dsn)

    @app.post("/projects/{project_id}/chosen-topic")
    async def choose(
        project_id: str,
        body: ChosenTopicRequest,
        x_user_id: str | None = Header(default=None),
    ) -> Response:
        caller_id = (
            await deps.user_check(x_user_id) if deps.user_check is not None
            else _trusted_header(x_user_id)
        )
        # 项目不存在 → 本端点自己翻成 404，NEVER 依赖装配处那个处理器：
        # 那个只在挂载之后生效，子应用被单独起来时同一条路径会 500，
        # 而一条「项目 id 打错了」以 500 收场，读起来是「服务器坏了」。
        try:
            scope = deps.owner_scope_for_project(project_id)
        except ProjectNotFound:
            return _error(404, "NOT_FOUND", f"unknown project: {project_id}")
        if not _may_write(caller_id, scope, deps.role_resolver):
            raise RoleMissing(caller_id, scope.id)

        # LOCK-01：连版本一起读。**改它就得先知道自己在改第几版**——
        # 不带版本地写会走 `save` 的「我在新建」那条路，而这一行已经在库里。
        project, version = await store.load_with_version(project_id)
        if project.chosen_topic_id == body.topic_id:
            # 幂等：同一主题重复选**不留第二条记录**（见模块 docstring）。
            return JSONResponse({"project_id": project_id,
                                 "chosen_topic_id": project.chosen_topic_id})
        try:
            updated = choose_topic(project, body.topic_id)
        except ProjectValidationError as invalid:
            return _error(400, "VALIDATION_FAILED", str(invalid))
        try:
            await store.save(updated, expected_version=version)
        except ProjectVersionConflict as conflict:
            # 409：这一行在我读到它之后被别人改过了。
            # **NEVER 覆盖**——覆盖会把对方那条 change_log 条目无声抹掉，
            # 而 change_log 是这个项目「谁在什么时候改了什么」的唯一记录。
            # 回当前版本，让调用方重读一次再选（重试就这一步，不需要别的策略）。
            return _error(
                409, "PROJECT_CONFLICT",
                f"project {project_id} changed while you were choosing "
                f"(current version {conflict.current_version}); reload and choose again")
        return JSONResponse({"project_id": project_id,
                             "chosen_topic_id": updated.chosen_topic_id})

    return app
