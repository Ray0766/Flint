"""DESIGN-32 验收（隔离带·G22 扩）：导出闸门增「模板未固化」判据。

acceptance：
① **未固化模板导出生产格式 → 拒绝并指认判据 id**；
② **被划掉时仅移除本卡与判据注册，基线闸门不受影响**。

## 为什么导出这一侧也要有门

G6（DESIGN-31）管的是**生产渲染**这条路。导出是**另一个出口**：
拿一份没固化的样板直接导出 PDF，示例数字就这样交给了客户，
而它一次都没经过生产渲染。两个出口都要有门。

## 探索期导出不受这条管

预览、内部分享 HTML 属于探索期的自由（G0）。把它们也拦下来，
用户会为了看一眼效果而被迫先固化——那等于把固化变成一道过场手续。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
BASE_GATE_SRC = REPO_ROOT / "flint" / "design" / "export_gate.py"
SRC = REPO_ROOT / "flint" / "design" / "export_gate_template.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.design.export_gate import DesignExportBlocked
from flint.design.export_gate_template import (
    CRITERION_ID,
    PRODUCTION_FORMATS,
    check_design_export_with_template,
    check_template_solidified,
    guard_design_export_with_template,
)
from flint.design.templates.registry import TemplateRegistry, register_template
from tests.v04._source_scan import code_names

TEMPLATE_HTML = "<section>{{block:b-1}}</section>"


def _owner(uid: str = "u1") -> Any:
    return M.Principal(kind="user", id=uid)


def _registry() -> tuple[TemplateRegistry, Any]:
    registry = TemplateRegistry()
    record = register_template(
        registry, template_id="tpl-1", owner=_owner(), name="计划书",
        slots=("block:b-1",), html=TEMPLATE_HTML, source_deliverable_id="d-1",
        now=NOW, model=M.TemplateRecord, checksum_of=M.template_checksum,
    )
    return registry, record


def _blocks() -> list[Any]:
    from flint.domain.models import Block, TextSpan

    return [
        Block(
            block_id="b-1", deliverable_id="d-1", section_id="s-1", order=0,
            type="paragraph", content=TextSpan(kind="text", text="正文"),
            claim_ids=[], fact_ids=[], author="system", revision=1, locked=False,
        )
    ]


def _edges() -> list[dict[str, str]]:
    return [{"edge_id": "e-1", "hypothesis": "共用同一条供应链"}]


# ───────────────────────── 第三条判据本身


def test_production_export_without_template_is_blocked() -> None:
    registry, _ = _registry()

    violations = check_template_solidified(
        export_format="pdf", template_id=None, registry=registry, owner=_owner()
    )

    assert [v.criterion for v in violations] == [CRITERION_ID]
    assert violations[0].action


def test_unregistered_template_is_blocked() -> None:
    registry, _ = _registry()

    violations = check_template_solidified(
        export_format="pack", template_id="tpl-404", registry=registry, owner=_owner()
    )

    assert [v.criterion for v in violations] == [CRITERION_ID]
    assert violations[0].ref == "tpl-404"


def test_registered_template_passes() -> None:
    registry, record = _registry()

    assert check_template_solidified(
        export_format="pdf", template_id=record.template_id,
        registry=registry, owner=_owner(),
    ) == []


def test_another_owners_template_is_blocked() -> None:
    """别人的模板不算已固化（D7，与 G6 门同一口径）。"""
    registry, record = _registry()

    violations = check_template_solidified(
        export_format="pdf", template_id=record.template_id,
        registry=registry, owner=_owner("u2"),
    )

    assert [v.criterion for v in violations] == [CRITERION_ID]


def test_disabled_template_is_blocked() -> None:
    registry, record = _registry()
    registry.all()[0].enabled = False

    violations = check_template_solidified(
        export_format="pdf", template_id=record.template_id,
        registry=registry, owner=_owner(),
    )

    assert [v.criterion for v in violations] == [CRITERION_ID]


def test_exploration_export_is_not_gated() -> None:
    """探索期导出（html 预览）不受这条管：那是 G0 该有的自由。"""
    registry, _ = _registry()

    assert check_template_solidified(
        export_format="html", template_id=None, registry=registry, owner=_owner()
    ) == []
    assert "html" not in PRODUCTION_FORMATS


# ───────────────────────── 与基线两条并列


def test_three_criteria_are_reported_together() -> None:
    """基线两条 + 本卡一条，一次说清（与 DESIGN-16 同一条纪律）。"""
    registry, _ = _registry()
    blocks = _blocks()
    blocks[0].needs_review = True
    blocks[0].review_reason = "fact_removed"
    blocks[0].review_severity = "blocking"

    result = check_design_export_with_template(
        blocks=blocks, edges=[{"edge_id": "e-2", "hypothesis": "  "}],
        export_format="pdf", template_id=None, registry=registry, owner=_owner(),
    )

    kinds = sorted(v.criterion for v in result.violations)
    assert kinds == ["empty_hypothesis", "fact_removed", CRITERION_ID]
    assert result.exportable is False


def test_clean_state_exports() -> None:
    registry, record = _registry()

    result = check_design_export_with_template(
        blocks=_blocks(), edges=_edges(), export_format="pdf",
        template_id=record.template_id, registry=registry, owner=_owner(),
    )

    assert result.exportable is True
    assert result.violations == []


def test_guard_blocks_before_rendering() -> None:
    registry, _ = _registry()
    rendered: list[str] = []

    with pytest.raises(DesignExportBlocked):
        guard_design_export_with_template(
            blocks=_blocks(), edges=_edges(), export_format="pdf",
            template_id=None, registry=registry, owner=_owner(),
            render=lambda: rendered.append("x") or "out",
        )

    assert rendered == []


def test_guard_renders_when_clean() -> None:
    registry, record = _registry()

    out = guard_design_export_with_template(
        blocks=_blocks(), edges=_edges(), export_format="pdf",
        template_id=record.template_id, registry=registry, owner=_owner(),
        render=lambda: "产物",
    )

    assert out == "产物"


# ───────────────────────── acceptance②：零下游破坏


def test_base_gate_is_untouched_by_this_card() -> None:
    """基线闸门里没有本卡的判据 id：划掉本卡 = 删这一个文件。"""
    base_source = BASE_GATE_SRC.read_text(encoding="utf-8")

    assert CRITERION_ID not in base_source
    assert "export_gate_template" not in base_source


def test_this_card_depends_on_base_not_the_other_way() -> None:
    """依赖方向只有「本卡 → 基线」，反向一条都没有。"""
    names = code_names(SRC)

    assert "flint.design.export_gate" in names
    assert "check_design_export" in names


def test_base_gate_still_works_on_its_own() -> None:
    """基线两条判据独立可用——本卡不在时它照常拦。"""
    from flint.design.export_gate import check_design_export

    result = check_design_export(
        blocks=_blocks(), edges=[{"edge_id": "e-2", "hypothesis": ""}]
    )

    assert result.exportable is False
    assert [v.criterion for v in result.violations] == ["empty_hypothesis"]
