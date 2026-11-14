"""DESIGN-16 验收：导出闸门基线（fact_removed=blocking + 空假设边拒绝）。

acceptance：
① **两判据命中 → 拒绝并列阻塞项清单**；
② **沿审11 blocking 语义（§9-P2 基线：判据在调用点）**。

## 为什么拒绝时必须列清单

一句「不能导出」会让用户去逐块翻找，而系统明明知道是哪几处。清单不是贴心，
是**可执行**：他要照着它一条条处理完才能导出。

## 两条判据为什么并列而不是短路

fact_removed（事实被撤了）与空假设边（连线说不出理由）是**两种不同的病**，
修法也不同。命中第一条就返回，用户改完再点导出又被第二条拦下——
一次说清所有问题（与 FAV-05 批量入台同一条纪律）。

## §9-P2 基线（判据在调用点）

owner 未采纳 P2 的判据注册表，故本卡按 D2 基线把两条判据写在闸门这一处。
风险登记见 `docs/trace/DESIGN-16.md`：第三个判据出现时要做一次抽取重构。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from flint.design.export_gate import (
    DesignExportBlocked,
    check_design_export,
    guard_design_export,
)
from tests.v04._source_scan import code_names

SRC = Path(__file__).resolve().parents[3] / "flint" / "design" / "export_gate.py"


def _blocks(*, removed: bool = False, advisory: bool = False) -> list[object]:
    from flint.domain.models import Block, TextSpan

    def block(bid: str, needs: bool, reason: str | None, severity: str | None) -> Block:
        return Block(
            block_id=bid, deliverable_id="d-1", section_id="s-1", order=0,
            type="paragraph", content=TextSpan(kind="text", text="正文"),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
            needs_review=needs, review_reason=reason,  # type: ignore[arg-type]
            review_severity=severity,  # type: ignore[arg-type]
        )

    rows = [block("b-1", False, None, None)]
    if removed:
        rows.append(block("b-2", True, "fact_removed", "blocking"))
    if advisory:
        rows.append(block("b-3", True, "fact_changed", "advisory"))
    return rows


def _edges(*, empty_hypothesis: bool = False) -> list[dict[str, str]]:
    rows = [{"edge_id": "e-1", "hypothesis": "共用同一条供应链"}]
    if empty_hypothesis:
        rows.append({"edge_id": "e-2", "hypothesis": "   "})
    return rows


# ───────────────────────── 判据一：fact_removed = blocking（审11）


def test_fact_removed_blocks_export() -> None:
    result = check_design_export(blocks=_blocks(removed=True), edges=_edges())

    assert result.exportable is False
    assert [v.criterion for v in result.violations] == ["fact_removed"]
    assert [v.ref for v in result.violations] == ["b-2"]


def test_advisory_does_not_block() -> None:
    """advisory 不拦（审11）：拦住的话用户会以为自己被卡死了。"""
    result = check_design_export(blocks=_blocks(advisory=True), edges=_edges())

    assert result.exportable is True
    assert result.violations == []


# ───────────────────────── 判据二：空假设边


def test_empty_hypothesis_edge_blocks_export() -> None:
    result = check_design_export(blocks=_blocks(), edges=_edges(empty_hypothesis=True))

    assert result.exportable is False
    assert [v.criterion for v in result.violations] == ["empty_hypothesis"]
    assert [v.ref for v in result.violations] == ["e-2"]


def test_whitespace_only_hypothesis_counts_as_empty() -> None:
    """只有空格的假设说明不了任何事，却能骗过「非空」这种粗筛。"""
    result = check_design_export(
        blocks=_blocks(), edges=[{"edge_id": "e-9", "hypothesis": "\t\n "}]
    )

    assert result.exportable is False


# ───────────────────────── 两条并列：一次说清所有问题


def test_both_criteria_are_reported_together() -> None:
    """命中两条就都列出来，NEVER 命中第一条就返回。

    短路的话用户改完第一条再点导出又被第二条拦下——他会觉得系统在挤牙膏。
    """
    result = check_design_export(
        blocks=_blocks(removed=True), edges=_edges(empty_hypothesis=True)
    )

    assert result.exportable is False
    assert sorted(v.criterion for v in result.violations) == [
        "empty_hypothesis", "fact_removed",
    ]


def test_violation_carries_what_and_where_and_how_to_fix() -> None:
    """每条违规带得出：哪条判据、哪个对象、怎么处理。"""
    result = check_design_export(
        blocks=_blocks(removed=True), edges=_edges(empty_hypothesis=True)
    )

    for violation in result.violations:
        assert violation.criterion
        assert violation.ref
        assert violation.action          # 一句能照着做的话，而不是「请修正」


def test_clean_state_exports() -> None:
    """阴性对照：都干净时放行（否则「拒绝」可能只是因为它谁都拒）。"""
    result = check_design_export(blocks=_blocks(), edges=_edges())

    assert result.exportable is True
    assert result.violations == []


# ───────────────────────── 守卫：拒绝时抛，且异常里带清单


def test_guard_raises_with_the_full_list() -> None:
    with pytest.raises(DesignExportBlocked) as err:
        guard_design_export(
            blocks=_blocks(removed=True),
            edges=_edges(empty_hypothesis=True),
            render=lambda: "NEVER 该被渲染",
        )

    assert len(err.value.violations) == 2
    assert "fact_removed" in str(err.value)
    assert "empty_hypothesis" in str(err.value)


def test_guard_does_not_render_when_blocked() -> None:
    """拒绝时**不渲染**：渲染完再拒等于白花一次算力，也可能留下半个产物。"""
    rendered: list[str] = []

    with pytest.raises(DesignExportBlocked):
        guard_design_export(
            blocks=_blocks(removed=True),
            edges=_edges(),
            render=lambda: rendered.append("x") or "out",
        )

    assert rendered == []


def test_guard_renders_when_clean() -> None:
    out = guard_design_export(
        blocks=_blocks(), edges=_edges(), render=lambda: "产物"
    )

    assert out == "产物"


def test_gate_reuses_the_existing_block_severity_source() -> None:
    """审11 的 blocking 语义来自既有门禁模块，本卡不另定一套严重度。"""
    names = code_names(SRC)

    assert "flint.render.gatekeeper" in names
    assert "check_export" in names
