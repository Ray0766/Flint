"""BE-04：陈旧与重核端点 `GET /deliverables/{id}/staleness`（蓝本 R4「端点未建」）。

`flint/revalidate/`（7 个模块）已经建好，但**零 API 出口**——前端那条
「陈旧/重核横幅位」拿不到任何数据。本卡把它暴露出来，只做三件事：
转调、拼装、如实报。

## 一行比对逻辑都不写

陈旧判定转调 `flint/analysis/stale_adapter.py#analysis_stale`，
到期日转调 `flint/revalidate/schedule.py#next_due_on`，
事件触发转调 `flint/revalidate/events.py#derive_event_triggers`。

`stale_adapter` 自己的 docstring 写死了为什么：

> 再写一套的后果不是重复劳动，而是同一份分析在两个地方被判成不同的新旧：
> 收藏页说它陈旧、分析页说它是最新的，用户不知道该信哪个。

所以本模块里**没有严重度字面量**（`"blocking"` / `"advisory"` 一个都不出现），
也没有年龄阶梯的天数。它们各有各的唯一真相，抄一份最坏的形态不是抄错，
是**日后只改了一处**。

## 陈旧不隐藏内容，只加标记

DESIGN-12 的既有纪律（失锚仍可见）在这里的形态是：
**陈旧的交付物与新鲜的交付物，响应形状逐字相同**——只有标记值不同。
少给一个键就是「因为旧了所以不给你看」。

本端点**根本不返回正文**，也 NEVER 出一个「已隐藏」的开关：
有那个开关，就迟早有人照它把内容藏起来。

## 「没判过」与「判过、不陈旧」分得开

版本信息缺失时**不报 fresh**——报 fresh 等于告诉用户「这份是最新的」，
而我们根本没能力知道（`flint/fav/stale.py#StaleNotEvaluated` 就是这条）。
`status: "not_checked"` 时**连 `stale` 这个键都不给**。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response

from flint.analysis.stale_adapter import DiffChannel, analysis_stale
from flint.api.schemas import ErrorBody, ErrorCode
from flint.revalidate.events import derive_event_triggers
from flint.revalidate.schedule import next_due_on


@dataclass(frozen=True)
class DeliverableStaleness:
    """判陈旧与算触发所需的全部输入。**由调用方一次给齐**。

    分散成多个查询的话，两次查询之间账本可能前进——那时算出来的判定
    对应的是两个不同时刻的库，而它看起来像一次判定。
    """

    owner: str
    project_id: str
    analysed_at_version: int | None      # None = 快照没记版本 → 判不了
    current_version: int | None
    cited_fact_ids: tuple[str, ...]
    created_on: date
    last_revalidated_on: date | None
    cluster_flags: tuple[str, ...]
    momentum: bool
    refute_doc_ids: tuple[str, ...]
    recent_triggers: tuple[tuple[str, str, date], ...]


StalenessLoader = Callable[[str], Awaitable[DeliverableStaleness | None]]


@dataclass
class StalenessApiDeps:
    load_staleness: StalenessLoader
    diff_channel: DiffChannel
    today: Callable[[], date]


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message).model_dump(exclude_none=True),
    )


def _stale_section(meta: DeliverableStaleness, diff: DiffChannel) -> dict[str, Any]:
    """陈旧判定：**转调适配器**，拿回来原样转出去。"""
    if meta.analysed_at_version is None or meta.current_version is None:
        # 判不了就说判不了。连 `stale` 这个键都不给——
        # 给一个 false 等于告诉用户「这份是最新的」，而我们根本没能力知道。
        return {
            "status": "not_checked",
            "reason": "快照没记账本版本：无从判断新旧，NEVER 猜一个版本",
        }
    verdict = analysis_stale(
        diff,
        project_id=meta.project_id,
        analysed_at_version=meta.analysed_at_version,
        current_version=meta.current_version,
        cited_fact_ids=meta.cited_fact_ids,
    )
    return {
        "status": "checked",
        "stale": verdict.stale,
        "severity": verdict.severity,
        "reason": verdict.reason,
        "fact_ids": list(verdict.fact_ids),
    }


def _triggers_section(meta: DeliverableStaleness, today: date) -> dict[str, Any]:
    """触发原因：定时那条走年龄阶梯，事件那条走既有推导器（含 14 天去重窗口）。"""
    due_on = next_due_on(meta.created_on, meta.last_revalidated_on)
    events = derive_event_triggers(
        deliverable_id="",                       # 去重比的是 (id, kind)，下面统一传空
        cluster_flags=list(meta.cluster_flags),
        momentum_flag=meta.momentum,
        new_strong_refute_doc_ids=list(meta.refute_doc_ids),
        recent=[("", kind, fired) for _did, kind, fired in meta.recent_triggers],
        today=today,
    )
    return {
        "scheduled": {"next_due_on": due_on.isoformat(), "due": due_on <= today},
        "events": [
            {"event_kind": t.event_kind, "evidence_refs": list(t.evidence_refs)}
            for t in events
        ],
    }


def staleness_json(
    deliverable_id: str, meta: DeliverableStaleness, diff: DiffChannel, today: date,
) -> dict[str, Any]:
    """三样：陈旧判定 / 触发原因 / 可重核项。**形状与新旧无关**（见模块 docstring）。"""
    stale = _stale_section(meta, diff)
    triggers = _triggers_section(meta, today)
    checked = stale["status"] == "checked"
    has_signal = bool(triggers["events"]) or triggers["scheduled"]["due"]
    return {
        "deliverable_id": deliverable_id,
        "stale": stale,
        "triggers": triggers,
        "revalidatable": (
            {"can": True, "reason": None}
            if (checked or triggers["events"]) and has_signal
            else {
                "can": False,
                # 不可重核要说**为什么**——只给一个 false，用户不知道该怎么办。
                "reason": (
                    "快照没记账本版本，且没有事件触发：重核跑出来的东西无从与旧结果对比"
                    if not checked else "还没到期，也没有事件触发"
                ),
            }
        ),
    }


def create_staleness_app(deps: StalenessApiDeps) -> FastAPI:
    app = FastAPI(title="Flint staleness & revalidation (BE-04)")

    @app.get("/deliverables/{deliverable_id}/staleness")
    async def staleness(deliverable_id: str, x_user_id: str = Header()) -> Response:
        meta = await deps.load_staleness(deliverable_id)
        if meta is None or meta.owner != x_user_id:
            # 越权与不存在**同一行**：403 会用状态码本身泄露存在性。
            return _error(404, "NOT_FOUND", f"unknown deliverable: {deliverable_id}")
        return JSONResponse(
            status_code=200,
            content=staleness_json(
                deliverable_id, meta, deps.diff_channel, deps.today()),
        )

    return app
