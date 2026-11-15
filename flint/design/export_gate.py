"""DESIGN-16：设计台导出闸门基线（G22 前半，§9-P2 的 D2 基线）。

两条判据：

1. **fact_removed = blocking**（审11）：产物引用的事实被撤了，那句话就没了依据。
   严重度沿用既有 `flint/render/gatekeeper.py#check_export`——本模块不另定一套。
2. **空假设边**：一条说不出两端为什么被连起来的边，在生成时是一条**没有理由的关联**，
   会被当成用户的判断写进文书（与 GRAPH-07 前后端两道拦截同源）。

## 两条并列，不短路

命中第一条就返回的话，用户改完再点导出又被第二条拦下——他会觉得系统在挤牙膏。
一次说清所有问题（与 FAV-05 批量入台同一条纪律）。

## 拒绝时列清单，且每条带「怎么办」

一句「不能导出」会让用户去逐块翻找，而系统明明知道是哪几处。清单不是贴心，
是**可执行**：他要照着它一条条处理完才能导出。

## 拒绝时不渲染

先判后渲：渲染完再拒等于白花一次算力，也可能留下半个产物在磁盘上。

## §9-P2：判据写在这一处（owner 未采纳注册表）

P2 建议把判据对象化进 `ExportGate.register`；owner 未采纳，故本卡按 D2 基线
把两条判据写在闸门这一处。风险照工单 ⑥ 登记：第三个判据出现时要做一次抽取重构。
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from flint.render.gatekeeper import check_export


@dataclass(frozen=True)
class GateViolation:
    """一条阻塞项：哪条判据、哪个对象、怎么处理。"""

    criterion: str
    ref: str
    action: str


@dataclass(frozen=True)
class GateResult:
    exportable: bool
    violations: list[GateViolation]


class DesignExportBlocked(Exception):
    def __init__(self, violations: list[GateViolation]) -> None:
        super().__init__(
            "导出被阻塞："
            + "；".join(f"{v.criterion}({v.ref}) → {v.action}" for v in violations)
        )
        self.violations = violations


def check_design_export(
    *, blocks: Sequence[Any], edges: Sequence[dict[str, Any]]
) -> GateResult:
    """跑完**两条**判据再回结果——NEVER 命中第一条就返回。"""
    violations: list[GateViolation] = []

    # 判据一：审11 的 blocking 语义取自既有门禁，本模块不另定严重度
    check = check_export(list(blocks))
    for block_id in check.blocking_block_ids:
        violations.append(
            GateViolation(
                criterion="fact_removed",
                ref=block_id,
                action="处理该 block 的阻塞级复核（更新引用或撤下这句话）",
            )
        )

    # 判据二：空假设边
    for edge in edges:
        if str(edge.get("hypothesis", "")).strip() == "":
            violations.append(
                GateViolation(
                    criterion="empty_hypothesis",
                    ref=str(edge.get("edge_id", "")),
                    action="给这条连线写一句假设，说明两端为什么相关",
                )
            )

    return GateResult(exportable=not violations, violations=violations)


def guard_design_export[RenderResult](
    *,
    blocks: Sequence[Any],
    edges: Sequence[dict[str, Any]],
    render: Callable[[], RenderResult],
) -> RenderResult:
    """先判后渲：被拒时**一次渲染都不发生**。"""
    result = check_design_export(blocks=blocks, edges=edges)
    if not result.exportable:
        raise DesignExportBlocked(result.violations)
    return render()
