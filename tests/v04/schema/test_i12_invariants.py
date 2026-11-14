"""SCHEMA-12 验收：I12 三条不变量（测试即规范）。

`WORKORDER-v04.md#4-I12` 规定了三个**函数名**，MUST 存在且通过：
  1. `test_primary_unique` —— 同一 graph 设第二个 primary 时前一个自动降 secondary，
     图内 primary 计数恒 ≤1（F6 存储层保证；UI toast 在 GRAPH-06）。
  2. `test_hypothesis_nonempty` —— 空串/全空白 hypothesis 的 GraphEdge 构造与持久化均被拒（F8）。
  3. `test_graph_change_derives_stale` —— 图谱节点/边变更 → 关联 Deliverable 派生 stale
     （纯函数层验证；运行时接线走 §6-H1，DESIGN-25 验）。

## 三条各自守什么

- **primary 唯一**：primary 是「这张图在讲哪件事」。两个 primary = 两个主语，
  下游拿它做标题/摘要时无从选择。**自动降级**而不是报错——用户点第二个节点设主，
  意思很明确，让他先去取消上一个是把系统的洁癖变成用户的负担。
- **假设非空**：一条没有假设的边说不出两端为什么被连起来（F8，与 combo 通道同语义）。
- **图变派生 stale**：图变了，基于它生成的产物就可能过时。
  但**移动节点位置不算**——画布上挪个位置没有改变任何论断，
  把布局变动也算成 stale 会让「陈旧」这个信号迅速失去意义。
"""
from __future__ import annotations

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


def _node(node_id: str, primary: bool = False) -> object:
    return M.GraphNode(
        node_id=node_id, graph_id="g1", source_kind="cluster", source_id=f"c-{node_id}",
        label=node_id, position=(0.0, 0.0), created_at=NOW, primary=primary)


def test_primary_unique() -> None:
    """I12-1：设第二个 primary → 前一个自动降 secondary，计数恒 ≤1。"""
    nodes = [_node("n1", primary=True), _node("n2"), _node("n3")]
    assert sum(n.primary for n in nodes) == 1

    M.set_primary(nodes, "n2")
    assert nodes[0].primary is False, "前一个 primary MUST 自动降级，而不是报错让用户自己取消"
    assert nodes[1].primary is True
    assert sum(n.primary for n in nodes) == 1, "图内 primary 计数恒 ≤1"

    # 再设一次同一个：幂等，仍然只有一个
    M.set_primary(nodes, "n2")
    assert sum(n.primary for n in nodes) == 1

    # 一张全无 primary 的图是合法的（还没定主语）
    blank = [_node("m1"), _node("m2")]
    assert sum(n.primary for n in blank) == 0

    with pytest.raises(ValueError, match="n404"):
        M.set_primary(nodes, "n404")


def test_hypothesis_nonempty() -> None:
    """I12-2：空串 / 全空白 hypothesis 的边，构造即被拒（F8）。"""
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(ValueError, match="hypothesis"):
            M.GraphEdge(
                edge_id="e1", graph_id="g1", from_node_id="n1", to_node_id="n2",
                hypothesis=bad, created_at=NOW)

    ok = M.GraphEdge(
        edge_id="e1", graph_id="g1", from_node_id="n1", to_node_id="n2",
        hypothesis="固态电池良率提升会先落到车规芯片封装线", created_at=NOW)
    assert ok.hypothesis


def test_graph_change_derives_stale() -> None:
    """I12-3：图的**结构**变更派生 stale；布局移动不派生（纯函数层）。"""
    links = {"g1": ["del-1", "del-2"], "g2": ["del-9"]}

    for structural in ("node_added", "node_removed", "edge_added", "edge_removed"):
        change = M.GraphChange(kind=structural, graph_id="g1", occurred_at=NOW)
        assert M.derive_stale(change, links) == {"del-1", "del-2"}, structural

    moved = M.GraphChange(kind="node_moved", graph_id="g1", occurred_at=NOW)
    assert M.derive_stale(moved, links) == set(), (
        "画布上挪个位置没有改变任何论断——把布局变动也算 stale，"
        "会让「陈旧」这个信号迅速失去意义")

    unknown_graph = M.GraphChange(kind="node_added", graph_id="g404", occurred_at=NOW)
    assert M.derive_stale(unknown_graph, links) == set(), "没有关联产物的图不派生任何 stale"


def test_stale_derivation_is_a_pure_function() -> None:
    """派生只算不改：入参 NEVER 被就地修改（运行时接线走 §6-H1，DESIGN-25 验）。"""
    links = {"g1": ["del-1"]}
    snapshot = {k: list(v) for k, v in links.items()}
    M.derive_stale(M.GraphChange(kind="edge_added", graph_id="g1", occurred_at=NOW), links)
    assert links == snapshot, "derive_stale MUST 是纯函数，不得就地修改入参"
