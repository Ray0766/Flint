"""GRAPH-14 验收：多工作台数据层 + archived（UI 单台，交互待 K6）。

acceptance（tasks-v04.json#GRAPH-14）：
  多台 CRUD 与 archived 生效；**多台 UI 入口 flag off** 断言。

## 数据层先行、UI 后到，是为了不把交互稿的空缺填成猜测

K6 未决：多工作台的交互设计还没出。数据层可以先做——多台的存储、归档、
按 owner 列举都是确定的；但**入口 flag 必须是 off**：
打开一个没有交互稿的入口，用户会遇到一半能用一半不能用的界面，
而那比「暂时只有一台」糟得多。

## archived 不是 delete

`WorkbenchGraph.archived`（SCHEMA-08 定的）默认 False。归档的台**仍然存在**、
仍可翻回；列举默认不含归档台，但显式要时能拿到。数据删除是 owner 人审节点，
v0.4 内不存在这条路径。
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

from flint.graph.multi import (
    MULTI_WORKBENCH_FLAG,
    WorkbenchStore,
    archive_workbench,
    create_workbench,
    list_workbenches,
    multi_workbench_ui_enabled,
    unarchive_workbench,
)


def _owner(uid: str = "u1") -> object:
    return M.Principal(kind="user", id=uid)


def _create(store: WorkbenchStore, graph_id: str, owner_id: str = "u1") -> object:
    return create_workbench(
        store, graph_id=graph_id, project_id="proj-1", owner=_owner(owner_id),
        title=f"台-{graph_id}", now=NOW, model=M.WorkbenchGraph)


# ── 多台 CRUD ───────────────────────────────────────────────────

def test_multiple_workbenches_coexist() -> None:
    store = WorkbenchStore()
    _create(store, "g1")
    _create(store, "g2")
    assert {w.graph_id for w in list_workbenches(store, owner=_owner())} == {"g1", "g2"}


def test_create_is_idempotent_on_graph_id() -> None:
    store = WorkbenchStore()
    first = _create(store, "g1")
    again = _create(store, "g1")
    assert again.graph_id == first.graph_id
    assert len(list_workbenches(store, owner=_owner())) == 1


def test_list_is_scoped_to_owner() -> None:
    store = WorkbenchStore()
    _create(store, "g1", owner_id="u1")
    _create(store, "g2", owner_id="u2")
    assert [w.graph_id for w in list_workbenches(store, owner=_owner("u1"))] == ["g1"]


# ── archived 生效 ───────────────────────────────────────────────

def test_archive_hides_from_default_listing() -> None:
    store = WorkbenchStore()
    _create(store, "g1")
    _create(store, "g2")
    assert archive_workbench(store, graph_id="g2") is True
    assert [w.graph_id for w in list_workbenches(store, owner=_owner())] == ["g1"]


def test_archived_workbench_still_exists() -> None:
    """归档不是删除：显式要时仍能拿到，内容一字不少。"""
    store = WorkbenchStore()
    _create(store, "g1")
    archive_workbench(store, graph_id="g1")
    got = list_workbenches(store, owner=_owner(), include_archived=True)
    assert [w.graph_id for w in got] == ["g1"]
    assert got[0].archived is True
    assert got[0].title == "台-g1"


def test_unarchive_brings_it_back() -> None:
    store = WorkbenchStore()
    _create(store, "g1")
    archive_workbench(store, graph_id="g1")
    assert unarchive_workbench(store, graph_id="g1") is True
    assert [w.graph_id for w in list_workbenches(store, owner=_owner())] == ["g1"]


def test_archive_is_idempotent_and_never_raises_on_missing() -> None:
    store = WorkbenchStore()
    _create(store, "g1")
    assert archive_workbench(store, graph_id="g1") is True
    assert archive_workbench(store, graph_id="g1") is True, "已归档再归档仍是归档态"
    assert archive_workbench(store, graph_id="g404") is False, "不存在的台返回 False 而非抛错"


def test_no_delete_path_exists() -> None:
    """数据删除是 owner 人审节点——v0.4 内 NEVER 有这条路径。"""
    import flint.graph.multi as module

    exported = {n for n in dir(module) if not n.startswith("_")}
    for forbidden in ("delete_workbench", "drop_workbench", "purge_workbench"):
        assert forbidden not in exported, f"出现删除入口：{forbidden}"


# ── 多台 UI 入口 flag off（K6 未决） ────────────────────────────

def test_multi_workbench_ui_flag_is_off_by_default() -> None:
    """K6 交互稿未出 → 入口必须关着。"""
    assert multi_workbench_ui_enabled({}) is False


def test_flag_name_follows_e8_convention() -> None:
    assert MULTI_WORKBENCH_FLAG == "multi_workbench_ui_enabled"


def test_flag_can_be_turned_on_explicitly_when_k6_lands() -> None:
    """开关本身是通的——K6 落地后打开即可，不必改代码。"""
    assert multi_workbench_ui_enabled({MULTI_WORKBENCH_FLAG: True}) is True


def test_data_layer_works_regardless_of_the_ui_flag() -> None:
    """数据层先行：flag 关着不影响多台存储本身。"""
    store = WorkbenchStore()
    _create(store, "g1")
    _create(store, "g2")
    assert multi_workbench_ui_enabled({}) is False
    assert len(list_workbenches(store, owner=_owner())) == 2


def test_flag_default_is_not_read_from_a_mutable_global() -> None:
    """默认关不能靠「调用方记得传空 dict」——不传也得是关的。"""
    import inspect

    sig = inspect.signature(multi_workbench_ui_enabled)
    param = sig.parameters["flags"]
    assert param.default in (inspect.Parameter.empty, None) or param.default == {}
    with pytest.raises(TypeError):
        multi_workbench_ui_enabled()          # type: ignore[call-arg]
