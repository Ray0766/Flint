"""GRAPH-14：多工作台数据层 + archived（UI 单台，交互待 K6）。

## 数据层先行、UI 后到

K6 未决: 多工作台的交互设计还没出。数据层可以先做——多台的存储、归档、
按 owner 列举都是确定的; 但**入口 flag 必须是 off**:
打开一个没有交互稿的入口, 用户会遇到一半能用一半不能用的界面,
那比「暂时只有一台」糟得多。K6 落地后把 flag 打开即可, 不必改代码。

## archived 不是 delete

`WorkbenchGraph.archived`（SCHEMA-08 定的）默认 False。归档的台**仍然存在**、
仍可翻回; 列举默认不含归档台, 显式要时能拿到。
数据删除是 owner 人审节点, v0.4 内 NEVER 有这条路径（测试守着导出面）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

# E8 flag 命名口径: {功能}_enabled
MULTI_WORKBENCH_FLAG = "multi_workbench_ui_enabled"


def multi_workbench_ui_enabled(flags: dict[str, bool]) -> bool:
    """多台 UI 入口是否开启。**默认关**（K6 交互稿未出）。

    `flags` 是必填参数: 默认关不能靠「调用方记得传空 dict」——
    不传就该是个错误, 而不是悄悄取到某个可变全局的当前值。
    """
    return bool(flags.get(MULTI_WORKBENCH_FLAG, False))


@dataclass
class WorkbenchStore:
    """内存实现；SQL 实现随 E2 的 `workbench_graphs` 表接入。"""

    _rows: dict[str, Any] = field(default_factory=dict)

    def get(self, graph_id: str) -> Any:
        return self._rows.get(graph_id)

    def put(self, graph: Any) -> None:
        self._rows[graph.graph_id] = graph

    def all(self) -> list[Any]:
        return list(self._rows.values())


def create_workbench(
    store: WorkbenchStore, *, graph_id: str, project_id: str, owner: Any,
    title: str, now: datetime, model: Any,
) -> Any:
    """建台。同 graph_id 幂等。"""
    existing = store.get(graph_id)
    if existing is not None:
        return existing
    graph = model(
        graph_id=graph_id, project_id=project_id, owner=owner, title=title,
        created_at=now, updated_at=now)
    store.put(graph)
    return graph


def list_workbenches(
    store: WorkbenchStore, *, owner: Any, include_archived: bool = False
) -> list[Any]:
    """我的台。默认**不含归档**；显式要时才给。"""
    mine = [
        g for g in store.all()
        if g.owner.kind == owner.kind and g.owner.id == owner.id
    ]
    if not include_archived:
        mine = [g for g in mine if not g.archived]
    return sorted(mine, key=lambda g: g.graph_id)


def archive_workbench(store: WorkbenchStore, *, graph_id: str) -> bool:
    """归档。幂等；台不存在时返回 False 而 NEVER 抛错。"""
    graph = store.get(graph_id)
    if graph is None:
        return False
    store.put(replace(graph, archived=True))
    return True


def unarchive_workbench(store: WorkbenchStore, *, graph_id: str) -> bool:
    """取消归档——归档不是删除，翻得回来。"""
    graph = store.get(graph_id)
    if graph is None:
        return False
    store.put(replace(graph, archived=False))
    return True
