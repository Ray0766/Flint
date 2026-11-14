"""BE-08 · 收藏端点族（暴露 `flint/fav` · v2 屏 2.15 收藏图书馆）。

`flint/fav/`（4 py）把写路径、pin、陈旧判定、批量都实现好了，但**零 API 出口**。
本卡暴露五个动作：列收藏 / 加收藏 / 取消收藏 / 看快照陈旧态 / 更新到最新。

判据里最要紧的四条，都是「既有函数**单独看是对的**，接成端点就会漏」：

1. `remove_favorite` **不判归属**——直接接成 DELETE，任何人都能删别人的收藏。
2. `add_favorite` 同 id 幂等且**直接返回既有那条**——直接接成 POST，
   拿别人的 favorite_id 一发就能读到别人的快照内容。
3. `evaluate_snapshot_stale` **会落库**——接成 GET 就是一个藏起来的写。
4. 取消收藏时顺手 unpin，会把**另一条收藏还在引用**的快照放回周删名单。

这四条都不是既有模块的错：它们各自的口径都写得很清楚。
漏在**接线处**——所以判据钉在端点上。
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, get_args, get_type_hints

from fastapi.testclient import TestClient

from flint.api.favorites import FavoritesApiDeps, create_favorites_app
from flint.fav.pin import SnapshotPins, expired_snapshot_ids
from flint.fav.stale import SnapshotHistoryStore
from flint.fav.store import FavoriteStore
from flint.ledger.diff import FactDiff

MODULE = Path("flint/api/favorites.py")

ME = "u-me"
OTHER = "u-other"
NOW = datetime(2026, 5, 6, 7, 8, tzinfo=UTC)


def _contract() -> Any:
    path = Path("contracts_v04/models_v04.py")
    spec = importlib.util.spec_from_file_location("models_v04_be08", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["models_v04_be08"] = module
    spec.loader.exec_module(module)
    return module


def _snapshot(version: int = 3, facts: tuple[str, ...] = ("f-1",),
              snapshot_id: str = "snap-1") -> dict[str, Any]:
    return {
        "ledger_version": version,
        "fact_ids": list(facts),
        "snapshot_id": snapshot_id,
        "body": {"nested": ["原文"]},
    }


class _Diff:
    """`DiffChannel` 是个**可调用对象**（`(project_id, since, until) -> FactDiff`），
    不是带 `.diff()` 方法的东西——照 `stale_adapter.analysis_stale` 的调用点写。"""

    def __init__(self, removed: tuple[str, ...] = ()) -> None:
        self._removed = removed

    def __call__(self, project_id: str, since: int, until: int) -> FactDiff:
        del project_id, since, until
        return FactDiff(changed=[], removed=list(self._removed), disputed=[])


def _app(
    *, removed: tuple[str, ...] = (),
) -> tuple[TestClient, FavoriteStore, SnapshotPins, SnapshotHistoryStore]:
    store, pins, history = FavoriteStore(), SnapshotPins(), SnapshotHistoryStore()
    deps = FavoritesApiDeps(
        store=store, pins=pins, history=history,
        diff_channel=_Diff(removed), now=lambda: NOW,
        project_id_for=lambda favorite: "p-1", current_version=lambda: 9,
    )
    return TestClient(create_favorites_app(deps)), store, pins, history


def _add(client: TestClient, favorite_id: str = "fav-1", user: str = ME,
         **overrides: Any) -> Any:
    body = {
        "favorite_id": favorite_id,
        "target_kind": "cluster",
        "target_id": "c-1",
        "evidence_snapshot": _snapshot(),
    }
    body.update(overrides)
    return client.post("/favorites", json=body, headers={"X-User-Id": user})


def _list(client: TestClient, user: str = ME) -> Any:
    return client.get("/favorites", headers={"X-User-Id": user})


# ───────────────────────── 一、列收藏（acceptance①④⑤）


def test_an_empty_library_is_an_empty_list_not_404() -> None:
    client, _, _, _ = _app()

    response = _list(client)

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_my_list_never_contains_another_owners_favorite() -> None:
    client, _, _, _ = _app()
    _add(client, "fav-mine", user=ME)
    _add(client, "fav-theirs", user=OTHER)

    assert [f["favorite_id"] for f in _list(client).json()["items"]] == ["fav-mine"]
    assert OTHER not in str(_list(client).json())


def test_listing_never_writes() -> None:
    """只读端点 NEVER 写库（阴性对照：读一次，库与 pin 都不许变）。"""
    client, store, pins, _ = _app()
    _add(client)
    before = (len(store.all()), pins.pinned_ids())

    _list(client)

    assert (len(store.all()), pins.pinned_ids()) == before


def test_a_listed_favorite_carries_the_frozen_fields() -> None:
    client, _, _, _ = _app()
    _add(client)

    item = _list(client).json()["items"][0]

    assert set(item) == {"favorite_id", "target_kind", "target_id",
                         "evidence_snapshot", "created_at", "snapshot_stale"}
    assert item["snapshot_stale"] is False


def test_identity_is_required_everywhere() -> None:
    client, _, _, _ = _app()

    assert client.get("/favorites").status_code == 422
    assert client.post("/favorites", json={}).status_code == 422
    assert client.delete("/favorites/fav-1").status_code == 422


# ───────────────────────── 二、加收藏 + pin（acceptance①②）


def test_adding_a_favorite_pins_its_snapshot() -> None:
    """acceptance②：pin 过的快照 GC NEVER 清它。"""
    client, _, pins, _ = _app()

    _add(client)

    assert pins.is_pinned("snap-1")
    long_ago = {"snap-1": NOW - timedelta(days=400)}
    assert expired_snapshot_ids(long_ago, now=NOW, pins=pins) == []


def test_a_snapshot_without_an_id_is_still_favourited() -> None:
    """内嵌那条路不依赖 pin——没有 snapshot_id 照样收藏成功（pin 是补充，不是前提）。"""
    client, _, pins, _ = _app()

    response = _add(client, evidence_snapshot={"ledger_version": 1, "fact_ids": []})

    assert response.status_code == 200
    assert pins.pinned_ids() == set()


def test_adding_is_idempotent_for_the_same_owner() -> None:
    client, store, _, _ = _app()

    _add(client)
    second = _add(client, target_id="c-999")

    assert second.status_code == 200
    assert len(store.all()) == 1
    assert second.json()["target_id"] == "c-1", "同 id 幂等：既有那条为准"


def test_taking_someone_elses_favorite_id_is_404_not_their_content() -> None:
    """`add_favorite` 同 id 直接返回既有那条——不判归属就等于一发请求读到别人的快照。"""
    client, _, _, _ = _app()
    _add(client, "fav-x", user=OTHER)

    response = _add(client, "fav-x", user=ME)

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert "原文" not in response.text


def test_an_empty_snapshot_is_422() -> None:
    """空快照的收藏是一个指向空处的壳（`add_favorite` 的原话）。"""
    client, _, _, _ = _app()

    response = _add(client, evidence_snapshot={})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_FAILED"


def test_an_unknown_target_kind_is_422_and_lists_the_options() -> None:
    client, _, _, _ = _app()
    contract = _contract()

    response = _add(client, target_kind="report")

    assert response.status_code == 422
    # 走 get_type_hints：冻结件开了 from __future__ import annotations，
    # `__annotations__` 里是**字符串**，对它 get_args 恒得空元组
    # ——那会让「四种之内」悄悄变成「一种都不许」。
    allowed = sorted(get_args(get_type_hints(contract.Favorite)["target_kind"]))
    assert allowed == ["card", "cluster", "deliverable", "topic"]
    assert response.json()["detail"]["allowed"] == allowed


# ───────────────────────── 三、取消收藏（acceptance④）


def test_removing_my_own_favorite_works() -> None:
    client, store, _, _ = _app()
    _add(client)

    response = client.delete("/favorites/fav-1", headers={"X-User-Id": ME})

    assert response.status_code == 204
    assert store.all() == []


def test_removing_someone_elses_favorite_is_404_and_leaves_it_alone() -> None:
    """`remove_favorite` **不判归属**——不在端点里补一道，任何人都能删别人的收藏。"""
    client, store, _, _ = _app()
    _add(client, "fav-x", user=OTHER)

    response = client.delete("/favorites/fav-x", headers={"X-User-Id": ME})

    assert response.status_code == 404
    assert len(store.all()) == 1, "越权删除必须什么都没删掉"


def test_removing_an_unknown_favorite_is_404_with_the_same_code() -> None:
    """两种 404 同一行同一码：状态码本身 NEVER 泄露存在性。"""
    client, _, _, _ = _app()
    _add(client, "fav-x", user=OTHER)

    unknown = client.delete("/favorites/fav-nope", headers={"X-User-Id": ME})
    theirs = client.delete("/favorites/fav-x", headers={"X-User-Id": ME})

    assert unknown.status_code == theirs.status_code == 404
    assert unknown.json()["code"] == theirs.json()["code"] == "NOT_FOUND"


def test_removing_a_favorite_never_unpins_a_snapshot_someone_else_still_uses() -> None:
    """顺手 unpin 会把**另一条收藏还在引用**的快照放回周删名单。

    那条收藏是内嵌的，删不掉；但走 pin 那条路的引用会在下一次周删时消失，
    而删的人完全不知道自己动了别人的东西。
    """
    client, _, pins, _ = _app()
    _add(client, "fav-a", user=ME)
    _add(client, "fav-b", user=OTHER)          # 同一个 snap-1

    client.delete("/favorites/fav-a", headers={"X-User-Id": ME})

    assert pins.is_pinned("snap-1")


# ───────────────────────── 四、陈旧态（acceptance③）


def test_the_staleness_check_delegates_to_the_existing_caliber() -> None:
    """判定转调 `evaluate_snapshot_stale`（§6-H1 统一口径），端点里一行比对都不写。"""
    client, _, _, _ = _app(removed=("f-1",))
    _add(client)

    body = client.post(
        "/favorites/fav-1/staleness", headers={"X-User-Id": ME}).json()

    assert body["status"] == "checked"
    assert body["snapshot_stale"] is True


def test_a_fresh_favorite_is_not_stale() -> None:
    client, _, _, _ = _app()
    _add(client)

    body = client.post(
        "/favorites/fav-1/staleness", headers={"X-User-Id": ME}).json()

    assert body["snapshot_stale"] is False


def test_a_snapshot_without_a_ledger_version_is_not_checked_not_fresh() -> None:
    """快照没记账本版本 → 报「没判过」。报 fresh 等于说「这份是最新的」，而我们不知道。"""
    client, _, _, _ = _app()
    _add(client, evidence_snapshot={"fact_ids": [], "snapshot_id": "s"})

    body = client.post(
        "/favorites/fav-1/staleness", headers={"X-User-Id": ME}).json()

    assert body["status"] == "not_checked"
    assert "snapshot_stale" not in body
    assert body["missing"] == "ledger_version"


def test_the_staleness_check_of_another_owner_is_404() -> None:
    client, _, _, _ = _app()
    _add(client, "fav-x", user=OTHER)

    response = client.post(
        "/favorites/fav-x/staleness", headers={"X-User-Id": ME})

    assert response.status_code == 404


def test_reading_the_list_never_evaluates_staleness() -> None:
    """`evaluate_snapshot_stale` 会落库——列表页 NEVER 顺手调它（那是藏起来的写）。

    列表报的是**库里存着的**那个标记；重算是显式的 POST。
    """
    client, store, _, _ = _app(removed=("f-1",))
    _add(client)

    _list(client)

    assert store.get("fav-1").snapshot_stale is False


# ───────────────────────── 五、更新到最新（acceptance③）


def test_refreshing_replaces_the_snapshot_and_keeps_the_old_one() -> None:
    client, store, _, history = _app()
    _add(client)

    response = client.post(
        "/favorites/fav-1/refresh-snapshot",
        json={"fresh_snapshot": _snapshot(version=9, snapshot_id="snap-2")},
        headers={"X-User-Id": ME})

    assert response.status_code == 200
    assert store.get("fav-1").evidence_snapshot["ledger_version"] == 9
    assert history.entries("fav-1")[0].snapshot["ledger_version"] == 3


def test_refreshing_never_unpins_the_old_snapshot() -> None:
    """「查看当时版本」要的正是那份旧快照——取消它的 pin 就是给它判了个缓刑。"""
    client, _, pins, _ = _app()
    _add(client)

    client.post("/favorites/fav-1/refresh-snapshot",
                json={"fresh_snapshot": _snapshot(snapshot_id="snap-2")},
                headers={"X-User-Id": ME})

    assert pins.is_pinned("snap-1"), "旧快照 NEVER 被解钉"
    assert pins.is_pinned("snap-2"), "新快照也要钉住"


def test_refreshing_with_an_empty_snapshot_is_422() -> None:
    client, store, _, _ = _app()
    _add(client)

    response = client.post("/favorites/fav-1/refresh-snapshot",
                           json={"fresh_snapshot": {}},
                           headers={"X-User-Id": ME})

    assert response.status_code == 422
    assert store.get("fav-1").evidence_snapshot["ledger_version"] == 3


def test_refreshing_someone_elses_favorite_is_404() -> None:
    client, store, _, _ = _app()
    _add(client, "fav-x", user=OTHER)

    response = client.post("/favorites/fav-x/refresh-snapshot",
                           json={"fresh_snapshot": _snapshot(version=9)},
                           headers={"X-User-Id": ME})

    assert response.status_code == 404
    assert store.get("fav-x").evidence_snapshot["ledger_version"] == 3


# ───────────────────────── 六、结构判据（acceptance⑥）


def test_the_module_writes_no_sql_of_its_own() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    docstrings = {ast.get_docstring(n) for n in ast.walk(tree)
                  if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef
                                | ast.AsyncFunctionDef)}
    literals = " ".join(
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value not in docstrings
    )

    for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER"):
        assert not re.search(rf"\b{verb}\b", literals, re.IGNORECASE), f"模块里有 {verb}"


def test_the_module_never_compares_versions_itself() -> None:
    """新旧只有账本说了算：模块里 NEVER 出现按版本号/时间戳自己比一次的表达式。"""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, ast.Lt | ast.Gt | ast.LtE | ast.GtE)
                   for op in node.ops):
            continue
        touched = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        assert not touched & {"ledger_version", "version", "created_at", "now"}, \
            f"模块自己比了一次新旧：{sorted(touched)}"


def test_no_field_is_synthesised() -> None:
    """收藏项逐字对齐冻结件 `Favorite`（owner 除外：调用方就是 owner，不必回给他自己）。"""
    client, _, _, _ = _app()
    _add(client)
    contract = _contract()

    item = _list(client).json()["items"][0]
    frozen = set(get_type_hints(contract.Favorite)) - {"owner"}

    assert set(item) == frozen
