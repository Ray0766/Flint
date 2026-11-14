"""DESIGN-11 验收：版本历史检查点（模板 VFS + 图谱状态同快照；恢复=新检查点）。

acceptance：**检查点含 VFS+图谱状态双份；恢复产生新检查点且历史不可变**。

## 为什么两份要在同一个检查点里

设计产物（模板 VFS）与它所依据的图谱是**一起**才说得通的：同一份页面，
配上另一张图谱，讲的就是另一件事。分开存两条历史，恢复时就要回答
「用哪一版图谱配哪一版页面」——那个问题没有正确答案，只有猜。

## 为什么恢复要产生新检查点

「恢复到三步前」如果是把后面几步删掉，用户就再也回不到当前这一版了——
而他常常是恢复过去看一眼、再回来。历史**只增不改**：恢复 = 把旧内容抄成一个新点，
时间线上永远是往前走的。
"""
from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from flint.design.checkpoints import (
    CheckpointStore,
    HistoryImmutable,
    UnknownCheckpoint,
    create_checkpoint,
    list_checkpoints,
    restore_checkpoint,
)

NOW = datetime(2026, 8, 3, 10, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 11, 0, tzinfo=UTC)
LATEST = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

VFS_A = {"index.html": "<h1>燧石</h1>", "styles.css": ".a{--gap:12px}"}
VFS_B = {"index.html": "<h1>Flint</h1>", "styles.css": ".a{--gap:16px}"}
GRAPH_A = {
    "nodes": [{"node_id": "n-1", "primary": True}],
    "edges": [{"from_node_id": "n-1", "to_node_id": "n-2", "hypothesis": "共用供应链"}],
}
GRAPH_B = {"nodes": [{"node_id": "n-9", "primary": True}], "edges": []}


def _store() -> CheckpointStore:
    return CheckpointStore()


# ───────────────────────── 双份同快照


def test_checkpoint_carries_both_vfs_and_graph() -> None:
    store = _store()

    cp = create_checkpoint(
        store, session_id="s-1", vfs=VFS_A, graph=GRAPH_A, now=NOW, label="第一版"
    )

    assert cp.vfs == VFS_A
    assert cp.graph == GRAPH_A
    assert cp.created_at == NOW
    assert cp.label == "第一版"


def test_checkpoint_rejects_a_half_snapshot() -> None:
    """缺一半就不是检查点：只存页面不存图谱，恢复时就要猜配哪一版图谱。"""
    store = _store()

    with pytest.raises(ValueError):
        create_checkpoint(store, session_id="s-1", vfs=VFS_A, graph={}, now=NOW)
    with pytest.raises(ValueError):
        create_checkpoint(store, session_id="s-1", vfs={}, graph=GRAPH_A, now=NOW)


def test_snapshot_is_deep_copied_from_the_live_state() -> None:
    """快照与现场彻底断开：现场后来怎么改都不该动到已存的那一份。"""
    store = _store()
    live_vfs = copy.deepcopy(VFS_A)
    live_graph = copy.deepcopy(GRAPH_A)

    cp = create_checkpoint(
        store, session_id="s-1", vfs=live_vfs, graph=live_graph, now=NOW
    )
    live_vfs["index.html"] = "<h1>改过了</h1>"
    live_graph["nodes"].append({"node_id": "n-2", "primary": False})

    assert cp.vfs["index.html"] == "<h1>燧石</h1>"
    assert len(store.get(cp.checkpoint_id).graph["nodes"]) == 1


def test_reading_a_checkpoint_returns_a_copy() -> None:
    """读出去的是副本：调用方改返回值 NEVER 改到历史里那一份。"""
    store = _store()
    cp = create_checkpoint(store, session_id="s-1", vfs=VFS_A, graph=GRAPH_A, now=NOW)

    stolen = store.get(cp.checkpoint_id)
    stolen.vfs["index.html"] = "<h1>篡改</h1>"

    assert store.get(cp.checkpoint_id).vfs["index.html"] == "<h1>燧石</h1>"


# ───────────────────────── 恢复 = 新检查点，历史不可变


