"""PERSIST-01：收藏 · 分享 · 偏好三表建齐，三族从内存件换成 SQL 实现。

## 根因不在接线那一层

`DEC-048` 记的实况：`favorites` / `share_links` / `prefs` 三张表
**从来没有建过**（`pg_tables` 实查，本卡开工前用 `asyncpg` 复核过一次）。
`flint/fav/store.py:35` 自述「内存实现；SQL 实现随 E2 的 `favorites` 表接入」——
**本卡就是那个接入**。

所以屏上「收藏按下去存不住」不是前端断线：`flint/api/app.py` 给 favorites
注的是 `store=None`（`WIRE-12` 的 `not_provided` 缝），给 share 与 prefs
注的是**内存件**——进程一重启就没了。

## 三族的三种失手各自不同，所以判据分三组

| 族 | 换成 SQL 之前的样子 | 换之后 MUST 成立的那一条 |
|---|---|---|
| 收藏 | `store=None` → `GET /favorites` 回 `not_provided` | 回**真列表**；空库时是空列表且**是查过的** |
| 分享 | 内存 `ShareLinkStore` → 重启即失效 | 链接跨进程还在；**撤销不是删除**（410 而不是 404） |
| 偏好 | 内存 `PrefsStore` → 换台设备就变了 | 服务端为真相（`PRINCIPLES#A3` 的可观测形式） |

## 「查过了是空的」与「没查过」NEVER 再合并

这是本卡最容易做假的一条：把 `store=None` 换成一个内存 store，
`GET /favorites` 立刻从 `not_provided` 变成 `{"items": []}`——**判据会转绿，
而用户看到的仍然是一句系统没有依据说出口的话**。
所以下面那条判据判的不是「回了空列表」，是**这个空列表来自一次真的查询**：
先往库里写一条别人的收藏，再断言我的列表是空的——
一个假 store 给不出这个区别（它对谁都回空）。

## 快照陈旧标记本卡 NEVER 自己置

`Favorite.snapshot_stale` 只能由 Revalidator 置（§6-H1，冻结件原话
「stale 判定来自 Revalidator 统一口径，前端 NEVER 自行按时间戳推断新鲜度」）。
SQL 实现是**存储层**：它照原样存、照原样读，NEVER 在读写路径上算一个出来。
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.domain.models import Principal

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PREFIX = "persist01-"
ME = f"{PREFIX}me"
OTHER = f"{PREFIX}other"
NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=UTC)

TABLES = ("favorites", "share_links", "prefs")


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(DSN)


async def _wipe() -> None:
    conn = await _conn()
    try:
        for table in TABLES:
            # 表名来自本文件的 `TABLES` 常量，不来自入参——没有注入面。
            await conn.execute(f"DELETE FROM {table}")
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _clean() -> Any:
    run(_wipe())
    yield
    run(_wipe())


# ───────────────────────── 一、三张表真的建出来了


def test_the_three_tables_exist_now() -> None:
    """`DEC-048` 的八张里的前三张。**实查 `pg_tables`**，不是查迁移文件。

    查迁移文件的话，一个写了 `op.create_table` 却没被 `alembic upgrade` 跑过的
    迁移也能让判据转绿——而库里仍然没有表。
    """
    async def _probe() -> list[str]:
        conn = await _conn()
        try:
            rows = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename = ANY($1::text[])", list(TABLES))
        finally:
            await conn.close()
        return sorted(r["tablename"] for r in rows)

    assert run(_probe()) == sorted(TABLES)


def test_the_migration_number_continues_without_a_gap() -> None:
    """迁移号从 `0023` 起顺序编，**NEVER 跳号也 NEVER 撞号**（本批 rules）。

    撞号的后果是 alembic 的 `down_revision` 链断成两条，
    `upgrade head` 会报 "Multiple head revisions" 而不是指出是哪两张卡撞了。
    """
    versions = sorted((REPO / "migrations" / "versions").glob("[0-9][0-9][0-9][0-9]_*.py"))
    numbers = [int(p.name[:4]) for p in versions]

    assert numbers == list(range(1, len(numbers) + 1)), f"号不连续：{numbers}"
    assert 23 in numbers, "本卡的迁移 0023 不在盘上"
    assert len(numbers) == len(set(numbers)), "有重号"


def test_the_migration_goes_down_and_up_again() -> None:
    """`upgrade` 与 `downgrade` **都跑通**（本批 rules）。

    只跑 upgrade 的话，一次回滚会把库卡在中间态——
    而回滚正是出事那天要做的第一件事。

    走子进程真跑 alembic：在进程内 import 迁移模块只证明它语法对。
    """
    # `migrations/env.py:20` 读的是 `DATABASE_URL`，且默认值指向 **demo 库**——
    # 不设它的话这条判据会把 demo 库降级再升级，而测试 NEVER 碰 demo 库。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "DATABASE_URL":
           DSN.replace("postgresql://", "postgresql+asyncpg://")}
    # **升回 `head` 而不是 `0023`**：升到 0023 就停的话，这条判据会把库
    # 丢在「本卡那三张表有了、后面几张迁移的表没了」的中间态，
    # 而同一次 `pytest -q` 里排在它后面的每一条用库的判据都会跟着红——
    # 实测被它带红过 20 条（模板表、全文列合规、docstore 三族），
    # 而那些红看起来全都像是别人的缺陷。
    for args in (["downgrade", "0022"], ["upgrade", "head"]):
        done = subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=REPO, env=env, capture_output=True, text=True, encoding="utf-8",
            check=False)          # 失败要由下面那句断言报出来，不是由 CalledProcessError
        assert done.returncode == 0, f"alembic {args} 失败：{done.stderr}"

    assert run(_table_names()) == sorted(TABLES), "回滚再升级之后三张表没有全回来"
    assert run(_at_head()) is True, "没有升回 head：库被丢在中间态了"


async def _at_head() -> bool:
    """库停在最新那一号上。**判的是「没有中间态」这件事本身**。"""
    conn = await _conn()
    try:
        current = await conn.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await conn.close()
    latest = max(
        int(p.name[:4])
        for p in (REPO / "migrations" / "versions").glob("[0-9][0-9][0-9][0-9]_*.py"))
    return str(current) == f"{latest:04d}"


async def _table_names() -> list[str]:
    conn = await _conn()
    try:
        rows = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename = ANY($1::text[])", list(TABLES))
    finally:
        await conn.close()
    return sorted(r["tablename"] for r in rows)


# ───────────────────────── 二、收藏：能存能读能删，且跨进程还在


def _fav_store() -> Any:
    from flint.fav.pgstore import PgFavoriteStore

    return PgFavoriteStore(dsn=DSN)


def _favorite(favorite_id: str, owner_id: str) -> Any:
    from flint.api.favorites import _contract

    return _contract().Favorite(
        favorite_id=favorite_id,
        owner=Principal(kind="user", id=owner_id),
        target_kind="cluster",
        target_id="cl-1",
        evidence_snapshot={"title": "热点一", "nested": {"k": ["v"]}},
        created_at=NOW,
    )


def test_a_favorite_survives_a_new_store_object() -> None:
    """存进去之后，**换一个 store 对象**照样读得到——这就是「存得住」的可观测形式。

    内存件在这一条上必红：它的字典跟着对象走。
    """
    _fav_store().put(_favorite("f1", ME))

    row = _fav_store().get("f1")

    assert row is not None
    assert row.favorite_id == "f1"
    assert row.target_kind == "cluster"
    assert row.evidence_snapshot == {"title": "热点一", "nested": {"k": ["v"]}}


def test_reading_a_favorite_gives_back_a_copy_not_a_handle() -> None:
    """读出去的是**副本**：调用方改返回值 NEVER 影响库里的快照。

    内存件靠 `copy.deepcopy` 做到这件事（`flint/fav/store.py:43` 原话）。
    SQL 实现天然是副本（每次从 JSON 重建），这条判据钉的是**这个性质没丢**——
    换实现时最容易掉的就是这种「本来就成立所以没人写下来」的性质。
    """
    _fav_store().put(_favorite("f1", ME))

    first = _fav_store().get("f1")
    first.evidence_snapshot["title"] = "被改了"

    assert _fav_store().get("f1").evidence_snapshot["title"] == "热点一"


def test_dropping_a_favorite_is_idempotent() -> None:
    """删两次 NEVER 抛错：第二次回 `False`（`remove_favorite` 的既有口径）。"""
    store = _fav_store()
    store.put(_favorite("f1", ME))

    assert store.drop("f1") is True
    assert store.drop("f1") is False


def test_my_list_is_empty_because_it_was_queried_not_because_it_was_never_stored() -> None:
    """**本卡最容易做假的一条**（见模块 docstring）。

    库里有一条**别人的**收藏，我的列表 MUST 是空的。
    一个假 store（对谁都回空）给不出这个区别，
    而「查过了、你确实没有收藏」与「这功能还没有库」正是靠这个区别分开的。
    """
    from flint.fav.store import list_favorites

    _fav_store().put(_favorite("f-other", OTHER))

    mine = list_favorites(_fav_store(), owner=Principal(kind="user", id=ME))
    theirs = list_favorites(_fav_store(), owner=Principal(kind="user", id=OTHER))

    assert mine == []
    assert [f.favorite_id for f in theirs] == ["f-other"]


def test_a_new_favorite_is_not_stale_and_the_store_never_decides_that() -> None:
    """`snapshot_stale` 只能由 Revalidator 置（§6-H1）。

    存储层照原样存、照原样读——**NEVER 在读写路径上算一个出来**。
    这条判据两个方向都量：新建的是 `False`；
    被 Revalidator 置成 `True` 的那条，读回来仍然是 `True`（存储层没把它抹平）。
    """
    from dataclasses import replace

    store = _fav_store()
    store.put(_favorite("f1", ME))
    assert store.get("f1").snapshot_stale is False

    store.put(replace(store.get("f1"), snapshot_stale=True))

    assert _fav_store().get("f1").snapshot_stale is True


# ───────────────────────── 三、分享：能生成能失效，且撤销不是删除


def _share_store() -> Any:
    from flint.share.pgstore import PgShareLinkStore

    return PgShareLinkStore(dsn=DSN)


def _link(token: str, owner_id: str, *, revoked: bool = False) -> Any:
    from flint.api.share import ShareLink

    return ShareLink(
        token=token, target_kind="deliverable", target_id="d-1",
        created_by=Principal(kind="user", id=owner_id),
        expires_at=None, revoked=revoked, created_at=NOW, password_hash=None,
    )


def test_a_share_link_survives_a_new_store_object() -> None:
    _share_store().put(_link("tok-1", ME))

    row = _share_store().get("tok-1")

    assert row is not None
    assert row.target_kind == "deliverable"
    assert row.created_by == Principal(kind="user", id=ME)


def test_revoking_keeps_the_row_so_the_holder_gets_410_not_404() -> None:
    """撤销 = 置位 + **留着那行**（冻结件原话「过期可续期，撤销不可逆」）。

    删掉的话持链人拿到 404「没这条」，他会以为自己拿错了链接；
    留着才能回 410「你没走错，它到期了」，他据此去找人续期。
    换成 SQL 之后最省事的写法就是 `DELETE`——所以这条判据钉住它。
    """
    from dataclasses import replace

    store = _share_store()
    store.put(_link("tok-1", ME))

    store.put(replace(store.get("tok-1"), revoked=True))

    row = _share_store().get("tok-1")
    assert row is not None, "撤销把行删掉了——持链人会拿到 404 而不是 410"
    assert row.revoked is True


def test_my_links_never_include_someone_elses() -> None:
    _share_store().put(_link("tok-mine", ME))
    _share_store().put(_link("tok-theirs", OTHER))

    mine = _share_store().for_owner(Principal(kind="user", id=ME))

    assert [r.token for r in mine] == ["tok-mine"]


def test_the_password_hash_round_trips_and_the_plaintext_never_lands() -> None:
    """口令只以 hash 形态存在（冻结件原话「连放明文的地方都不留」）。

    这条判据量的是**库里那一列**：ORM 层做对了而 SQL 写错列的话，
    上层判据全绿而库里躺着明文。
    """
    from dataclasses import replace

    from flint.share.links import hash_password

    digest = hash_password("open-sesame")
    _share_store().put(replace(_link("tok-1", ME), password_hash=digest))

    async def _column() -> Any:
        conn = await _conn()
        try:
            return await conn.fetchval(
                "SELECT password_hash FROM share_links WHERE token = $1", "tok-1")
        finally:
            await conn.close()

    stored = run(_column())
    assert stored == digest
    assert "open-sesame" not in (stored or "")


# ───────────────────────── 四、偏好：服务端为真相


def _prefs_store() -> Any:
    from flint.profile.pgprefs import PgPrefsStore

    return PgPrefsStore(dsn=DSN)


def test_prefs_round_trip_across_store_objects() -> None:
    """「跨设备一致」不是附加功能，它就是「服务端为真相」的可观测形式
    （`flint/profile/prefs.py` 文件头原话）。换 store 对象读得到 = 那句话成立。
    """
    from flint.profile.prefs import Prefs

    _prefs_store().put(ME, Prefs(lang="en", region="US"))

    assert _prefs_store().get(ME) == Prefs(lang="en", region="US")


def test_an_unset_user_gets_the_declared_default_not_an_empty_row() -> None:
    """没设过 → **声明过的默认值**（zh/CN），而不是「空」或「猜」。

    SQL 实现最容易在这里出错：`SELECT` 回 `None` 之后返回 `None`，
    于是上层拿到一个没有 `lang` 的对象——而默认值这件事是
    `get_prefs` 的既有口径，NEVER 由存储层改写。
    """
    from flint.profile.prefs import DEFAULT_LANG, DEFAULT_REGION, Prefs

    assert _prefs_store().get(f"{PREFIX}never-set") == Prefs(
        lang=DEFAULT_LANG, region=DEFAULT_REGION)


def test_setting_one_axis_leaves_the_other_alone_through_sql() -> None:
    """`PRINCIPLES#A3` 两条轴：只改语言时地区不动。

    既有判据在内存件上量过一次；换成 SQL 之后**必须再量一次**——
    upsert 写法最常见的失手就是把没传的那一列覆盖成默认值。
    """
    from flint.profile.prefs import Prefs, set_prefs

    _prefs_store().put(ME, Prefs(lang="zh", region="JP"))

    set_prefs(_prefs_store(), user_id=ME, lang="en")

    assert _prefs_store().get(ME) == Prefs(lang="en", region="JP")


# ───────────────────────── 五、接上之后：not_provided 那一态保留但不再触发


def _client() -> Any:
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    return TestClient(create_app(dsn=DSN), raise_server_exceptions=False)


def test_favorites_no_longer_answers_not_provided() -> None:
    """接上之后 `GET /favorites` 回**真列表**。

    改前它回的是 `{"status": "not_provided", …}`——那一态**本身是对的**
    （`WIRE-12` 建它是为了不拿空列表冒充「你确实没有收藏」），
    本卡做的是让它**不再被触发**，NEVER 把那一态删掉。
    """
    got = _client().get("/favorites", headers={"x-user-id": ME})

    assert got.status_code == 200
    body = got.json()
    assert body.get("status") != "not_provided", "still not_provided：store 没接上"
    assert body == {"items": []}


def test_the_not_provided_seam_is_still_in_the_code() -> None:
    """那一态 MUST 还在：`store=None` 时它仍然是唯一诚实的答复。

    删掉的话，下一次库没配好时端点会回一个空列表——
    而那正是 `WIRE-12` 花了一整张卡去消灭的那句话。
    """
    from flint.api.favorites import FavoritesApiDeps, create_favorites_app

    source = Path(_module_file("flint.api.favorites")).read_text(encoding="utf-8")
    assert "not_provided" in source
    # `PERSIST-01` 把这个形参放宽成协议（`FavoriteStoreLike`），
    # 为的是 SQL 实现在类型上过得去。**缝本身没变**：可空仍然是可空。
    assert "store: FavoriteStoreLike | None" in source

    app = create_favorites_app(FavoritesApiDeps(
        store=None, pins=_null_pins(), history=_null_history(),
        diff_channel=None, now=lambda: NOW,
        project_id_for=lambda _row: "", current_version=lambda: 0))
    from fastapi.testclient import TestClient

    got = TestClient(app).get("/favorites", headers={"x-user-id": ME})
    assert got.json()["status"] == "not_provided"


def _module_file(name: str) -> str:
    import importlib

    path = importlib.import_module(name).__file__
    assert path is not None
    return path


def _null_pins() -> Any:
    from flint.fav.pin import SnapshotPins

    return SnapshotPins()


def _null_history() -> Any:
    from flint.fav.stale import SnapshotHistoryStore

    return SnapshotHistoryStore()


def test_a_favorite_written_through_the_endpoint_lands_in_the_table() -> None:
    """端到端一条：POST 一次，**库里那张表**里就该有一行。

    只断言端点回 200 的话，一个把行写进内存字典的实现也能全绿。
    """
    client = _client()
    body = {"favorite_id": "f-api", "target_kind": "cluster", "target_id": "cl-9",
            "evidence_snapshot": {"title": "从端点写进去的"}}

    posted = client.post("/favorites", json=body, headers={"x-user-id": ME})
    assert posted.status_code == 200, posted.text

    async def _count() -> int:
        conn = await _conn()
        try:
            return int(await conn.fetchval(
                "SELECT count(*) FROM favorites WHERE favorite_id = $1", "f-api"))
        finally:
            await conn.close()

    assert run(_count()) == 1

    listed = client.get("/favorites", headers={"x-user-id": ME}).json()
    assert [row["favorite_id"] for row in listed["items"]] == ["f-api"]


def test_someone_else_can_neither_see_nor_delete_my_favorite() -> None:
    """鉴权照 `AUTH-03` 口径：收藏是写操作，越权 NEVER 得逞。

    端点把越权与不存在**合成一句 404**（403 会用状态码本身泄露存在性，
    `flint/api/favorites.py` 文件头原话）——本卡换存储层，那条口径 NEVER 变。
    """
    client = _client()
    client.post("/favorites", headers={"x-user-id": ME}, json={
        "favorite_id": "f-mine", "target_kind": "cluster", "target_id": "cl-1",
        "evidence_snapshot": {"title": "我的"}})

    listed = client.get("/favorites", headers={"x-user-id": OTHER}).json()
    deleted = client.delete("/favorites/f-mine", headers={"x-user-id": OTHER})

    assert listed == {"items": []}
    assert deleted.status_code == 404

    still = client.get("/favorites", headers={"x-user-id": ME}).json()
    assert [row["favorite_id"] for row in still["items"]] == ["f-mine"]


def test_prefs_written_through_the_endpoint_survive_a_new_app() -> None:
    """`PUT /settings/locale` 写完之后，**换一个 app 实例**读得到。

    内存件在这一条上必红——而它红的正是 owner 说的那件事：
    「选择要存得住」。
    """
    _client().put("/settings/locale", json={"region": "JP"},
                  headers={"x-user-id": ME})

    got = _client().get("/settings/locale", headers={"x-user-id": ME}).json()

    assert got["region"] == "JP"
    assert got["lang"] == "zh", "只改地区时语言 NEVER 跟着动（A3）"


def test_shares_written_through_the_endpoint_survive_a_new_app() -> None:
    created = _client().post(
        "/shares", headers={"x-user-id": ME},
        json={"target_kind": "deliverable", "target_id": "d-1"})
    assert created.status_code == 200, created.text
    token = created.json()["token"]

    mine = _client().get("/shares", headers={"x-user-id": ME}).json()

    assert [row["token"] for row in mine["items"]] == [token]
