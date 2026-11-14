"""BE-03：质量卡端点 `GET /deliverables/{id}/quality`（蓝本 R3「端点未建」）。

## 只回布尔、枚举与计数——NEVER 回可靠度分值

技术约束清单第 1 条原话：「是否出现可靠度进度条、百分比、星级、雷达图，
或任何把布尔/枚举画成连续量的表达？**后端不返回这类分值**。」

所以覆盖率给的是**分子与分母两个数**，不是一个比例：
「4 个块里 2 个有引用」前端能列出来；「引用覆盖率 50%」前端会拿它画进度条——
**而那条进度条没有出处**。给了商，也就没人再去想它是怎么算出来的。

本模块**一处除法都没有**（判据打在 AST 上）：比例是除出来的。

## 覆盖率的分母只算 system 且未被用户修改的块

冻结件 `Block` docstring [审3] 原话：「质量卡覆盖率/对齐率**只统计
author=="system" 且未被用户修改的 block**」。

把用户块算进去的话，用户自己写的段落会拉低「我们的引用覆盖」——
那个数说的就不再是系统生成的质量了。被排除的块数**一并报出来**，
否则读的人不知道分母为什么比总块数小。

## 「没检查过」与「检查过、是 0」分得开

未解引用数要真去解一遍才知道。解引用器没注入时本端点**不报 0**——
报 0 等于说「查过了，一个都没有」。它报 `status: "not_checked"`，
且**不给 count 这个键**（给了就还是一个数）。

## 被阻断的块复用既有闸门

`flint/render/gatekeeper.py#check_export` 已经在算这件事（导出门用的就是它）。
本端点直接调它——两处各判各的话，质量卡说「没有阻断」而导出却 409，
用户无从判断该信哪个。

## 越权与不存在同一个出口

403 等于告诉对方「这个 id 存在，只是不给你看」——状态码本身就泄露了存在性。
两种情况走**同一行** `_error(404, "NOT_FOUND", ...)`。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields
from typing import Any

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse, Response

from flint.api.schemas import ErrorBody, ErrorCode
from flint.domain.models import Block
from flint.render.gatekeeper import check_export

BlocksLoader = Callable[[str], Awaitable[list[Block]]]
DeliverableOwner = Callable[[str], Awaitable[str | None]]   # None = 不存在
# 注入式解引用判定：给一个 ref，回它解不解得开。
# **不注入时本端点不猜**——见模块 docstring 的「没检查过」那一段。
RefResolver = Callable[[str], bool]

# `BlockContent` 判别联合里指向别处的字段名。逐个列出而不是「看着像 id 就算」：
# 猜出来的 ref 会让「未解引用」这个数变成一个没人能复核的数。
#
# ## 证据引用与元信息引用**分开数**
#
# 「引用覆盖」说的是**结论有没有出处**（S2-2 的三条出处通道 + 由事实派生的图表）。
# 而 `card_ref`（质量卡）与 `hints_ref`（缺口清单）指的是**关于这份交付物的元信息**，
# 不是证据：把它们算进覆盖率，一份满是缺口提示的交付物会显得「引用充分」——
# 那正好把这个数的意思弄反了。
#
# 两类都进「未解引用」检查：元信息 ref 解不开同样是坏链接。
_EVIDENCE_REF_FIELDS: tuple[str, ...] = ("citation_id", "fact_id", "price_entry_id",
                                         "chart_id")
_META_REF_FIELDS: tuple[str, ...] = ("card_ref", "hints_ref")
_REF_FIELDS: tuple[str, ...] = _EVIDENCE_REF_FIELDS + _META_REF_FIELDS
_REF_LIST_FIELDS: tuple[str, ...] = ("citation_ids", "fact_ids")


@dataclass
class QualityApiDeps:
    load_blocks: BlocksLoader
    deliverable_owner: DeliverableOwner
    ref_resolver: RefResolver | None = None


def _error(status: int, code: ErrorCode, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorBody(code=code, message=message).model_dump(exclude_none=True),
    )


def _refs(block: Block, names_wanted: tuple[str, ...],
          lists_wanted: tuple[str, ...] = ()) -> list[str]:
    content = block.content
    out: list[str] = []
    names = (
        {f.name for f in fields(content)}
        if hasattr(content, "__dataclass_fields__") else set()
    )
    for name in names_wanted:
        if name in names and getattr(content, name):
            out.append(str(getattr(content, name)))
    for name in lists_wanted:
        if name in names:
            out.extend(str(v) for v in getattr(content, name) or [])
    return out


def block_refs(block: Block) -> list[str]:
    """一个 block 指向别处的**所有** ref（证据 + 元信息）。

    **按字段名取，NEVER 靠形状猜**：猜出来的 ref 会让「未解引用」这个数
    变成一个没人能复核的数。
    """
    return _refs(block, _REF_FIELDS, _REF_LIST_FIELDS)


def evidence_refs(block: Block) -> list[str]:
    """只算**证据**引用——覆盖率用这一个（见上面那段注释）。"""
    return _refs(block, _EVIDENCE_REF_FIELDS, _REF_LIST_FIELDS)


def counted_blocks(blocks: list[Block]) -> list[Block]:
    """进覆盖率分母的块：**system 且未被用户修改**（冻结件 [审3]）。"""
    return [b for b in blocks if b.author == "system" and not b.user_modified]


def quality_json(
    deliverable_id: str, blocks: list[Block], resolver: RefResolver | None,
) -> dict[str, Any]:
    """块清单 → 质量卡。只出计数、布尔、枚举与 id 列表。"""
    counted = counted_blocks(blocks)
    with_refs = [b for b in counted if evidence_refs(b)]
    check = check_export(blocks)

    if resolver is None:
        # **不报 0**：报 0 等于说「查过了，一个都没有」。
        # 连 `count` 这个键都不给——给了它就还是一个数。
        unresolved: dict[str, Any] = {"status": "not_checked"}
    else:
        bad = sorted({ref for b in blocks for ref in block_refs(b) if not resolver(ref)})
        unresolved = {"status": "checked", "count": len(bad), "ids": bad}

    return {
        "deliverable_id": deliverable_id,
        "citation_coverage": {
            "blocks_counted": len(counted),
            "blocks_with_refs": len(with_refs),
            # 被排除的块数一并报出来，否则读的人不知道分母为什么比总块数小。
            "blocks_excluded_user": len(blocks) - len(counted),
        },
        "unresolved": unresolved,
        "gap_hint_refs": sorted({
            str(b.content.hints_ref)
            for b in blocks if hasattr(b.content, "hints_ref")
        }),
        # 阻断态四项全部来自既有闸门，NEVER 另写一遍判断。
        "blocking_block_ids": list(check.blocking_block_ids),
        "blocking_open": check.blocking_open,
        "advisory_open": check.advisory_open,
        "exportable": check.exportable,
    }


def create_quality_app(deps: QualityApiDeps) -> FastAPI:
    app = FastAPI(title="Flint quality card (BE-03)")

    @app.get("/deliverables/{deliverable_id}/quality")
    async def quality_card(deliverable_id: str, x_user_id: str = Header()) -> Response:
        owner = await deps.deliverable_owner(deliverable_id)
        if owner is None or owner != x_user_id:
            # 越权与不存在**同一行**：差一个字都能被用来枚举 id。
            return _error(404, "NOT_FOUND", f"unknown deliverable: {deliverable_id}")
        blocks = await deps.load_blocks(deliverable_id)
        return JSONResponse(
            status_code=200,
            content=quality_json(deliverable_id, blocks, deps.ref_resolver),
        )

    return app
