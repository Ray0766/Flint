"""GRAPH-02 验收：图谱数据层（有向图存储 + 入台 + H8 假设通道复用）。

acceptance（tasks-v04.json#GRAPH-02）：
  ① 同 source **二次入台幂等**返回既有节点；
  ② hypothesis 校验函数 **import 自 combo 通道模块**（H8 断言）。

## 幂等按什么判

按 `(graph_id, source_kind, source_id)` —— 「同一个热点被拖进同一张图两次」
应当回到**同一个节点**，而不是并排出现两个一模一样的卡片。
按 node_id 判是不够的：用户第二次拖入时不会带着上次的 node_id。
"""
from __future__ import annotations

import importlib.util
import inspect
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

from flint.graph import store as store_module
from flint.graph.store import (
    GraphStore,
    add_edge,
    add_node,
    neighbors,
)


def _store() -> GraphStore:
    return GraphStore()


def _node(store: GraphStore, source_id: str = "c-1", kind: str = "cluster",
          node_id: str = "n-auto") -> object:
    return add_node(
        store, graph_id="g1", node_id=node_id, source_kind=kind, source_id=source_id,
        label="固态电池", position=(0.0, 0.0), now=NOW, model=M.GraphNode)


# ── ① 入台幂等 ──────────────────────────────────────────────────

def test_second_admission_of_same_source_returns_existing_node() -> None:
    store = _store()
    first = _node(store, node_id="n-1")
    second = _node(store, node_id="n-2")          # 用户第二次拖入，不带上次的 node_id
    assert second.node_id == first.node_id, "同 source 二次入台 MUST 回到同一节点"
    assert len(store.nodes("g1")) == 1


def test_same_source_in_a_different_graph_is_a_new_node() -> None:
    """幂等的作用域是**一张图**——同一个热点当然可以出现在两张图里。"""
    store = _store()
    _node(store, node_id="n-1")
    other = add_node(
        store, graph_id="g2", node_id="n-2", source_kind="cluster", source_id="c-1",
        label="固态电池", position=(0.0, 0.0), now=NOW, model=M.GraphNode)
    assert other.node_id == "n-2"
    assert len(store.nodes("g1")) == 1 and len(store.nodes("g2")) == 1


def test_different_source_kind_is_a_different_node() -> None:
    """同 id 不同类（cluster c-1 vs topic c-1）不是同一个东西。"""
    store = _store()
    _node(store, source_id="x", kind="cluster", node_id="n-1")
    _node(store, source_id="x", kind="topic", node_id="n-2")
    assert len(store.nodes("g1")) == 2


# ── 有向边 ───────────────────────────────────────────────────────

def test_edge_is_directed() -> None:
    store = _store()
    _node(store, source_id="c-1", node_id="n-1")
    _node(store, source_id="c-2", node_id="n-2")
    add_edge(store, graph_id="g1", edge_id="e-1", from_node_id="n-1", to_node_id="n-2",
             hypothesis="固态电池良率提升会先落到车规芯片封装线", now=NOW, model=M.GraphEdge)
    assert neighbors(store, graph_id="g1", node_id="n-1") == ["n-2"]
    assert neighbors(store, graph_id="g1", node_id="n-2") == [], "方向不可逆"


def test_edge_requires_both_endpoints_to_exist() -> None:
    """悬空边 NEVER 入库：一条指向不存在节点的边，在画布上就是一根断线。"""
    store = _store()
    _node(store, source_id="c-1", node_id="n-1")
    with pytest.raises(ValueError, match="n-404"):
        add_edge(store, graph_id="g1", edge_id="e-1", from_node_id="n-1",
                 to_node_id="n-404", hypothesis="x 会影响 y", now=NOW, model=M.GraphEdge)


def test_edge_admission_is_idempotent_on_same_pair() -> None:
    store = _store()
    _node(store, source_id="c-1", node_id="n-1")
    _node(store, source_id="c-2", node_id="n-2")
    kw: dict[str, object] = {
        "graph_id": "g1", "from_node_id": "n-1", "to_node_id": "n-2",
        "hypothesis": "固态电池良率提升会先落到车规芯片封装线", "now": NOW,
        "model": M.GraphEdge}
    first = add_edge(store, edge_id="e-1", **kw)
    second = add_edge(store, edge_id="e-2", **kw)
    assert second.edge_id == first.edge_id
    assert len(store.edges("g1")) == 1


# ── ② H8：假设校验复用 combo 通道 ──────────────────────────────

def test_hypothesis_validator_is_imported_from_combo_channel() -> None:
    """H8：边假设复用 combo 的 hypothesis 校验语义，NEVER 新写一份。"""
    source = inspect.getsource(store_module)
    assert "from flint.topic.create import" in source, (
        "hypothesis 校验应 import 自 combo 通道模块（flint/topic/create.py）")


def test_empty_hypothesis_is_rejected_by_the_shared_validator() -> None:
    store = _store()
    _node(store, source_id="c-1", node_id="n-1")
    _node(store, source_id="c-2", node_id="n-2")
    for bad in ("", "   ", "\t"):
        with pytest.raises(ValueError, match="hypothesis"):
            add_edge(store, graph_id="g1", edge_id="e-x", from_node_id="n-1",
                     to_node_id="n-2", hypothesis=bad, now=NOW, model=M.GraphEdge)


def test_shared_validator_matches_combo_semantics() -> None:
    """同一个判据：combo 拒的空假设，图谱边也拒；combo 收的，图谱边也收。"""
    from flint.topic.create import OriginValidationError, _require_str

    with pytest.raises(OriginValidationError):
        _require_str({"hypothesis": "   "}, "hypothesis")
    assert _require_str({"hypothesis": "两个热点的交叉点"}, "hypothesis") == "两个热点的交叉点"
