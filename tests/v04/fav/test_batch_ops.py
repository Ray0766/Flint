"""FAV-05 验收（后端半）：批量入台单事务 + 批量取消。

acceptance（tasks-v04.json#FAV-05）：**部分失败整体回滚 + 报错清单**（事务断言）。

## 为什么必须是「全成或全不成」

批量入台 20 条，第 13 条失败——若前 12 条已经落了台，用户看到的是
「一半进去了、一半没有」，而他**并不知道是哪一半**。再点一次批量入台，
前 12 条要么重复、要么因幂等静默跳过，两种都让人无法确认最终状态。

所以：**要么全成，要么全不成 + 一份说清哪条为什么失败的清单**。
清单不是可选项——只回滚不报错，用户会以为是自己没点到。
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
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.fav.batch import (
    BatchFailure,
    BatchRejected,
    batch_add_to_workbench,
    batch_remove_favorites,
)
from flint.fav.store import FavoriteStore, add_favorite, list_favorites
from flint.graph.store import GraphStore


def _owner() -> object:
    return M.Principal(kind="user", id="u1")


def _seed(store: FavoriteStore, ids: list[str]) -> None:
    for fid in ids:
        add_favorite(
            store, favorite_id=fid, owner=_owner(), target_kind="cluster",
            target_id=f"c-{fid}", evidence_snapshot={"cluster_id": f"c-{fid}"},
            now=NOW, model=M.Favorite)


# ── 批量入台：全成 ──────────────────────────────────────────────

def test_all_succeed_commits_everything() -> None:
    favs = FavoriteStore(); graph = GraphStore()
    _seed(favs, ["f-1", "f-2", "f-3"])
    added = batch_add_to_workbench(
        favs, graph, favorite_ids=["f-1", "f-2", "f-3"], graph_id="g1",
        owner=_owner(), now=NOW, node_model=M.GraphNode)
    assert len(added) == 3
    assert len(graph.nodes("g1")) == 3


# ── 批量入台：部分失败 → 整体回滚 + 报错清单 ──────────────────

def test_partial_failure_rolls_everything_back() -> None:
    favs = FavoriteStore(); graph = GraphStore()
    _seed(favs, ["f-1", "f-2"])
    with pytest.raises(BatchRejected) as err:
        batch_add_to_workbench(
            favs, graph, favorite_ids=["f-1", "f-404", "f-2"], graph_id="g1",
            owner=_owner(), now=NOW, node_model=M.GraphNode)
    assert graph.nodes("g1") == [], "部分失败时 MUST 整体回滚——NEVER 留下「一半进去了」"
    assert isinstance(err.value.failures[0], BatchFailure)


def test_failure_report_names_the_offender_and_the_reason() -> None:
    """清单不是可选项：只回滚不报错，用户会以为是自己没点到。"""
    favs = FavoriteStore(); graph = GraphStore()
    _seed(favs, ["f-1"])
    with pytest.raises(BatchRejected) as err:
        batch_add_to_workbench(
            favs, graph, favorite_ids=["f-1", "f-404"], graph_id="g1",
            owner=_owner(), now=NOW, node_model=M.GraphNode)
    failures = err.value.failures
    assert [f.favorite_id for f in failures] == ["f-404"]
    assert failures[0].reason


def test_all_failures_are_collected_not_just_the_first() -> None:
    """一次说清所有问题——只报第一条会逼用户改一条试一次。"""
    favs = FavoriteStore(); graph = GraphStore()
    with pytest.raises(BatchRejected) as err:
        batch_add_to_workbench(
            favs, graph, favorite_ids=["f-a", "f-b", "f-c"], graph_id="g1",
            owner=_owner(), now=NOW, node_model=M.GraphNode)
    assert {f.favorite_id for f in err.value.failures} == {"f-a", "f-b", "f-c"}


def test_cross_owner_favorite_is_rejected_not_silently_skipped() -> None:
    """越权项 MUST 报错，NEVER 静默跳过——静默跳过等于悄悄少做了事。"""
    favs = FavoriteStore(); graph = GraphStore()
    _seed(favs, ["f-1"])
    other = M.Principal(kind="user", id="u2")
    with pytest.raises(BatchRejected) as err:
        batch_add_to_workbench(
            favs, graph, favorite_ids=["f-1"], graph_id="g1",
            owner=other, now=NOW, node_model=M.GraphNode)
    assert err.value.failures[0].favorite_id == "f-1"
    assert graph.nodes("g1") == []


def test_empty_batch_is_rejected() -> None:
    favs = FavoriteStore(); graph = GraphStore()
    with pytest.raises(ValueError, match="favorite_ids"):
        batch_add_to_workbench(
            favs, graph, favorite_ids=[], graph_id="g1",
            owner=_owner(), now=NOW, node_model=M.GraphNode)


# ── 批量取消 ────────────────────────────────────────────────────

def test_batch_remove_all_or_nothing() -> None:
    favs = FavoriteStore()
    _seed(favs, ["f-1", "f-2"])
    with pytest.raises(BatchRejected):
        batch_remove_favorites(favs, favorite_ids=["f-1", "f-404"], owner=_owner())
    assert len(list_favorites(favs, owner=_owner())) == 2, "回滚后两条都还在"


def test_batch_remove_succeeds_when_all_present() -> None:
    favs = FavoriteStore()
    _seed(favs, ["f-1", "f-2"])
    removed = batch_remove_favorites(favs, favorite_ids=["f-1", "f-2"], owner=_owner())
    assert sorted(removed) == ["f-1", "f-2"]
    assert list_favorites(favs, owner=_owner()) == []
