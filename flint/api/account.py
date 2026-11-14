"""BE-05：账户端点 `GET /account`（蓝本 R1「端点未建」）。

蓝本外壳 S0 的「用户位」现在写死 `X-User-Id: self`。本卡给它真数据：
**当前 principal 的身份、owner_scope、角色**。

## 身份是头给的，不是查出来的

鉴权中间件（JWT，E3）尚未接线，本层与既有端点一致——以受信 `X-User-Id`
头解析 Principal（`flint/api/analysis.py` 的模块 docstring 写死了这条）。
所以返回的 `principal` **逐字等于头**，NEVER 由本模块另行判定「你是谁」。

由此得出一条结构性质：**本端点没有 id 入参，越权在结构上不可达**。
这里 NEVER 写一个走不到的 404 分支——写了就等于给它留一条日后能被接通的路。

## 三张表都不存在，所以三样都经注入

`users` / `orgs` / `memberships` 在本仓迁移里**一张都没有**。
档案与组织因此全部经注入取，且严格分三态：

- 没注入 → `not_checked`（**没查过**）
- 注入了、库里没有 → `no_record`（**查过了、确实没有**）
- 注入了、查到了 → `known`

拿空列表冒充「你不属于任何组织」，是把一句没查过的话说成了断言。
（同一形状本轮第五次：DOC-01 的 `content=None`、PAY-02 的「配成 0 与没配」、
PAY-01 的「实读与未读到」、BE-03 的「没解引用器时不报 0」、BE-04 的 `not_checked`。）

## NEVER 泄露凭据，也 NEVER 泄露他人

本模块**不碰任何凭据来源**（不读环境变量、不读配置、不持 dsn）——
泄露的上游是「拿得到」，拿不到就漏不出去。

成员关系按调用方过滤**在本模块里再滤一遍**：数据源若按 org 查，会捞到
同组织里别人的行。多租户隔离 NEVER 只靠调用方查对了。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response

from flint.domain.models import Membership, User

UserLoader = Callable[[str], Awaitable[User | None]]
MembershipLoader = Callable[[str], Awaitable[Sequence[Membership]]]


@dataclass
class AccountApiDeps:
    """两个数据源都 **MAY 缺席**——缺席时如实说没查过（见模块 docstring）。"""

    load_user: UserLoader | None = None
    load_memberships: MembershipLoader | None = None


def _profile(user: User | None, caller: str, *, checked: bool) -> dict[str, Any]:
    if not checked:
        return {"status": "not_checked"}
    if user is not None and user.user_id != caller:
        # 数据源拿回来的不是调用方的档案（键错了、或按邮箱查串了行）——
        # **丢掉**。显示出去就是把别人的名字与邮箱贴在你的账户屏上。
        # 与成员关系那一处同一条纪律：多租户隔离 NEVER 只靠调用方查对了。
        user = None
    if user is None:
        # 查过了、库里没有这个人的档案。**NEVER 拿 id 拼一个显示名**——
        # 前端会把它当真名显示，而它是我们编的。
        return {"status": "no_record"}
    return {
        "status": "known",
        "display_name": user.display_name,
        "email": user.email,
        "created_at": user.created_at.isoformat(),
    }


def _memberships(
    rows: Sequence[Membership] | None, caller: str
) -> dict[str, Any]:
    if rows is None:
        return {"status": "not_checked"}
    return {
        "status": "checked",
        "items": [
            {
                "principal": {"kind": "org", "id": row.org_id},
                "role": row.role,
                "via": "membership",
            }
            # 数据源若按 org 查会捞到别人的行——本模块自己再滤一遍。
            for row in rows if row.user_id == caller
        ],
    }


def account_json(
    caller: str, user: User | None, *, profile_checked: bool,
    rows: Sequence[Membership] | None,
) -> dict[str, Any]:
    """三样：身份 / owner_scope / 角色。**NEVER 造第四样。**"""
    return {
        "principal": {"kind": "user", "id": caller},
        "profile": _profile(user, caller, checked=profile_checked),
        "scopes": {
            # 冻结件 Principal docstring：授权 = 归属直属，或经 Membership.role 解析。
            # 第一条分支恒成立（个人使用无需先建 Org），且它**不是**一条 Membership 记录。
            "direct": {
                "principal": {"kind": "user", "id": caller},
                "role": "owner",
                "via": "direct",
            },
            "memberships": _memberships(rows, caller),
        },
    }


def create_account_app(deps: AccountApiDeps) -> FastAPI:
    app = FastAPI(title="Flint account (BE-05)")

    @app.get("/account")
    async def account(x_user_id: str = Header()) -> Response:
        user = await deps.load_user(x_user_id) if deps.load_user else None
        rows = (
            await deps.load_memberships(x_user_id) if deps.load_memberships else None
        )
        return JSONResponse(
            status_code=200,
            content=account_json(
                x_user_id, user,
                profile_checked=deps.load_user is not None, rows=rows,
            ),
        )

    return app
