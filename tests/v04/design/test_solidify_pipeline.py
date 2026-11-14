"""DESIGN-28 验收（隔离带·G3）：固化管道（示例 → 插槽 → 注册）。

acceptance：
① **固化产物注册进 G5 且插槽清单与内容一致**；
② **solidify_result 事件带 violations 空集**。

## 固化在做的是一件很具体的事

把探索期那份「长得对但内容是假的」样板，变成一份**只剩形状**的模板：
示例正文换成 `{{block:id}}`、示例文案换成 `{{t:key}}`。
换不干净的后果不是不好看——是那段示例数字会跟着模板进入生产渲染，
而生产渲染只认模板、不再看内容（G6 已立）。**这一步是最后一次能拦住它的地方。**

## 插槽清单与内容必须一致

注册表里记着 slots，渲染时按 slots 要值。清单与 HTML 里实际的插槽对不上，
就会出现「要了一个模板里没有的值」或「模板里有个槽没人填」——
后者会把 `{{block:x}}` 原样渲染给客户看。
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
SRC = REPO_ROOT / "flint" / "design" / "solidify.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.design.solidify import (
    SolidifyBlocked,
    solidify_mock,
    to_slots,
)
from flint.design.templates.registry import TemplateRegistry, list_templates
from tests.v04._source_scan import code_names

# 探索期样板：带水印、占位数字、示例正文与示例文案
MOCK = (
    '<section data-mock-watermark="true">'
    '<h1 data-slot="t:title">示例标题</h1>'
    '<p data-slot="block:b-1">这里是示例正文，渗透率 XX.X%（[来源待补]）</p>'
    "</section>"
)


def _owner() -> Any:
    return M.Principal(kind="user", id="u1")


def _solidify(mock: str = MOCK, **kw: Any) -> Any:
    registry = kw.pop("registry", None) or TemplateRegistry()
    return registry, solidify_mock(
        registry,
        mock_html=mock,
        template_id=kw.pop("template_id", "tpl-1"),
        owner=_owner(),
        name=kw.pop("name", "计划书模板"),
        source_deliverable_id="d-1",
        now=NOW,
        model=M.TemplateRecord,
        event_model=M.SolidifyResult,
        **kw,
    )


# ───────────────────────── 示例 → 插槽


def test_marked_regions_become_slots() -> None:
    html, slots = to_slots(MOCK)

    assert "{{t:title}}" in html
    assert "{{block:b-1}}" in html
    assert slots == ("block:b-1", "t:title")     # 排序稳定，便于比对


def test_example_content_is_gone_after_solidifying() -> None:
    """示例正文与示例数字都不留：这一步是最后一次能拦住它进生产的地方。"""
    html, _ = to_slots(MOCK)

    assert "示例标题" not in html
    assert "示例正文" not in html
    assert "XX.X%" not in html
    assert "[来源待补]" not in html


def test_watermark_is_stripped_from_the_template() -> None:
    """水印属于样板，不属于模板：留着的话，正式产物上会印着「这是样板」。"""
    html, _ = to_slots(MOCK)

    assert "data-mock-watermark" not in html


def test_unmarked_mock_is_rejected() -> None:
    """一个槽都没标 → 拒绝：那不是模板，是一张静态页（契约 slots 非空同款理由）。"""
    with pytest.raises(SolidifyBlocked):
        to_slots('<section data-mock-watermark="true"><p>纯示例</p></section>')


def test_leftover_example_number_is_rejected() -> None:
    """标记之外还留着示例数字 → 拒绝，并指出是哪一处。"""
    dirty = MOCK.replace("</section>", "<p>增速 42.7%</p></section>")

    with pytest.raises(SolidifyBlocked) as err:
        to_slots(dirty)

    assert any("42.7" in v for v in err.value.violations)


# ───────────────────────── 注册 + 事件


def test_solidified_template_lands_in_the_registry() -> None:
    registry, result = _solidify()

    records = list_templates(registry, owner=_owner())
    assert len(records) == 1
    assert records[0].template_id == "tpl-1"
    assert result.accepted is True
    assert result.kind == "solidify_result"
    assert result.reason is None


def test_registered_slots_match_the_html() -> None:
    """acceptance①：插槽清单与内容一致——两侧都算一遍再比。"""
    registry, _ = _solidify()
    record = list_templates(registry, owner=_owner())[0]

    from flint.design.prod_render import SLOT_PATTERN

    in_html = tuple(sorted(set(SLOT_PATTERN.findall(record.html))))
    assert tuple(sorted(record.slots)) == in_html


def test_solidified_template_renders_in_production() -> None:
    """闭环：固化出来的东西，生产渲染门（G6）认得。"""
    registry, _ = _solidify()
    record = list_templates(registry, owner=_owner())[0]

    from flint.design.prod_render import ProductionRenderer

    out = ProductionRenderer(registry=registry, owner=_owner()).render(
        record.template_id, {"block:b-1": "真正的正文", "t:title": "真正的标题"}
    )

    assert "真正的正文" in out
    assert "{{" not in out


def test_event_carries_empty_violations_on_success() -> None:
    """acceptance②：成功时 violations 是**空集**，不是「没有这个字段」。"""
    _, result = _solidify()

    assert result.accepted is True
    assert result.reason is None


def test_blocked_solidify_reports_every_violation() -> None:
    """被拒时一次说清所有问题（与 DESIGN-16 闸门同一条纪律）。"""
    dirty = MOCK.replace("</section>", "<p>增速 42.7%，来源 SRC-1234</p></section>")

    with pytest.raises(SolidifyBlocked) as err:
        _solidify(dirty)

    assert len(err.value.violations) >= 2


def test_registry_unavailable_blocks_solidify_but_says_what_still_works() -> None:
    """注册表不可用 → 阻断固化，但报错要说清**探索仍可继续**（E6 降级行）。"""
    registry = TemplateRegistry(available=False)

    with pytest.raises(Exception) as err:
        _solidify(registry=registry)

    assert "探索" in str(err.value)


def test_module_never_writes_its_own_registry() -> None:
    """注册走 DESIGN-30 的既有实现，本模块不另建存储。"""
    names = code_names(SRC)

    assert "register_template" in names
    for forbidden in ("TemplateRegistry", "asyncpg", "INSERT"):
        assert forbidden not in names
