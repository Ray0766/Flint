"""WIRE-12 · 假空态：没有存储面的族 NEVER 回一个空表。

## 那句系统没有依据说出口的话

装配之后 `/favorites` 与 `/design/templates` 回的是 `{"items": []}`——
而迁移里 **34 张表没有 `favorites`，也没有 `templates`**。
那个空表与「查过了，你确实一条收藏都没有」**逐字相同**，
前端照契约渲染，屏上就写「还没有收藏」。

**真相是「这个功能还没有库，我们根本没查」。**

## 照 `/billing` 已经做对的那个形状

`/billing` 在没配时回 `{"status": "not_enabled", "reason": "…"}`——
状态一个位、理由一句话。本卡把那两族改成同一形状（`status: "not_provided"`）。

## 读回 200、写回 503

读用 200：**「这功能还没上」本身就是一个成功的回答**。
写用 503：调用方的那次写**确实没有发生**——回 200 会让它以为存下了。

## 「没查过」与「查过了是空的」NEVER 挤进同一个表示

这是第 2 批钉住、本卡继续执行的同一条纪律。判据两侧都留了实例：
`store=None` → `not_provided`；`store` 真在 → `{"items": []}` 照旧是
「查过了、确实没有」。**只改一侧的话，第二种意思就没地方表达了。**
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from flint.api.app import create_app

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
TICKET = REPO / "docs" / "blocked" / "WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md"
# `PERSIST-01`（`DEC-048`）之后 **`/favorites` 从这张名单上毕业了**：
# `favorites` 表建出来了，它回的是一份真列表。
# 名单上留下的是**仍然没有存储面**的那一族（`templates` 表由 `PERSIST-03` 建，
# 建完之后它也会毕业，而那时这张名单就该是空的）。
#
# **缝本身 NEVER 跟着毕业**：`store=None` 时的 `not_provided` 是本卡的产品，
# 它由下面两条**直接打缝**的判据看着
# （`test_the_seam_still_answers_not_provided_when_there_is_no_store`
# 与 `test_a_write_against_no_storage_is_refused_not_accepted`）——
# 从「装配后的应用」挪到「缝本身」，是因为装配面会一族一族地接上库，
# 而缝是永久的。挪之前那两条判的其实是「今天还没接」，不是「缝还在」。
# `PERSIST-03`（`DEC-048`）之后 **`/design/templates` 也毕业了**：
# `templates` 表建出来了，它回的是一份真列表。名单**空了**——
# `PERSIST-01` 在这里留的注释预告过这一刻。
#
# **空了 NEVER 等于缝没了**：`store=None` / `registry.available == False` 时
# `not_provided` 仍然是唯一诚实的答复，由下面两条**直接打缝**的判据看着。
# 名单留成空元组而不是删掉：下一族没有存储面的东西出现时，
# 把它的路径加进来就重新有人量了。
FAKE_EMPTY_PATHS: tuple[str, ...] = ()


def _seamless_favorites_app() -> Any:
    """一个**没有存储面**的收藏应用（`store=None`）——缝的那一侧。"""
    from flint.api.favorites import FavoritesApiDeps, create_favorites_app
    from flint.fav.pin import SnapshotPins
    from flint.fav.stale import SnapshotHistoryStore

    return create_favorites_app(FavoritesApiDeps(
        store=None, pins=SnapshotPins(), history=SnapshotHistoryStore(),
        diff_channel=lambda *_a, **_k: None, now=lambda: None,
        project_id_for=lambda _row: "", current_version=lambda: 0))


@pytest.fixture
def client() -> Any:
    with TestClient(create_app(DSN)) as test_client:
        yield test_client


def _get(client: TestClient, path: str) -> Any:
    return client.get(path, headers={"X-User-Id": "wire12-probe"})


# ───────────────────────── acceptance①②：不再回空表


@pytest.mark.skipif(not FAKE_EMPTY_PATHS,
                    reason="八张表建齐之后这张名单空了——缝改由直接打缝的两条量")
@pytest.mark.parametrize("path", FAKE_EMPTY_PATHS)
def test_a_family_without_storage_never_answers_with_an_empty_list(
    client: TestClient, path: str,
) -> None:
    """两条都不再回 `{"items": []}`。"""
    body = _get(client, path).json()

    assert "items" not in body, f"{path} 还在拿空表冒充查过了：{body}"


@pytest.mark.skipif(not FAKE_EMPTY_PATHS,
                    reason="八张表建齐之后这张名单空了——缝改由直接打缝的两条量")
@pytest.mark.parametrize("path", FAKE_EMPTY_PATHS)
def test_it_says_not_provided_and_says_why(client: TestClient, path: str) -> None:
    """照 `/billing` 的形状：`status` 一个位、`reason` 一句话。

    只给 `status` 不给 `reason` 的话，读的人知道「没有」却不知道**为什么没有**——
    而「还没建表」与「你没权限看」要人做的事完全不同。
    """
    got = _get(client, path)
    body = got.json()

    assert got.status_code == 200, got.text
    assert body["status"] == "not_provided", body
    assert len(body["reason"]) > 20, body
    assert "NEVER" in body["reason"], "理由里没写清楚它拒绝做什么"


def test_the_billing_shape_is_the_one_being_copied(client: TestClient) -> None:
    """**对照**：`/billing` 那个已经做对的形状还在。

    没有这一条，「照 billing 的形状」就是一句没人验证过的话。
    """
    body = _get(client, "/billing").json()

    assert body["billing"]["status"] == "not_enabled"
    assert body["billing"]["reason"]


# ───────────────────────── acceptance③：两种意思各有表示


def test_a_real_store_still_means_checked_and_empty() -> None:
    """**缝的另一侧**：`store` 真在时，`{"items": []}` 照旧是「查过了、确实没有」。

    只改一侧的话，「查过了是空的」这个意思就没地方表达了——
    而它是一个真实存在的状态。
    """
    from flint.api.favorites import FavoritesApiDeps, create_favorites_app
    from flint.fav.pin import SnapshotPins
    from flint.fav.stale import SnapshotHistoryStore
    from flint.fav.store import FavoriteStore

    deps = FavoritesApiDeps(
        store=FavoriteStore(), pins=SnapshotPins(),
        history=SnapshotHistoryStore(),
        diff_channel=lambda *_a, **_k: None, now=lambda: None,
        project_id_for=lambda _row: "", current_version=lambda: 0)
    with TestClient(create_favorites_app(deps)) as client:
        body = client.get("/favorites", headers={"X-User-Id": "u"}).json()

    assert body == {"items": []}, body


def test_the_seam_still_answers_not_provided_when_there_is_no_store() -> None:
    """**缝的那一侧**：`store=None` 时读回 200 + `not_provided` + 一句理由。

    `/favorites` 接上库之后（`PERSIST-01`）装配面上量不到这件事了，
    而缝**没有消失**——下一族没有库的时候走的仍然是这条路。
    所以这条判据直接构造 `store=None` 的应用去量，NEVER 依赖「今天哪一族还没接」。
    """
    with TestClient(_seamless_favorites_app()) as client:
        got = client.get("/favorites", headers={"X-User-Id": "wire12-probe"})
    body = got.json()

    assert got.status_code == 200, got.text
    assert "items" not in body, f"拿空表冒充查过了：{body}"
    assert body["status"] == "not_provided", body
    assert len(body["reason"]) > 20, body
    assert "NEVER" in body["reason"], "理由里没写清楚它拒绝做什么"


def test_a_write_against_no_storage_is_refused_not_accepted() -> None:
    """**写回 503**：那次写确实没有发生——回 200 会让调用方以为存下了。

    同上，改打缝本身（改前打的是装配后的 `/favorites`）。
    """
    client = TestClient(_seamless_favorites_app())
    got = client.post(
        "/favorites",
        json={"favorite_id": "wire12-f1", "target_kind": "cluster",
              "target_id": "c-1", "evidence_snapshot": {}},
        headers={"X-User-Id": "wire12-probe"})

    assert got.status_code == 503, got.text
    assert got.json()["family"] == "favorites"


# ───────────────────────── acceptance④：前端跟着改


def test_the_favorites_screen_maps_not_provided_to_the_not_checked_view() -> None:
    """前端把 `not_provided` 翻成「没查过」，把 `items` 翻成真列表。

    组件的入参口径是 `null` = 没查过、`[]` = 查过了确实没有——
    适配器**必须两种都能给出来**，否则屏上永远只有一种说法。
    """
    adapter = (REPO / "web" / "lib" / "screenAdapters.ts").read_text(encoding="utf-8")
    page = (REPO / "web" / "app" / "favorites" / "page.tsx").read_text(
        encoding="utf-8")

    assert "toFavoritesView" in adapter
    assert 'box.status === "not_provided"' in adapter and "return null" in adapter
    # 屏改成真取数了，而不是把 `null` 写死在页面里。
    assert "useScreenData" in page and "toFavoritesView" in page
    # **判代码，NEVER 判注释**：页面注释里写着「`not_provided` → `favorites={null}`」
    # 正是为了说明这条映射。本批第五次踩同一个坑，这次靠剥注释解决。
    code = "\n".join(
        line for line in page.splitlines() if not line.strip().startswith("//"))
    assert "favorites={null}" not in code, "还写死着 null——那不是取数，是硬编码"


# ───────────────────────── acceptance⑤：单子关掉


def test_the_ticket_is_closed() -> None:
    head = "\n".join(TICKET.read_text(encoding="utf-8").splitlines()[:16])

    assert "**状态** closed" in head
    assert "WIRE-12" in head
