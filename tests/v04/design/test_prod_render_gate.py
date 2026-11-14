"""DESIGN-31 验收（隔离带·G6）：生产渲染门——只认已注册模板。

acceptance：
① **任意 HTML 进生产路径 → 拒绝；已注册模板放行**；
② **两路径共用 Renderer 接口不同实现（断言）**。

## 这道门是两阶段模型的承重墙

G0 给了探索期几乎无约束的自由，而那份自由的安全性**完全押在这道门上**：
没有它，探索期随手生成的任意 HTML（带示例数字、带外部 CDN、带水印却没人检查）
会直接漏进生产渲染，两阶段就退化成一阶段——工单 §11-③ 的原话是
「G0 的『几乎无约束』就从特性变成事故通道」。

所以判据只有一条、且是**白名单**：生产渲染的输入必须是注册表里的一条记录，
而不是「一段看起来合规的 HTML」。任何「检查一下就放行」的实现都是黑名单，
而黑名单永远漏。
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
SRC = REPO_ROOT / "flint" / "design" / "prod_render.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.design.prod_render import (
    ExploreRenderer,
    ProductionRenderer,
    UnregisteredTemplate,
)
from flint.design.templates.registry import TemplateRegistry, register_template
from tests.v04._source_scan import code_names

TEMPLATE_HTML = "<section>{{block:b-1}}<span>{{t:title}}</span></section>"


def _checksum(html: str) -> str:
    # 用契约那份指纹：注册表构造期就是拿它校验的（另写一份会当场建不出模板）
    return M.template_checksum(html)


def _owner() -> Any:
    return M.Principal(kind="user", id="u1")


def _registry_with_template() -> tuple[TemplateRegistry, Any]:
    registry = TemplateRegistry()
    record = register_template(
        registry, template_id="tpl-1", owner=_owner(), name="计划书",
        slots=("block:b-1", "t:title"), html=TEMPLATE_HTML,
        source_deliverable_id="d-1", now=NOW, model=M.TemplateRecord,
        checksum_of=_checksum,
    )
    return registry, record


# ───────────────────────── 白名单：只认注册表里的记录


def test_registered_template_renders() -> None:
    registry, record = _registry_with_template()
    renderer = ProductionRenderer(registry=registry, owner=_owner())

    out = renderer.render(record.template_id, {"block:b-1": "正文", "t:title": "标题"})

    assert "正文" in out
    assert "标题" in out
    assert "{{" not in out          # 插槽都填上了


def test_arbitrary_html_is_rejected() -> None:
    """任意 HTML 进生产路径 → 拒绝。**接口上根本不收 html**，只收 template_id。"""
    registry, _ = _registry_with_template()
    renderer = ProductionRenderer(registry=registry, owner=_owner())

    with pytest.raises(TypeError):
        renderer.render(html="<h1>随手写的</h1>")  # type: ignore[call-arg]


def test_unknown_template_id_is_rejected() -> None:
    registry, _ = _registry_with_template()
    renderer = ProductionRenderer(registry=registry, owner=_owner())

    with pytest.raises(UnregisteredTemplate):
        renderer.render("tpl-404", {})


def test_another_owners_template_is_not_visible() -> None:
    """别人的模板不算「已注册」：注册表是按 owner 分的（D7）。"""
    registry, record = _registry_with_template()
    renderer = ProductionRenderer(registry=registry, owner=M.Principal(kind="user", id="u2"))

    with pytest.raises(UnregisteredTemplate):
        renderer.render(record.template_id, {})


def test_disabled_template_is_rejected() -> None:
    """停用的模板不再放行：停用就是为了让它别再被用。"""
    registry, record = _registry_with_template()
    registry.all()[0].enabled = False
    renderer = ProductionRenderer(registry=registry, owner=_owner())

    with pytest.raises(UnregisteredTemplate):
        renderer.render(record.template_id, {})


def test_tampered_template_is_rejected() -> None:
    """内容与 checksum 对不上 → 拒绝：那意味着有人绕过注册流程改了模板。"""
    registry, record = _registry_with_template()
    registry.all()[0].html = "<section>被改过{{block:b-1}}</section>"
    renderer = ProductionRenderer(registry=registry, owner=_owner())

    with pytest.raises(UnregisteredTemplate):
        renderer.render(record.template_id, {"block:b-1": "x"})


def test_missing_slot_value_is_rejected() -> None:
    """插槽没给值 → 拒绝，NEVER 渲染出一个 `{{block:b-1}}` 给客户看。"""
    registry, record = _registry_with_template()
    renderer = ProductionRenderer(registry=registry, owner=_owner())

    with pytest.raises(ValueError):
        renderer.render(record.template_id, {"t:title": "只给了一个"})


def test_unknown_slot_value_is_rejected() -> None:
    """给了模板里没有的插槽 → 拒绝：那说明调用方以为自己在填另一个模板。"""
    registry, record = _registry_with_template()
    renderer = ProductionRenderer(registry=registry, owner=_owner())

    with pytest.raises(ValueError):
        renderer.render(
            record.template_id,
            {"block:b-1": "a", "t:title": "b", "block:b-9": "多出来的"},
        )


# ───────────────────────── 两路径是两个实现，入参形状互斥


def test_the_two_renderers_are_two_implementations_not_one_interface() -> None:
    """两个渲染器**不共用**一个接口——这是设计，不是疏漏（终检 F-04）。

    这条原名 `test_both_renderers_share_one_interface`，断的是
    `hasattr(prod, "render") and hasattr(explore, "render")`。**「都有一个叫 render 的方法」
    不等于「共用接口」**：`ExploreRenderer.render(html)` 与
    `ProductionRenderer.render(template_id, slot_values)` 签名互不兼容，不继承共同基类，
    也不实现契约里的 `Renderer`（那个的签名是 `render(deliverable_id, fmt)`，与两者都不是一回事）。

    真正该守的不变量是**入参形状互斥**：生产渲染器根本没有接受 html 的口子。
    强行抽一个共同 Protocol 反而会**削弱**它——那等于给两条路径造一个共同调用点。
    完整判据与反例探针在 `tests/v041/test_renderer_interface.py`（GAUGE-06）。
    """
    registry, _ = _registry_with_template()
    prod = ProductionRenderer(registry=registry, owner=_owner())
    explore = ExploreRenderer()

    assert type(prod) is not type(explore)
    assert not isinstance(prod, ExploreRenderer)
    assert not isinstance(explore, ProductionRenderer)
    assert ProductionRenderer.__mro__[1:] == (object,)      # 无共同基类，NEVER 靠继承串起来
    assert ExploreRenderer.__mro__[1:] == (object,)


def test_explore_renderer_takes_html_and_production_does_not() -> None:
    """两条路径的**入参形状**就不一样：探索收 html，生产只收 template_id。

    这条是这道门最实在的部分：不是「生产渲染器检查了一下 html」，
    而是它**根本没有**接受 html 的口子。
    """
    import inspect

    explore_params = set(inspect.signature(ExploreRenderer.render).parameters)
    prod_params = set(inspect.signature(ProductionRenderer.render).parameters)

    assert "html" in explore_params
    assert "html" not in prod_params
    assert "template_id" in prod_params


def test_production_module_never_falls_back_to_raw_html() -> None:
    """源码里没有任何「拿不到模板就用传进来的 html」的回落路径。"""
    names = code_names(SRC)

    for forbidden in ("srcdoc", "raw_html", "fallback_html"):
        assert forbidden not in names


def test_explore_path_stays_unrestricted() -> None:
    """探索期照旧几乎无约束（G0）：这道门只管生产路径。"""
    assert ExploreRenderer().render("<h1>随手写的</h1>") == "<h1>随手写的</h1>"
