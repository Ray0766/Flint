"""BE-11：PriceBook 与 Profile 读端点（暴露 `flint/pricebook` + `flint/profile`）。

支撑报告里 **PriceCell** 与 **ProfileRef** 两个通道的解引用。

## 三通道各回各的（S2-2）

Fact / PriceCell / ProfileRef 是三条互不混用的出处通道。所以：

- 价格那条路上不出现 profile 字段，涉我那条路上不出现价格；
- **两条路都不碰 Fact 通道**——那是 `flint/api/deref.py`（FB-04）的事。
  混用的第一步恒是「顺手在这里也解一下 fact」，所以本模块连它都不 import。

## 过期价照实标，NEVER 静默用旧价

时效状态与价格**一起返回**：过期不等于不给——给，但要标。
静默用旧价的后果是报告里那个数看起来和新价一模一样，而它是两年前的。

判定转调既有 `check_stale`（30.44 天/月的日粒度口径写在那里），
质量卡注记转调 `price_data_notes`。本模块**一次日期运算都不做**。

## 无出处的条目：查得到，但不可引

`make_price_cell` 的口径：`source` 为空的条目 NEVER 可被预算表引用。
本端点不拒绝返回它（查得到是一回事），但**必须把 `citable: false` 说出来**——
不说的话，调用方会拿它去填单元格。能不能引由既有构造点判，本模块不另判一次。

## 视角是判出来的，不是请求里带的

`viewer_role` 若能由调用方递进来，等于人人可自称 owner，D12 的敏感度口径当场作废。
所以它经 `viewer_role_for(caller, profile)` **判定**，且本模块的处理函数里
连一个叫 role 的参数都没有（判据钉在签名上）。

判不出视角（既不是 owner、也确认不了是同事）→ **404**，
而不是给一份过滤后的 profile：给了就等于承认「这个 profile 存在」。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response

from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import GapHint, PriceEntry, Principal, UserProfile
from flint.pricebook.cell import PriceChannelViolation, make_price_cell
from flint.pricebook.stale import check_stale, price_data_notes
from flint.profile.ref import make_ref_or_gap, resolve_profile_field
from flint.profile.store import ViewerRole, scoped_view

EntryLoader = Callable[[], Awaitable[list[PriceEntry]]]
ProfileLoader = Callable[[str], Awaitable[UserProfile | None]]
RoleResolver = Callable[[Principal, UserProfile], "ViewerRole | None"]

_PROBE_QUANTITY = 1.0


@dataclass
class PriceProfileApiDeps:
    load_entries: EntryLoader
    load_profile: ProfileLoader
    viewer_role_for: RoleResolver
    today: Callable[[], date]


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message).model_dump(exclude_none=True),
    )


def _citable(entry: PriceEntry) -> bool:
    """能不能被预算表引用——**由既有构造点说了算**，本模块不另判一次。

    两处各判各的那天，这里说「可引」而构造点抛异常，用户看不出是哪一边错了。
    """
    try:
        make_price_cell(entry, _PROBE_QUANTITY)
    except PriceChannelViolation:
        return False
    return True


def entry_json(entry: PriceEntry, today: date) -> dict[str, Any]:
    """一条价格。字段逐字对齐冻结件 `PriceEntry`，外加时效与可引性两项判定。"""
    check = check_stale(entry, today)
    return {
        "entry_id": entry.entry_id,
        "item": entry.item,
        "unit": entry.unit,
        "price_low": entry.price_low,
        "price_high": entry.price_high,
        "currency": entry.currency,
        "region": entry.region,
        "year": entry.year,
        "source": entry.source,
        "updated_at": entry.updated_at.isoformat(),
        "stale_after_months": entry.stale_after_months,
        # 过期仍可用，但双重标注缺一不可（黄标位 + 年份）。
        "freshness": {"stale": check.stale, "yellow_flag": check.yellow_flag,
                      "year": check.year},
        "citable": _citable(entry),
    }


def profile_json(profile: UserProfile) -> dict[str, Any]:
    """一份（已按视角过滤的）profile。字段逐字对齐冻结件 `UserProfile`。

    **不回 owner**：调用方要么是 owner 本人，要么是被判定过的同事——
    回一个 id 出去只多一条把别人身份带出去的路。
    """
    return {
        "profile_id": profile.profile_id,
        "identity": profile.identity,
        "research": profile.research,
        "team": profile.team,
        "assets": profile.assets,
        "constraints": profile.constraints,
        "track_record": profile.track_record,
        "locale": profile.locale,
        "updated_at": profile.updated_at.isoformat(),
    }


def gap_json(gap: GapHint) -> dict[str, Any]:
    """一个缺口。**`missing_permission` 绝不伪装成缺资料**（审8）。

    伪装的话，团队成员会去「补录」一份 owner 不想给他看的东西。
    """
    return {
        "missing_what": gap.missing_what,
        "cause": gap.cause,
        "suggested_sources": list(gap.suggested_sources),
        "action": gap.action,
        "required_scope": gap.required_scope,
    }


def create_pricebook_app(deps: PriceProfileApiDeps) -> FastAPI:
    app = FastAPI(title="Flint pricebook & profile (BE-11)")

    async def _scoped(profile_id: str, caller: Principal) -> UserProfile | None:
        loaded = await deps.load_profile(profile_id)
        if loaded is None:
            return None
        role = deps.viewer_role_for(caller, loaded)
        if role is None:
            # 判不出视角就是看不到。返回过滤后的 profile 等于承认它存在。
            return None
        # 过滤在**读取面**执行——无权字段不出库（M3-014 的硬条款）。
        return scoped_view(loaded, role)

    # ── PriceCell 通道 ─────────────────────────────────────
    @app.get("/pricebook")
    async def list_prices(x_user_id: str = Header()) -> Response:
        del x_user_id      # 身份是入口要求；价格表全局共享，不按 owner 切
        today = deps.today()
        entries = await deps.load_entries()
        return JSONResponse(
            status_code=200,
            content={
                "items": [entry_json(e, today) for e in entries],
                # 质量卡那句注记也转调既有实现。
                "notes": price_data_notes(list(entries), today),
            },
        )

    @app.get("/pricebook/{entry_id}")
    async def one_price(entry_id: str, x_user_id: str = Header()) -> Response:
        del x_user_id
        today = deps.today()
        for entry in await deps.load_entries():
            if entry.entry_id == entry_id:
                return JSONResponse(status_code=200,
                                    content=entry_json(entry, today))
        return _error(404, "NOT_FOUND", f"unknown price entry: {entry_id}")

    # ── ProfileRef 通道 ────────────────────────────────────
    @app.get("/profile/{profile_id}")
    async def one_profile(profile_id: str, x_user_id: str = Header()) -> Response:
        caller = Principal(kind="user", id=x_user_id)
        profile = await _scoped(profile_id, caller)
        if profile is None:
            return _error(404, "NOT_FOUND", f"unknown profile: {profile_id}")
        return JSONResponse(status_code=200, content=profile_json(profile))

    @app.get("/profile/{profile_id}/fields/{field_path}")
    async def one_field(
        profile_id: str, field_path: str, x_user_id: str = Header()
    ) -> Response:
        caller = Principal(kind="user", id=x_user_id)
        loaded = await deps.load_profile(profile_id)
        if loaded is None:
            return _error(404, "NOT_FOUND", f"unknown profile: {profile_id}")
        role = deps.viewer_role_for(caller, loaded)
        if role is None:
            return _error(404, "NOT_FOUND", f"unknown profile: {profile_id}")

        # 先按视角裁一遍再解——无权字段在这里就已经不在了，
        # 于是 `make_ref_or_gap` 走的是「解不出 + 该路径 owner_only」那条分支，
        # 得到 missing_permission 而不是 missing_data。
        visible = scoped_view(loaded, role)
        outcome = make_ref_or_gap(visible, field_path, role)
        if isinstance(outcome, GapHint):
            return JSONResponse(status_code=200,
                                content={"gap": gap_json(outcome)})
        return JSONResponse(
            status_code=200,
            content={
                "ref": {"kind": outcome.kind, "field_path": outcome.field_path},
                "value": resolve_profile_field(visible, field_path),
            },
        )

    return app
