"""DESIGN-30 验收：G5 模板注册表（CRUD/版本/复用列表）。

acceptance（tasks-v04.json#DESIGN-30）：
  注册/**版本递增**/按 **checksum 去重**；注册表不可用 → **阻断固化、不阻断探索**（E6 行）。

## 为什么「不可用」要分两种后果

E6 新降级行：模板注册表不可用时——
  · **固化与生产渲染阻断**：把一个存不进注册表的模板当成「已固化」，
    下次生产渲染就会找不到它，而那时用户已经拿它出过东西了；
  · **探索期不阻断**：设计台里试样式、看预览，不需要注册表参与。
把两者一起阻断会让一次存储故障变成「整个设计台不能用」。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _models() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 2, tzinfo=UTC)
HTML_V1 = "<section>{{title}}<div>{{body}}</div></section>"
HTML_V2 = "<article>{{title}}<p>{{body}}</p></article>"

from flint.design.templates.registry import (
    RegistryUnavailable,
    TemplateRegistry,
    list_templates,
    may_explore,
    register_template,
)


def _owner() -> object:
    return M.Principal(kind="user", id="u1")


def _register(reg: TemplateRegistry, html: str, name: str = "产品单页") -> object:
    return register_template(
        reg, template_id="tpl-1", owner=_owner(), name=name, slots=("title", "body"),
        html=html, source_deliverable_id=None, now=NOW,
        model=M.TemplateRecord, checksum_of=M.template_checksum)


# ── 注册 + 版本递增 ─────────────────────────────────────────────

def test_first_registration_is_version_one() -> None:
    reg = TemplateRegistry()
    rec = _register(reg, HTML_V1)
    assert rec.version == 1
    assert rec.checksum == M.template_checksum(HTML_V1)


def test_new_content_bumps_the_version() -> None:
    reg = TemplateRegistry()
    _register(reg, HTML_V1)
    second = _register(reg, HTML_V2)
    assert second.version == 2, "内容变了就是新版本"
    assert len(list_templates(reg, owner=_owner())) == 2, "旧版本 NEVER 被覆盖掉"


def test_identical_content_is_deduped_by_checksum() -> None:
    """按 checksum 去重：同样的内容重复固化不该产出第二个版本。"""
    reg = TemplateRegistry()
    first = _register(reg, HTML_V1)
    again = _register(reg, HTML_V1)
    assert again.version == first.version
    assert again.checksum == first.checksum
    assert len(list_templates(reg, owner=_owner())) == 1


def test_dedupe_ignores_name_changes() -> None:
    """只按内容去重：改个名字不构成新版本，内容才是模板本身。"""
    reg = TemplateRegistry()
    _register(reg, HTML_V1, name="产品单页")
    again = _register(reg, HTML_V1, name="改了个名字")
    assert again.version == 1
    assert len(list_templates(reg, owner=_owner())) == 1


def test_list_is_scoped_to_owner() -> None:
    reg = TemplateRegistry()
    _register(reg, HTML_V1)
    other = M.Principal(kind="user", id="u2")
    assert list_templates(reg, owner=other) == []


def test_versions_are_ordered_newest_last() -> None:
    reg = TemplateRegistry()
    _register(reg, HTML_V1)
    _register(reg, HTML_V2)
    versions = [r.version for r in list_templates(reg, owner=_owner())]
    assert versions == sorted(versions)


# ── E6：不可用时阻断固化、不阻断探索 ────────────────────────────

def test_unavailable_registry_blocks_solidify() -> None:
    reg = TemplateRegistry(available=False)
    with pytest.raises(RegistryUnavailable, match="固化"):
        _register(reg, HTML_V1)


def test_unavailable_registry_does_not_block_exploration() -> None:
    """探索期照常：试样式、看预览不需要注册表参与。"""
    assert may_explore(TemplateRegistry(available=False)) is True
    assert may_explore(TemplateRegistry()) is True


def test_blocking_message_says_what_still_works() -> None:
    """报错要告诉人「什么还能做」，否则一次存储故障看起来像整个设计台挂了。"""
    reg = TemplateRegistry(available=False)
    with pytest.raises(RegistryUnavailable) as err:
        _register(reg, HTML_V1)
    assert "探索" in str(err.value)


def test_checksum_mismatch_is_impossible_by_construction() -> None:
    """checksum 由内容算出，NEVER 由调用方传入——传入就意味着可以传错。"""
    import inspect

    from flint.design.templates import registry as module

    sig = inspect.signature(register_template)
    assert "checksum" not in sig.parameters, "checksum NEVER 作为入参"
    assert "checksum_of" in sig.parameters
    assert "checksum=" in inspect.getsource(module)
