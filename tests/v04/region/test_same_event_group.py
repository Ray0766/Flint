"""REGION-05 验收：same_event_group 显式建解（禁自动建组）。

acceptance（tasks-v04.json#REGION-05）：
  ① 建组/解组端点幂等；
  ② embedding 相似度路径不存在（**模块导出面断言**）。

## 为什么「不存在」比「默认关闭」强

`PRINCIPLES#B5`：跨区关联的唯一合法通道是 same_event_group **显式建立**。
留一个 `auto_group(threshold=…)` 函数而默认不调用，等于留一条「有人调用它就自动跨区合并」的路——
而 B5 要防的正是 embedding 把两国报道合成一簇。所以这里断言的是**导出面上根本没有这条路**。
"""
from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from flint.region import same_event
from flint.region.same_event import (
    SameEventGroup,
    SameEventStore,
    dissolve_group,
    establish_group,
)

NOW = datetime(2026, 8, 2, tzinfo=UTC)


def _store() -> SameEventStore:
    return SameEventStore()


# ── ① 幂等 ────────────────────────────────────────────────────────

def test_establish_is_idempotent() -> None:
    store = _store()
    first = establish_group(
        store, group_id="g1", cluster_ids=["us-1", "jp-1"], actor="user:u1", now=NOW)
    second = establish_group(
        store, group_id="g1", cluster_ids=["us-1", "jp-1"], actor="user:u1", now=NOW)
    assert first == second
    assert len(store.all()) == 1, "重复建组 NEVER 产出第二个组"


def test_dissolve_is_idempotent() -> None:
    store = _store()
    establish_group(store, group_id="g1", cluster_ids=["us-1", "jp-1"],
                    actor="user:u1", now=NOW)
    assert dissolve_group(store, group_id="g1") is True
    assert dissolve_group(store, group_id="g1") is False, "解不存在的组返回 False 而不是抛错"
    assert store.all() == []


def test_establish_after_dissolve_starts_clean() -> None:
    store = _store()
    establish_group(store, group_id="g1", cluster_ids=["us-1", "jp-1"],
                    actor="user:u1", now=NOW)
    dissolve_group(store, group_id="g1")
    again = establish_group(store, group_id="g1", cluster_ids=["us-1", "au-1"],
                            actor="user:u2", now=NOW)
    assert again.cluster_ids == ("us-1", "au-1")
    assert len(store.all()) == 1


# ── 建组是**显式操作**：必须留下谁建的 ──────────────────────────────

def test_group_records_who_established_it() -> None:
    """显式建立 = 有主体。没有 actor 的组就是「系统自动建的」，那正是要禁的。"""
    store = _store()
    group = establish_group(store, group_id="g1", cluster_ids=["us-1", "jp-1"],
                            actor="user:u1", now=NOW)
    assert isinstance(group, SameEventGroup)
    assert group.established_by == "user:u1"
    assert group.established_at == NOW


def test_blank_actor_is_rejected() -> None:
    store = _store()
    with pytest.raises(ValueError, match="actor"):
        establish_group(store, group_id="g1", cluster_ids=["us-1", "jp-1"],
                        actor="   ", now=NOW)


def test_group_needs_at_least_two_clusters() -> None:
    store = _store()
    with pytest.raises(ValueError, match="cluster_ids"):
        establish_group(store, group_id="g1", cluster_ids=["us-1"], actor="user:u1", now=NOW)


# ── ② 导出面上没有自动建组的路 ────────────────────────────────────

def test_no_similarity_based_path_in_module_surface() -> None:
    """模块导出面断言：NEVER 有靠相似度自动建组的入口。"""
    exported = {n for n in dir(same_event) if not n.startswith("_")}
    forbidden = {
        "auto_group", "auto_establish", "group_by_similarity", "cluster_similarity",
        "embedding", "cosine", "threshold", "similarity",
    }
    hit = exported & forbidden
    assert not hit, f"导出面上出现自动建组入口 {hit}：留一条路就等于允许它被走 [B5]"


def test_no_embedding_symbol_in_source() -> None:
    """源码里没有相似度计算的**标识符**。

    只扫标识符、NEVER 扫全文：docstring 里解释「要防的正是 embedding 自动合并」
    是说明文字，把它当成实现会红在一个本来正确的模块上（SCHEMA-09 踩过同一个坑）。
    """
    import ast

    tree = ast.parse(inspect.getsource(same_event))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name)
    lowered = {n.lower() for n in names}
    for forbidden in ("embedding", "cosine", "vector", "centroid", "similarity"):
        hit = {n for n in lowered if forbidden in n}
        assert not hit, f"源码标识符里出现 {hit}：本模块 NEVER 参与相似度计算"


def test_establish_signature_takes_explicit_ids_only() -> None:
    """入参只有显式 id 与 actor —— 没有任何「按什么自动找」的参数。"""
    params = set(inspect.signature(establish_group).parameters)
    assert params == {"store", "group_id", "cluster_ids", "actor", "now"}
