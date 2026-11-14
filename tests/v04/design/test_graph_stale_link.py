"""DESIGN-25 验收：图谱变更 → 样板 stale（H1 第三个薄适配器；G33 不自动重跑）。

acceptance：
① **graph_stale_notice 触发标黄；自动重跑路径不存在（断言）**；
② **「查看差异/重新生成」两动作可用**。

## 为什么 NEVER 自动重跑

用户在图谱上挪了一个节点、加了一条边，样板就自己重新生成一遍——他刚调好的
版式、刚手改过的那句话，全没了。而他并没有要求重做，他只是在整理关系。

「变了」与「要不要重做」是两个问题，第二个只有用户能回答。所以这一层只**标黄**
（提示它可能过时）+ 给两条出路（看差异 / 主动重新生成），一次生成都不发起。

## 为什么复用 H1 而不是自己判「旧不旧」

`Revalidator` 的统一口径已经定义了「什么算陈旧」。设计台另写一套，
就会出现同一份产物在图谱页说陈旧、在文档页说最新——两处各有一半的道理，
而用户不知道该信哪个。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
SRC = REPO_ROOT / "flint" / "design" / "graph_stale.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)

from flint.design.graph_stale import (
    STALE_ACTIONS,
    GraphStaleNotice,
    notices_for_change,
)
from tests.v04._source_scan import code_names

LINKS = {"g-1": ["d-1", "d-2"], "g-2": ["d-9"]}


def _change(kind: str, graph_id: str = "g-1") -> Any:
    return M.GraphChange(kind=kind, graph_id=graph_id, occurred_at=NOW)


# ───────────────────────── 结构性变更 → 标黄


def test_structural_change_marks_linked_deliverables() -> None:
    notices = notices_for_change(_change("edge_added"), LINKS)

    assert [n.deliverable_id for n in notices] == ["d-1", "d-2"]
    assert all(n.stale for n in notices)
    assert all(n.graph_id == "g-1" for n in notices)


def test_non_structural_change_marks_nothing() -> None:
    """挪个位置不算内容变了：那样的话用户每拖一次节点就得看一次黄条。"""
    assert notices_for_change(_change("node_moved"), LINKS) == []


def test_change_on_another_graph_does_not_touch_us() -> None:
    notices = notices_for_change(_change("node_added", graph_id="g-2"), LINKS)

    assert [n.deliverable_id for n in notices] == ["d-9"]


def test_unlinked_graph_yields_no_notice() -> None:
    assert notices_for_change(_change("edge_added", graph_id="g-404"), LINKS) == []


def test_derivation_reuses_the_contract_rule() -> None:
    """派生规则来自契约 `derive_stale`（I12-3），本模块不另写一套「什么算结构性」。"""
    names = code_names(SRC)

    assert "derive_stale" in names
    assert "models_v04" in names or "contracts_v04.models_v04" in names


# ───────────────────────── 两个动作 + 不自动重跑


def test_notice_offers_exactly_two_actions() -> None:
    notices = notices_for_change(_change("edge_added"), LINKS)

    assert [a for a in STALE_ACTIONS] == ["view_diff", "regenerate"]
    assert notices[0].actions == ("view_diff", "regenerate")


def test_regenerate_is_an_action_not_an_effect() -> None:
    """「重新生成」是**用户点的一个动作**，不是这一层的副作用。"""
    notices = notices_for_change(_change("edge_added"), LINKS)

    assert "regenerate" in notices[0].actions
    # 通知对象里没有任何「已经发起」的痕迹
    assert not hasattr(notices[0], "job_id")
    assert not hasattr(notices[0], "triggered")


def test_module_never_submits_a_job() -> None:
    """自动重跑路径**不存在**：本模块不 import runner、不构造 payload、不入队。

    用户在图谱上挪了个节点，样板就自己重生成一遍——他刚调好的版式、刚手改过的
    那句话全没了，而他并没有要求重做。
    """
    names = code_names(SRC)

    for forbidden in (
        "JobRunner", "submit", "submit_deep_analysis", "enqueue", "arq", "asyncpg",
    ):
        assert forbidden not in names


def test_notice_is_data_not_an_action_object() -> None:
    """通知是**数据**：谁去执行动作由上层决定，这一层不持有回调。"""
    notices = notices_for_change(_change("edge_added"), LINKS)

    assert isinstance(notices[0], GraphStaleNotice)
    for field in ("on_regenerate", "callback", "handler"):
        assert not hasattr(notices[0], field)


def test_same_change_twice_is_idempotent() -> None:
    """同一次变更算两遍，结果一样：通知不该越积越多。"""
    first = notices_for_change(_change("edge_added"), LINKS)
    second = notices_for_change(_change("edge_added"), LINKS)

    assert first == second


def test_unknown_change_kind_is_rejected() -> None:
    """未知变更类型报错，NEVER 当成「不算结构性」悄悄放过。

    放过的话，新增一种真会影响内容的变更时，样板不会标黄而用户以为它是最新的。
    """
    with pytest.raises(ValueError):
        notices_for_change(_change("teleported"), LINKS)
