"""SCHEMA-10 验收：I10 TemplateRecord（版本/插槽/checksum）。

acceptance（tasks-v04.json#SCHEMA-10）：
  slots 元组非空校验；checksum 与内容绑定。

## checksum 为什么必须与内容绑定，而不是「随便存一个串」

模板固化（G5）之后会被**生产渲染**反复使用。若 checksum 与 html 无关，
改了模板却不改 checksum，下游拿到的是「版本号没变、内容已变」的东西——
产物不可复现（CLAUDE.md S2-2 第三条铁律）。
绑定之后，内容一改 checksum 必须跟着改，否则构造期就被拒。

## slots 非空

一个没有插槽的模板不是模板，是一张静态页：固化它没有意义，
而它会占着 `template_id` 让人以为可以拿来生成。
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _load()
NOW = datetime(2026, 8, 2, tzinfo=UTC)
HTML = "<section>{{title}}<div>{{body}}</div></section>"


def _record(**kw: object) -> object:
    base: dict[str, object] = {
        "template_id": "tpl-1", "owner": M.Principal(kind="user", id="u1"),
        "name": "产品单页", "version": 1, "slots": ("title", "body"), "html": HTML,
        "checksum": M.template_checksum(HTML), "source_deliverable_id": None,
        "solidified_at": NOW, "enabled": True}
    base.update(kw)
    return M.TemplateRecord(**base)


def test_fields_present_with_version_slots_checksum() -> None:
    fields = set(M.TemplateRecord.__dataclass_fields__)
    assert {"template_id", "version", "slots", "html", "checksum"} <= fields


def test_valid_record_constructs() -> None:
    """阴性对照：合法值必须造得出来。"""
    r = _record()
    assert r.slots == ("title", "body")
    assert r.checksum == hashlib.sha256(HTML.encode("utf-8")).hexdigest()


def test_empty_slots_are_rejected() -> None:
    """没有插槽的模板不是模板，是一张静态页。"""
    with pytest.raises(ValueError, match="slots"):
        _record(slots=())


def test_blank_slot_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="slots"):
        _record(slots=("title", "   "))


def test_slots_is_a_tuple_not_a_list() -> None:
    """元组：插槽集合固化后不该被就地追加——那会绕过 checksum 绑定。"""
    with pytest.raises(TypeError, match="slots"):
        _record(slots=["title", "body"])


def test_checksum_must_match_content() -> None:
    """改了内容不改 checksum → 构造期被拒（否则产物不可复现）。"""
    with pytest.raises(ValueError, match="checksum"):
        _record(html="<section>{{title}}</section>")     # checksum 仍是旧 HTML 的


def test_checksum_changes_when_content_changes() -> None:
    other = "<section>{{title}}</section>"
    assert M.template_checksum(other) != M.template_checksum(HTML)
    r = _record(html=other, checksum=M.template_checksum(other))
    assert r.checksum == M.template_checksum(other)


def test_template_record_coexists_with_template_spec() -> None:
    """预填表 I10：真件已有 `TemplateSpec`（章节模板）是另一物，命名不冲突。"""
    assert hasattr(M, "TemplateSpec") and hasattr(M, "TemplateRecord")
    assert M.TemplateSpec is not M.TemplateRecord
