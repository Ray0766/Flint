"""SCHEMA-08 验收：I8 图谱三实体（WorkbenchGraph / GraphNode / GraphEdge）。

acceptance（tasks-v04.json#SCHEMA-08）：
  有向图字段齐全；**source_kind 三值判别**；**archived 默认 False**。

## 节点引用什么，边承载什么

节点 `source_kind` 只有三值——`cluster` / `evidence_card` / `topic`：图谱里的节点是
**既有实体的投影**，不是新造的东西（§6-H8：source 引用既有实体 id 体系）。
「假设」不是节点而是**边**上的 `hypothesis`：假设描述的是两个东西之间的关系，
把它做成节点就会出现「一个没有两端的假设」，那正是 combo 通道要求 hypothesis 必填的原因。

## archived 而不是 delete

图是用户的思考过程。删掉就没了，归档还能翻回来——`archived` 默认 False，
删除路径在 v0.4 内不存在（数据删除是 owner 人审节点）。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

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
OWNER = None  # 延后到用例内构造，避免模块级依赖


def _graph(**kw: object) -> object:
    base: dict[str, object] = {
        "graph_id": "g1", "project_id": "proj-1",
        "owner": M.Principal(kind="user", id="u1"),
        "title": "固态电池 × 车规芯片", "created_at": NOW, "updated_at": NOW}
    base.update(kw)
    return M.WorkbenchGraph(**base)


def _node(node_id: str, source_kind: str = "cluster", source_id: str = "c1") -> object:
    return M.GraphNode(
        node_id=node_id, graph_id="g1", source_kind=source_kind, source_id=source_id,
        label="固态电池", position=(0.0, 0.0), created_at=NOW)


def test_source_kind_is_exactly_three_values() -> None:
    values = set(get_args(M.GraphSourceKind))
    assert values == {"cluster", "evidence_card", "topic"}, f"三值判别不符：{sorted(values)}"


def test_node_projects_an_existing_entity() -> None:
    """节点是既有实体的投影：source_kind + source_id 两者都在（§6-H8）。"""
    fields = set(M.GraphNode.__dataclass_fields__)
    assert {"node_id", "graph_id", "source_kind", "source_id", "label",
            "position", "created_at"} <= fields


def test_graph_is_directed() -> None:
    """有向：边区分 from / to，两个字段名不可互换。"""
    fields = set(M.GraphEdge.__dataclass_fields__)
    assert {"from_node_id", "to_node_id"} <= fields, f"边不是有向的：{sorted(fields)}"
    e = M.GraphEdge(
        edge_id="e1", graph_id="g1", from_node_id="n1", to_node_id="n2",
        hypothesis="固态电池良率提升会先落到车规芯片封装线", created_at=NOW)
    assert (e.from_node_id, e.to_node_id) == ("n1", "n2")


def test_archived_defaults_to_false() -> None:
    g = _graph()
    assert g.archived is False, "新建的图 MUST 不是归档态"


def test_archiving_is_the_only_removal_path() -> None:
    """图是用户的思考过程：归档可翻回，删除不在 v0.4 内（数据删除是 owner 人审节点）。"""
    g = _graph()
    g.archived = True
    assert g.archived is True
    assert not [f for f in M.WorkbenchGraph.__dataclass_fields__ if "delet" in f.lower()], (
        "WorkbenchGraph 不该有删除标记字段")


def test_edge_hypothesis_is_required_and_non_empty() -> None:
    """边假设复用 combo 的校验语义（§6-H8）：空假设 NEVER 成边。"""
    with pytest.raises(ValueError, match="hypothesis"):
        M.GraphEdge(
            edge_id="e2", graph_id="g1", from_node_id="n1", to_node_id="n2",
            hypothesis="   ", created_at=NOW)


def test_hypothesis_lives_on_edges_not_nodes() -> None:
    """假设描述的是两个东西之间的关系——做成节点就会出现「没有两端的假设」。"""
    assert "hypothesis" in M.GraphEdge.__dataclass_fields__
    assert "hypothesis" not in M.GraphNode.__dataclass_fields__
    assert "hypothesis" not in set(get_args(M.GraphSourceKind))
