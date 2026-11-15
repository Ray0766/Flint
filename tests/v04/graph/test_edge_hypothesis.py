"""GRAPH-07 验收（后端半）：绕过前端直发空假设 → 422 EMPTY_HYPOTHESIS。

acceptance（tasks-v04.json#GRAPH-07）：
① 松手弹假设框；空值前端不发请求；**绕过前端直发 → 422 EMPTY_HYPOTHESIS**；
② 校验复用 §6-H8 函数（import 断言）。

## 为什么前端拦一次还不够

前端那一半只能保证「正常用界面的人不会建出空假设边」。curl 一发、或者哪天多一个
批量导入入口，空假设边就进库了——而一条没有假设的边说不出两端为什么被连起来，
它在画布上是一根线，在生成时是一条**没有理由的关联**，会被当成用户的判断写进文书。
所以服务端这一道是**独立的**一道，不是前端的回声。

## 校验只有一份

边上的假设与 combo 的关联假设是同一个东西（§6-H8）。两份实现就是两种口径，
用户会遇到「在 combo 里能提交、在图谱里被拒」这种事。故本层不写任何
`if not hypothesis.strip()`，而是让共享校验器抛，再把它的异常类型映射成 422。
"""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import sys
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
EDGE_API_SRC = REPO_ROOT / "flint" / "api" / "graph_edges.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.api.graph_edges import GraphEdgeDeps, create_graph_edge_app
from flint.api.schemas import ERROR_CODES
from flint.graph.store import GraphStore, add_node

GRAPH = "wb-1"


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def _seeded_store() -> GraphStore:
    store = GraphStore()
    for nid in ("n-1", "n-2"):
        add_node(
            store, graph_id=GRAPH, node_id=nid, source_kind="cluster",
            source_id=f"c-{nid}", label=nid, position=(0.0, 0.0), now=NOW,
            model=M.GraphNode,
        )
    return store


def _app(store: GraphStore) -> Any:
    return create_graph_edge_app(
        GraphEdgeDeps(store=store, now=lambda: NOW, edge_model=M.GraphEdge)
    )


async def _post(app: Any, body: dict[str, Any]) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.post(f"/workbenches/{GRAPH}/edges", json=body)


@pytest.mark.parametrize("hypothesis", ["", "   ", "\t\n"])
def test_empty_hypothesis_is_422_with_the_named_code(hypothesis: str) -> None:
    """空白也算空：一个只有空格的假设说明不了任何事，却能骗过「非空」这种粗筛。"""
    store = _seeded_store()

    response = run(_post(_app(store), {
        "edge_id": "e-1", "from_node_id": "n-1", "to_node_id": "n-2",
        "hypothesis": hypothesis,
    }))

    assert response.status_code == 422
    assert response.json()["code"] == "EMPTY_HYPOTHESIS"
    assert store.edges(GRAPH) == []          # 边一条都没进库


def test_missing_hypothesis_field_is_also_422() -> None:
    """字段干脆不给 → 同一条路：NEVER 当成「没填就算没有」放过去。"""
    store = _seeded_store()

    response = run(_post(_app(store), {
        "edge_id": "e-1", "from_node_id": "n-1", "to_node_id": "n-2",
    }))

    assert response.status_code == 422
    assert response.json()["code"] == "EMPTY_HYPOTHESIS"
    assert store.edges(GRAPH) == []


def test_valid_edge_is_created_once_and_is_idempotent() -> None:
    """阴性对照：正常的边确实建得出来（否则「空的建不出来」什么都没证明）。"""
    store = _seeded_store()
    app = _app(store)
    body = {
        "edge_id": "e-1", "from_node_id": "n-1", "to_node_id": "n-2",
        "hypothesis": "两者共用同一条供应链，上游停摆会同时影响",
    }

    first = run(_post(app, body))
    second = run(_post(app, {**body, "edge_id": "e-2"}))

    assert first.status_code == 201
    assert second.status_code == 201
    assert len(store.edges(GRAPH)) == 1      # 同 (from,to) 幂等（GRAPH-02 口径）
    assert store.edges(GRAPH)[0].hypothesis.startswith("两者共用")


def test_dangling_edge_is_rejected_with_a_different_code() -> None:
    """悬空边也拒，但**不是** EMPTY_HYPOTHESIS：两种错的修法完全不同。"""
    store = _seeded_store()

    response = run(_post(_app(store), {
        "edge_id": "e-1", "from_node_id": "n-1", "to_node_id": "n-404",
        "hypothesis": "有假设",
    }))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"
    assert store.edges(GRAPH) == []


def test_empty_hypothesis_code_is_registered() -> None:
    """错误码进注册表且是机器可读的 UPPER_SNAKE（沿用 M2-041 的口径）。"""
    assert "EMPTY_HYPOTHESIS" in ERROR_CODES
    for code in ERROR_CODES:
        assert code == code.upper() and " " not in code


# ───────────────────────── acceptance ② H8 复用断言


def test_api_layer_never_reimplements_the_hypothesis_check() -> None:
    """本层不写自己的非空判断：校验只有一份（§6-H8）。

    两份实现就是两种口径，用户会遇到「在 combo 里能提交、在图谱里被拒」这种事。

    断的是**代码**不是文字：模块 docstring 里正写着「本层不做那个非空判断」，
    按字符串扫会把这句解释判成违规（SCHEMA-09/REGION-05/I18N-06-b/FAV-04 同一个坑）。
    """
    tree = ast.parse(EDGE_API_SRC.read_text(encoding="utf-8"))
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "strip" not in attrs, "本层自己写了非空判断"
    assert "_require_str" not in (attrs | names)  # 连直接调都不必：走 add_edge 那条路
    imported = {
        n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "flint.graph.store" in imported


def test_the_shared_validator_is_what_rejects_it() -> None:
    """映射键的是**共享校验器的异常类型**，不是本层自己认的某种错。"""
    tree = ast.parse(EDGE_API_SRC.read_text(encoding="utf-8"))
    imported = {
        n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "flint.topic.create" in imported   # OriginValidationError 的出处


def test_store_still_routes_through_the_combo_validator() -> None:
    """H8 链条另一端：store 仍 import combo 的校验器（本卡未把它绕开）。"""
    store_src = (REPO_ROOT / "flint" / "graph" / "store.py").read_text(encoding="utf-8")
    assert "from flint.topic.create import _require_str" in store_src
