"""FAV-02 验收：snapshot_stale 打标 + 双动作（查看当时版本 / 更新到最新）。

acceptance（tasks-v04.json#FAV-02）：
① stale 判定复用 §6-H1 适配器（import 断言）；
② refresh 生成新快照且**旧值保留历史**。

## 「更新到最新」不能是覆盖

两个动作是一对：**查看当时版本** 与 **更新到最新**。若 refresh 直接覆盖，
第一个动作就没有数据可看了——用户点「更新到最新」时并不知道自己按下的是
一次不可撤销的擦除。所以旧值进历史，且历史保留**每一次**旧值而不只是上一次。

## stale 只能由统一口径置 True

冻结件 `Favorite` 的 docstring 写死：`snapshot_stale` 只能由 Revalidator 通道置 True，
前端 NEVER 自行按时间戳推断新鲜度。按时间戳推断的坏处是它**看起来总是对的**：
一份三个月前的收藏「显然」旧了，可事实一个字没变时，那个标记只会让用户白重跑一次；
反过来，昨天的收藏也可能因为一次事实移除而彻底失效。新旧只有账本说了算。
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
V04 = REPO_ROOT / "contracts_v04" / "models_v04.py"
STALE_SRC = REPO_ROOT / "flint" / "fav" / "stale.py"


def _models() -> Any:
    spec = importlib.util.spec_from_file_location("models_v04", V04)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04"] = module
    spec.loader.exec_module(module)
    return module


M = _models()
NOW = datetime(2026, 8, 3, tzinfo=UTC)
LATER = datetime(2026, 8, 4, tzinfo=UTC)

from flint.domain.models import FactDiff
from flint.fav.stale import (
    SnapshotHistoryStore,
    StaleNotEvaluated,
    evaluate_snapshot_stale,
    original_snapshot,
    refresh_snapshot,
)
from flint.fav.store import FavoriteStore, add_favorite

SNAPSHOT_V1 = {
    "cluster_id": "c-1",
    "ledger_version": 7,
    "fact_ids": ["f-1", "f-2"],
    "cards": [{"card_id": "card-1", "links": ["http://a"]}],
}
SNAPSHOT_V2 = {
    "cluster_id": "c-1",
    "ledger_version": 9,
    "fact_ids": ["f-1", "f-3"],
    "cards": [{"card_id": "card-1", "links": ["http://a", "http://b"]}],
}


def _owner(uid: str = "u1") -> Any:
    return M.Principal(kind="user", id=uid)


def _seed(snapshot: dict[str, Any] | None = None) -> FavoriteStore:
    store = FavoriteStore()
    add_favorite(
        store, favorite_id="fav-1", owner=_owner(), target_kind="cluster",
        target_id="c-1", evidence_snapshot=snapshot or SNAPSHOT_V1,
        now=NOW, model=M.Favorite,
    )
    return store


# ───────────────────────── acceptance ① stale 判定复用 H1 适配器


def test_stale_module_imports_the_h1_adapter() -> None:
    """import 断言：判定来自 HOTSPOT-06 的适配器，而它 import 自 contracts 通道。"""
    tree = ast.parse(STALE_SRC.read_text(encoding="utf-8"))
    sources = {
        n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "flint.analysis.stale_adapter" in sources


def test_stale_module_never_infers_freshness_from_time() -> None:
    """本模块 NEVER 按时间戳推断新鲜度（冻结件 Favorite docstring 写死）。

    时间戳推断看起来总是对的：三个月前的收藏「显然」旧了——可事实一个字没变时，
    那个标记只会让用户白重跑一次；而昨天的收藏也可能因一次事实移除而彻底失效。
    """
    source = STALE_SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    defined = [
        n.name for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    assert [n for n in defined if "diff" in n.lower()] == []
    for forbidden in ("timedelta", "days=", "utcnow", "time.time"):
        assert forbidden not in source, f"按时间戳推断新鲜度：{forbidden}"


def test_marks_stale_when_the_channel_says_a_cited_fact_moved() -> None:
    store = _seed()

    def diff_channel(project_id: str, v_from: int, v_to: int) -> FactDiff:
        assert (v_from, v_to) == (7, 9)          # 版本对来自快照，不是猜的
        return FactDiff(changed=[], removed=["f-2"], disputed=[])

    row = evaluate_snapshot_stale(
        store, favorite_id="fav-1", owner=_owner(), project_id="p-1",
        current_version=9, diff_channel=diff_channel,
    )

    assert row.snapshot_stale is True
    assert store.get("fav-1").snapshot_stale is True   # 落库了，不只是返回值


def test_unrelated_change_leaves_the_favorite_fresh() -> None:
    """账本前进但这份收藏引用的事实没动 → 不标陈旧（零污染）。"""
    store = _seed()

    def diff_channel(project_id: str, v_from: int, v_to: int) -> FactDiff:
        return FactDiff(changed=["f-99"], removed=[], disputed=[])

    row = evaluate_snapshot_stale(
        store, favorite_id="fav-1", owner=_owner(), project_id="p-1",
        current_version=9, diff_channel=diff_channel,
    )

    assert row.snapshot_stale is False


def test_snapshot_without_ledger_version_is_not_guessed() -> None:
    """快照没记账本版本 → 报错，NEVER 猜一个、更 NEVER 悄悄标成不陈旧。

    悄悄放过的话，界面会告诉用户「这份收藏是最新的」——而我们根本没能力知道。
    """
    store = _seed({"cluster_id": "c-1", "fact_ids": ["f-1"]})

    def unused(project_id: str, v_from: int, v_to: int) -> FactDiff:
        raise AssertionError("NEVER 该被调到")

    with pytest.raises(StaleNotEvaluated):
        evaluate_snapshot_stale(
            store, favorite_id="fav-1", owner=_owner(), project_id="p-1",
            current_version=9, diff_channel=unused,
        )
    assert store.get("fav-1").snapshot_stale is False   # 状态保持原样


def test_evaluate_rejects_another_owners_favorite() -> None:
    """越权 NEVER 静默跳过（沿用 FAV-05 的 _owned 口径）。"""
    store = _seed()

    def unused(project_id: str, v_from: int, v_to: int) -> FactDiff:
        raise AssertionError("NEVER 该被调到")

    with pytest.raises(PermissionError):
        evaluate_snapshot_stale(
            store, favorite_id="fav-1", owner=_owner("u2"), project_id="p-1",
            current_version=9, diff_channel=unused,
        )


# ───────────────────────── acceptance ② refresh 生成新快照且旧值保留历史


def test_refresh_replaces_snapshot_and_keeps_the_old_one() -> None:
    store, history = _seed(), SnapshotHistoryStore()

    row = refresh_snapshot(
        store, history, favorite_id="fav-1", owner=_owner(),
        fresh_snapshot=SNAPSHOT_V2, now=LATER,
    )

    assert row.evidence_snapshot == SNAPSHOT_V2
    entries = history.entries("fav-1")
    assert len(entries) == 1
    assert entries[0].snapshot == SNAPSHOT_V1        # 旧值逐字保留
    assert entries[0].replaced_at == LATER


def test_history_keeps_every_old_value_in_order() -> None:
    """保留的是**每一次**旧值，不只是上一次——否则「查看当时版本」只能回到昨天。"""
    store, history = _seed(), SnapshotHistoryStore()
    mid = {"cluster_id": "c-1", "ledger_version": 8, "fact_ids": ["f-1"]}

    refresh_snapshot(store, history, favorite_id="fav-1", owner=_owner(),
                     fresh_snapshot=mid, now=NOW)
    refresh_snapshot(store, history, favorite_id="fav-1", owner=_owner(),
                     fresh_snapshot=SNAPSHOT_V2, now=LATER)

    entries = history.entries("fav-1")
    assert [e.snapshot for e in entries] == [SNAPSHOT_V1, mid]
    assert original_snapshot(store, history, favorite_id="fav-1") == SNAPSHOT_V1


def test_original_snapshot_before_any_refresh_is_the_current_one() -> None:
    """没刷新过时，「当时版本」就是现在这份——不是空。"""
    store, history = _seed(), SnapshotHistoryStore()
    assert original_snapshot(store, history, favorite_id="fav-1") == SNAPSHOT_V1


def test_refresh_clears_the_stale_mark() -> None:
    store, history = _seed(), SnapshotHistoryStore()

    def diff_channel(project_id: str, v_from: int, v_to: int) -> FactDiff:
        return FactDiff(changed=[], removed=["f-2"], disputed=[])

    evaluate_snapshot_stale(store, favorite_id="fav-1", owner=_owner(),
                            project_id="p-1", current_version=9,
                            diff_channel=diff_channel)
    assert store.get("fav-1").snapshot_stale is True

    row = refresh_snapshot(store, history, favorite_id="fav-1", owner=_owner(),
                           fresh_snapshot=SNAPSHOT_V2, now=LATER)

    assert row.snapshot_stale is False


def test_history_entries_are_copies() -> None:
    """历史是副本：改返回值 NEVER 改到库里那份（与 FAV-01 的深拷贝口径同源）。"""
    store, history = _seed(), SnapshotHistoryStore()
    refresh_snapshot(store, history, favorite_id="fav-1", owner=_owner(),
                     fresh_snapshot=SNAPSHOT_V2, now=LATER)

    stolen = history.entries("fav-1")[0].snapshot
    stolen["cards"][0]["links"].append("http://tampered")

    assert history.entries("fav-1")[0].snapshot == SNAPSHOT_V1


def test_identical_refresh_records_no_history() -> None:
    """内容没变的刷新不产生历史条目：没有旧值可留，历史里多一条只会误导。"""
    store, history = _seed(), SnapshotHistoryStore()

    refresh_snapshot(store, history, favorite_id="fav-1", owner=_owner(),
                     fresh_snapshot=dict(SNAPSHOT_V1), now=LATER)

    assert history.entries("fav-1") == []


def test_refresh_rejects_empty_snapshot() -> None:
    """空快照拒绝（FAV-01 同款理由：内嵌基线的意义就是不让收藏变成空壳）。"""
    store, history = _seed(), SnapshotHistoryStore()
    with pytest.raises(ValueError):
        refresh_snapshot(store, history, favorite_id="fav-1", owner=_owner(),
                         fresh_snapshot={}, now=LATER)


def test_refresh_rejects_another_owners_favorite() -> None:
    store, history = _seed(), SnapshotHistoryStore()
    with pytest.raises(PermissionError):
        refresh_snapshot(store, history, favorite_id="fav-1", owner=_owner("u2"),
                         fresh_snapshot=SNAPSHOT_V2, now=LATER)
    assert store.get("fav-1").evidence_snapshot == SNAPSHOT_V1


def test_refresh_unknown_favorite_raises() -> None:
    store, history = FavoriteStore(), SnapshotHistoryStore()
    with pytest.raises(KeyError):
        refresh_snapshot(store, history, favorite_id="nope", owner=_owner(),
                         fresh_snapshot=SNAPSHOT_V2, now=LATER)
