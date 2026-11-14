"""GRAPH-06 验收（后端半）：并发双写下「图内主唯一」仍成立（I12-1）。

acceptance（tasks-v04.json#GRAPH-06）第二条：**服务端并发双写下 primary ≤1 仍成立**。

## 规则成立 ≠ 并发下成立

契约里的 `set_primary` 在一个列表上当然是对的。但两个写入方各自
「读全图 → 改自己那一个 → 写回」时，两次都会成功，图里于是有两个 primary——
UI 只显示其中一个是主，另一个悄悄也是主，「这张图在讲哪件事」就没有答案了。

所以这一半测的不是规则，是**临界区**。并发测试最容易变成摆设（线程太少、
跑得太快、恰好没撞上），故这里配一个**反例探针**：同样的并发压力打在不加锁的
写法上必须让断言变红——一把见谁都放行的尺子量不出任何东西。
"""
from __future__ import annotations

import importlib.util
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.graph.roles import (
    RoleChange,
    naive_set_primary_unsafe,
    primary_count,
    set_node_role,
)
from flint.graph.store import GraphStore, add_node

GRAPH = "wb-1"
NODE_IDS = [f"n-{i}" for i in range(8)]


def _store() -> GraphStore:
    store = GraphStore()
    for nid in NODE_IDS:
        add_node(
            store, graph_id=GRAPH, node_id=nid, source_kind="cluster",
            source_id=f"c-{nid}", label=nid, position=(0.0, 0.0), now=NOW,
            model=M.GraphNode,
        )
    return store


def _hammer(fn: Any, ids: list[str], rounds: int = 40) -> None:
    """多线程反复写：每个线程把自己那一个节点设主，来回轰。"""
    barrier = threading.Barrier(len(ids))

    def worker(nid: str) -> None:
        # 所有线程在同一屏障上对齐后同时开跑：不对齐的话它们会前后脚各跑各的，
        # 写入根本撞不上，这个测试就退化成串行调用了。
        barrier.wait()
        for _ in range(rounds):
            fn(nid)

    threads = [threading.Thread(target=worker, args=(nid,)) for nid in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def test_primary_stays_unique_under_concurrent_writes() -> None:
    store = _store()

    _hammer(
        lambda nid: set_node_role(store, graph_id=GRAPH, node_id=nid, role="primary"),
        NODE_IDS,
    )

    assert primary_count(store, graph_id=GRAPH) == 1


def test_the_concurrency_check_can_actually_fail() -> None:
    """反例探针：同样的压力打在不加锁的写法上必须破功。

    否则上一条的绿可能只是因为线程没撞上——那种绿什么都没证明。
    """
    store = _store()

    _hammer(
        lambda nid: naive_set_primary_unsafe(store, graph_id=GRAPH, node_id=nid),
        NODE_IDS,
    )

    assert primary_count(store, graph_id=GRAPH) > 1


def test_setting_a_second_primary_demotes_the_first_and_says_so() -> None:
    """旧主自动降级，并**如实报出**被降的是谁（UI 据此出 toast）。"""
    store = _store()
    first = set_node_role(store, graph_id=GRAPH, node_id="n-0", role="primary")
    second = set_node_role(store, graph_id=GRAPH, node_id="n-1", role="primary")

    assert first == RoleChange(node_id="n-0", role="primary", demoted_node_id=None)
    assert second.demoted_node_id == "n-0"
    assert primary_count(store, graph_id=GRAPH) == 1
    assert [n.node_id for n in store.nodes(GRAPH) if n.primary] == ["n-1"]


def test_resetting_the_same_node_reports_no_demotion() -> None:
    """对着当前主再设一次主：没有谁被降级，NEVER 报一个自己降了自己的 toast。"""
    store = _store()
    set_node_role(store, graph_id=GRAPH, node_id="n-0", role="primary")
    again = set_node_role(store, graph_id=GRAPH, node_id="n-0", role="primary")

    assert again.demoted_node_id is None
    assert primary_count(store, graph_id=GRAPH) == 1


def test_demoting_the_primary_leaves_the_graph_without_one() -> None:
    """主可以被降成 secondary：图可以没有主（NEVER 自动挑一个顶上）。

    自动顶上等于系统替用户决定「这张图在讲哪件事」，而那正是他要自己回答的问题。
    """
    store = _store()
    set_node_role(store, graph_id=GRAPH, node_id="n-0", role="primary")
    change = set_node_role(store, graph_id=GRAPH, node_id="n-0", role="secondary")

    assert change.demoted_node_id is None
    assert primary_count(store, graph_id=GRAPH) == 0


def test_unknown_node_and_unknown_role_are_rejected() -> None:
    store = _store()
    with pytest.raises(KeyError):
        set_node_role(store, graph_id=GRAPH, node_id="n-404", role="primary")
    with pytest.raises(ValueError):
        set_node_role(store, graph_id=GRAPH, node_id="n-0", role="main")  # type: ignore[arg-type]


def test_roles_module_never_reimplements_the_contract_rule() -> None:
    """角色集与「旧主自动降」的语义源出契约（SCHEMA-12 已验），本模块只加运行时。"""
    from typing import get_args

    from flint.graph.roles import NodeRole

    assert set(get_args(NodeRole)) == {"primary", "secondary", "auxiliary"}
    assert hasattr(M, "set_primary")  # 契约里的规则函数仍在，未被本模块取代