def test_restore_appends_a_new_checkpoint_and_keeps_the_old_ones() -> None:
    store = _store()
    first = create_checkpoint(store, session_id="s-1", vfs=VFS_A, graph=GRAPH_A, now=NOW)
    second = create_checkpoint(
        store, session_id="s-1", vfs=VFS_B, graph=GRAPH_B, now=LATER
    )

    restored = restore_checkpoint(store, checkpoint_id=first.checkpoint_id, now=LATEST)

    history = list_checkpoints(store, session_id="s-1")
    assert [c.checkpoint_id for c in history] == [
        first.checkpoint_id, second.checkpoint_id, restored.checkpoint_id,
    ]
    # 恢复出来的那一版内容等于被恢复的那一版，但**是新的一个点**
    assert restored.vfs == first.vfs
    assert restored.graph == first.graph
    assert restored.checkpoint_id != first.checkpoint_id
    assert restored.created_at == LATEST
    assert restored.restored_from == first.checkpoint_id


def test_restore_never_deletes_or_rewrites_history() -> None:
    """恢复到三步前 NEVER 把后面几步删掉：用户常常是回去看一眼、再回来。"""
    store = _store()
    first = create_checkpoint(store, session_id="s-1", vfs=VFS_A, graph=GRAPH_A, now=NOW)
    second = create_checkpoint(
        store, session_id="s-1", vfs=VFS_B, graph=GRAPH_B, now=LATER
    )

    restore_checkpoint(store, checkpoint_id=first.checkpoint_id, now=LATEST)

    assert store.get(second.checkpoint_id).vfs == VFS_B      # 后面那一版还在
    assert store.get(first.checkpoint_id).created_at == NOW  # 旧点的时间没被改写


def test_history_is_append_only_at_the_store_level() -> None:
    """存储层拒绝改写已存在的检查点：不留「更新一下历史」这个口子。"""
    store = _store()
    cp = create_checkpoint(store, session_id="s-1", vfs=VFS_A, graph=GRAPH_A, now=NOW)

    with pytest.raises(HistoryImmutable):
        store.put(cp)                    # 同 id 二次写入即拒绝


def test_restore_unknown_checkpoint_raises() -> None:
    with pytest.raises(UnknownCheckpoint):
        restore_checkpoint(_store(), checkpoint_id="cp-404", now=NOW)


def test_history_is_scoped_per_session() -> None:
    """别的会话的检查点 NEVER 出现在这条时间线上。"""
    store = _store()
    mine = create_checkpoint(store, session_id="s-1", vfs=VFS_A, graph=GRAPH_A, now=NOW)
    create_checkpoint(store, session_id="s-2", vfs=VFS_B, graph=GRAPH_B, now=LATER)

    history = list_checkpoints(store, session_id="s-1")

    assert [c.checkpoint_id for c in history] == [mine.checkpoint_id]


def test_history_is_ordered_by_time_then_creation() -> None:
    """时间线按时间序：同一时刻创建的按写入序，NEVER 每次读出来的顺序都不同。"""
    store = _store()
    a = create_checkpoint(store, session_id="s-1", vfs=VFS_A, graph=GRAPH_A, now=NOW)
    b = create_checkpoint(store, session_id="s-1", vfs=VFS_B, graph=GRAPH_B, now=NOW)

    ids = [c.checkpoint_id for c in list_checkpoints(store, session_id="s-1")]

    assert ids == [a.checkpoint_id, b.checkpoint_id]
    assert ids == [c.checkpoint_id for c in list_checkpoints(store, session_id="s-1")]


def test_module_never_reaches_into_the_graph_store() -> None:
    """检查点只存**图谱状态的快照**，不去改活的图谱（快照与现场是两件事）。

    断的是 AST 里的名字而不是源码字符串：本模块的 docstring 正写着
    「NEVER import GraphStore」，按字符串扫会把那句解释判成违规——
    Python 侧同一个坑的第二次（第一次是 GRAPH-07 后端），故抽了
    `tests/v04/_source_scan.py` 共用。
    """
    from pathlib import Path

    from tests.v04._source_scan import code_names

    src = Path(__file__).resolve().parents[3] / "flint" / "design" / "checkpoints.py"
    names = code_names(src)

    assert "GraphStore" not in names
    for forbidden in ("put_node", "put_edge", "add_node", "add_edge"):
        assert forbidden not in names
