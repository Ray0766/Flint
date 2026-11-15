"""DESIGN-32（隔离带·G22 扩）：导出闸门增第三条判据「模板未固化」。

## 为什么是**加一层**而不是改基线闸门

本卡是隔离带卡：owner 划掉它时，应当只删掉这个文件与它的接线，
`flint/design/export_gate.py`（DESIGN-16 的两条判据）**一个字都不用改**。
所以这里不去动基线，而是提供第三条判据 + 一个把两者串起来的组合函数。

这也是 §9-P2 那场取舍的落点：P2 建议把判据对象化进注册表，owner 未采纳；
基线因此把两条判据写在调用点（D2 基线）。第三条判据来的时候，
本卡没有回头去做那次抽取重构——**因为隔离带的约束比「少一次重构」更硬**：
判据注册表会把三条判据焊在一起，届时划掉本卡就要动那张表。

代价照 DESIGN-16 trace 记的那样存在：三条判据现在分布在两个模块里。
`GateViolation` 的形状是共享的，所以调用点与错误体仍然只有一种。

## 判据本身

生产格式（PDF / vibe_pack zip / 任何要交付出去的东西）**只能用已固化的模板**渲染。
拿一份没固化的样板去导出，等于把探索期的示例数字直接交给客户——
而 G6 的门只管生产渲染这条路，导出是另一个出口。**两个出口都要有门。**

探索期导出（预览、内部分享 HTML）不受这条判据管：那正是探索期该有的自由。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from flint.design.export_gate import (
    DesignExportBlocked,
    GateResult,
    GateViolation,
    check_design_export,
)

# 生产格式：交付出去的那些。探索期的 HTML 预览不在其中。
PRODUCTION_FORMATS: frozenset[str] = frozenset({"pdf", "pack", "docx"})

CRITERION_ID = "template_not_solidified"


def check_template_solidified(
    *, export_format: str, template_id: str | None, registry: Any, owner: Any
) -> list[GateViolation]:
    """第三条判据：生产格式只能用已固化（已注册）的模板渲染。"""
    if export_format not in PRODUCTION_FORMATS:
        return []                       # 探索期导出不受此判据管

    if template_id is None:
        return [
            GateViolation(
                criterion=CRITERION_ID,
                ref=export_format,
                action="先固化这份样板再导出生产格式——"
                       "未固化的样板里还带着示例数字，导出等于把它交给客户",
            )
        ]

    for record in registry.all():
        same_owner = (
            record.owner.kind == owner.kind and record.owner.id == owner.id
        )
        if record.template_id == template_id and same_owner and record.enabled:
            return []

    return [
        GateViolation(
            criterion=CRITERION_ID,
            ref=template_id,
            action="这个模板不在注册表里（或已停用）：固化它，或换一个已固化的模板",
        )
    ]


def check_design_export_with_template(
    *,
    blocks: Sequence[Any],
    edges: Sequence[dict[str, Any]],
    export_format: str,
    template_id: str | None,
    registry: Any,
    owner: Any,
) -> GateResult:
    """基线两条 + 本卡第三条。**基线闸门本身未被改动**（隔离带要求）。"""
    base = check_design_export(blocks=blocks, edges=edges)
    extra = check_template_solidified(
        export_format=export_format, template_id=template_id,
        registry=registry, owner=owner,
    )
    violations = [*base.violations, *extra]
    return GateResult(exportable=not violations, violations=violations)


def guard_design_export_with_template[RenderResult](
    *,
    blocks: Sequence[Any],
    edges: Sequence[dict[str, Any]],
    export_format: str,
    template_id: str | None,
    registry: Any,
    owner: Any,
    render: Callable[[], RenderResult],
) -> RenderResult:
    """先判后渲：三条判据任一命中即拒，且**一次渲染都不发生**。"""
    result = check_design_export_with_template(
        blocks=blocks, edges=edges, export_format=export_format,
        template_id=template_id, registry=registry, owner=owner,
    )
    if not result.exportable:
        raise DesignExportBlocked(result.violations)
    return render()
