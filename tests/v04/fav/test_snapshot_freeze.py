"""FAV-01 验收：收藏写路径 + 快照冻结（基线内嵌；P1 位）。

acceptance（tasks-v04.json#FAV-01）：
  ① 收藏后**改源** fixture → 快照**字节不变**；
  ② P1 采纳位以注释标记（pin 路径），**基线不实现**。

## 「冻结」在基线里靠的是内嵌，不是保护

SCHEMA-09 定的基线是**内嵌** `evidence_snapshot`：收藏时把内容抄一份带走。
所以「源被改了、被删了、被周删清了」都影响不到它——**冻结是结构性的**，
不依赖任何人记得去保护被引对象。

`§9-P1` 提案才是「改回引用 + 给被引 snapshot 加冻结保护」。那是提案，
owner 未采纳前 NEVER 实现——本卡只在 pin 路径留注释。
"""
from __future__ import annotations

import importlib.util
import json
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

from flint.fav.store import (
    FavoriteStore,
    add_favorite,
    list_favorites,
    remove_favorite,
)


def _source() -> dict[str, object]:
    """可变的「源」——收藏之后我们会改它，看快照会不会跟着变。"""
    return {
        "cluster_id": "c-solid-state",
        "name_native": "全固体電池",
        "top_links": ["doc-1", "doc-2"],
    }


def _owner() -> object:
    return M.Principal(kind="user", id="u1")


def _add(store: FavoriteStore, source: dict[str, object], favorite_id: str = "fav-1") -> object:
    return add_favorite(
        store, favorite_id=favorite_id, owner=_owner(), target_kind="cluster",
        target_id="c-solid-state", evidence_snapshot=source, now=NOW, model=M.Favorite)


# ── ① 快照冻结：改源不动快照 ────────────────────────────────────

def test_mutating_the_source_dict_does_not_touch_the_snapshot() -> None:
    """最容易漏的一种：源是同一个 dict 对象，收藏若只存引用，改源就改了快照。"""
    store = FavoriteStore()
    source = _source()
    fav = _add(store, source)
    frozen = json.dumps(fav.evidence_snapshot, ensure_ascii=False, sort_keys=True)

    source["name_native"] = "被改过的名字"
    source["top_links"].append("doc-3")
    source["extra"] = "新加的字段"

    after = json.dumps(fav.evidence_snapshot, ensure_ascii=False, sort_keys=True)
    assert after == frozen, "改源之后快照跟着变了——说明存的是引用不是副本"


def test_snapshot_is_byte_identical_after_source_deletion() -> None:
    """源整个没了，快照照常可读——冻结是结构性的，不依赖源活着。"""
    store = FavoriteStore()
    source = _source()
    fav = _add(store, source)
    expected = fav.evidence_snapshot["name_native"]
    source.clear()
    assert store.get("fav-1").evidence_snapshot["name_native"] == expected


def test_nested_structures_are_deep_copied() -> None:
    """浅拷贝会漏：顶层键抄了，嵌套的 list/dict 还是同一个对象。"""
    store = FavoriteStore()
    source = _source()
    source["nested"] = {"inner": ["a"]}
    fav = _add(store, source)
    source["nested"]["inner"].append("b")
    assert fav.evidence_snapshot["nested"]["inner"] == ["a"], "嵌套结构没有深拷贝"


def test_reading_back_does_not_expose_the_stored_object() -> None:
    """读出去的也得是副本——否则调用方改一下返回值就改了库里的快照。"""
    store = FavoriteStore()
    _add(store, _source())
    got = store.get("fav-1")
    got.evidence_snapshot["name_native"] = "外部改写"
    assert store.get("fav-1").evidence_snapshot["name_native"] == "全固体電池"


# ── 写路径 ───────────────────────────────────────────────────────

def test_add_is_idempotent_on_same_id() -> None:
    store = FavoriteStore()
    first = _add(store, _source())
    second = _add(store, _source())
    assert first.favorite_id == second.favorite_id
    assert len(list_favorites(store, owner=_owner())) == 1


def test_remove_is_idempotent() -> None:
    store = FavoriteStore()
    _add(store, _source())
    assert remove_favorite(store, favorite_id="fav-1") is True
    assert remove_favorite(store, favorite_id="fav-1") is False


def test_list_is_scoped_to_owner() -> None:
    """越权读 NEVER 发生：别人的收藏不出现在我的列表里。"""
    store = FavoriteStore()
    _add(store, _source())
    other = M.Principal(kind="user", id="u2")
    assert list_favorites(store, owner=other) == []
    assert len(list_favorites(store, owner=_owner())) == 1


def test_snapshot_stale_starts_false() -> None:
    """stale 只能由 Revalidator 置 True（§6-H1）——新收藏一律 False。"""
    store = FavoriteStore()
    fav = _add(store, _source())
    assert fav.snapshot_stale is False


def test_empty_snapshot_is_rejected() -> None:
    """空快照的收藏 = 一个指向空处的壳，正是内嵌要避免的东西。"""
    store = FavoriteStore()
    with pytest.raises(ValueError, match="evidence_snapshot"):
        add_favorite(
            store, favorite_id="fav-x", owner=_owner(), target_kind="cluster",
            target_id="c1", evidence_snapshot={}, now=NOW, model=M.Favorite)


# ── ② P1 采纳位：注释在、实现不在 ────────────────────────────────

def test_p1_pin_path_is_comment_only() -> None:
    source = (REPO_ROOT / "flint" / "fav" / "store.py").read_text(encoding="utf-8")
    comments = [ln for ln in source.split("\n") if ln.strip().startswith("#")]
    assert any("P1" in ln for ln in comments), "pin 路径应有 P1 采纳位注释"
    assert any("pin" in ln.lower() for ln in comments), "注释应写明 pin 的接法"

    import flint.fav.store as store_module

    exported = {n for n in dir(store_module) if not n.startswith("_")}
    for forbidden in ("pin_snapshot", "freeze_snapshot", "protect_snapshot"):
        assert forbidden not in exported, f"P1 未采纳，{forbidden} NEVER 成为真实现"
