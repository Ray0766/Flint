"""LOCK-01：`projects` 全行 upsert 没有乐观锁——`change_log` 会被**静默**覆盖。

## steward 第 6 批复核查出来的

`ENTRY-02` 把 `PgProjectStore.save` 从纯 `INSERT` 改成全行 upsert。
**改动本身是对的**（`save` 只能建不能更是真缺陷，`created_at` 排除在更新列外也对）。

**但它没有乐观锁，而 `change_log` 在被覆盖的列里。** `projects` 九列没有版本列：

```
project_id · owner · origin_id · topic_ids · chosen_topic_id
· deliverable_ids · change_log · status · created_at
```

并发下：

```
A 读（change_log=[e1]） → B 读（[e1]） → A 写（[e1,e2]） → B 写（[e1,e3]）
                                                          ↑ e2 无声消失
```

**改前是「第二次写大声失败（500）」，改后是「并发下静默丢失」**——
它把一个响亮的错换成了一个安静的错。现在只有一条写路径，风险是**潜伏**的，
而「潜伏」正是 `ENTRY-02` 形容原缺陷时用的词。

## 本卡把响亮的错找回来

加版本列 + 条件更新（`WHERE version = $n`），版本不符抛
`ProjectVersionConflict`，端点转 409。

## 阴性对照 MUST 断言「数据没丢」

**只断言抛了异常不够。** 这张卡修的正是「静默丢失」——
一个抛了异常但已经把 `[e1,e2]` 覆盖成 `[e1,e3]` 的实现，
在「抛异常」那条判据下是绿的，而它把这张卡要修的东西原样留着。

所以 `test_the_first_writers_entry_survives_the_conflict` 是这一组的核心：
冲突之后**回库读一次**，A 那条 `change_log` 条目必须还在。

## 口径与 `LedgerStore` 同源，NEVER 另发明一套

`flint/ledger/store.py#derive` 的既有形状：先读当前版本 → 与 expected 比 →
不符则抛一个**携带当前状态**的冲突（败者看到胜者的状态）。本卡照抄这个形状，
连异常携带的东西都一样——两套不同的乐观锁写法会让调用方分不清该怎么重试。
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "migrations" / "versions" / "0022_project_version.py"
MIGRATIONS = REPO / "migrations" / "versions"
STORE = REPO / "flint" / "topic" / "store.py"
LEDGER = REPO / "flint" / "ledger" / "store.py"
TOPICS_API = REPO / "flint" / "api" / "topics.py"

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
PROJECT_ID = "proj-lock-01"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _project(change_log: list[Any], chosen: str | None = None) -> Any:
    from datetime import UTC, datetime

    from flint.domain.models import Principal, Project

    return Project(
        project_id=PROJECT_ID, owner=Principal(kind="user", id="u-lock"),
        origin_id="origin-lock-01", topic_ids=["tp-a", "tp-b"],
        chosen_topic_id=chosen, deliverable_ids=[],
        change_log=change_log, status="active",
        created_at=datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture()
def created() -> Any:
    """一条干净的 project，`change_log` 从空开始。"""
    import asyncpg

    from flint.topic.store import PgProjectStore

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "DELETE FROM projects WHERE project_id = $1", PROJECT_ID)
        finally:
            await conn.close()

    _run(wipe())
    _run(PgProjectStore(dsn=DSN).save(_project([])))
    yield
    _run(wipe())


async def _read_change_log() -> list[Any]:
    import json

    import asyncpg

    conn = await asyncpg.connect(DSN)
    try:
        raw = await conn.fetchval(
            "SELECT change_log FROM projects WHERE project_id = $1", PROJECT_ID)
    finally:
        await conn.close()
    return list(json.loads(raw)) if raw else []


# ───────────────────────── 一、迁移：接号、两个方向、列本身


def test_the_migration_continues_the_numbering() -> None:
    """接 0021，**NEVER 跳号**。

    跳号的迁移在 `alembic history` 上仍然是一条线（它按 `down_revision` 串），
    所以跳号不会当场报错——**它只会让下一个人算错水位**。
    """
    assert MIGRATION.exists(), "迁移 0022 不在"
    numbers = sorted(
        int(m.group(1)) for p in MIGRATIONS.glob("*.py")
        if (m := re.match(r"(\d{4})_", p.name))
    )

    # 改前这里还钉着 `numbers[-1] == 22`（写这条判据时 0022 是最后一个）。
    # `PERSIST-01` 加了 0023 之后它红了——**红的是「22 是最后一个」这个事实过去了，
    # 不是有人跳号**，而这条判据的意图（docstring 原话）是「NEVER 跳号」。
    # 钉住最大值等于让每一张新迁移卡都回来改 LOCK-01 的判据，
    # 而每改一次都要重新判断「这次红是真的吗」——那正是判据该替人做的事。
    # 所以改成**只判连续**：22 在里面、全段无断档。意图一字未动。
    assert 22 in numbers, f"迁移 0022 不在号段里：{numbers}"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), (
        f"迁移号有断档：{numbers}")


def test_the_migration_chains_onto_0021() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert re.search(r'down_revision\s*[:=].*"0021', text), "没接在 0021 后面"
    assert re.search(r'revision\s*[:=].*"0022', text)


def test_both_directions_are_implemented() -> None:
    """`downgrade` 不是摆设。

    只写 `upgrade` 的迁移，出问题时唯一的退路是**手写 SQL 改生产库**——
    而那正是 `S2-10` 要人工确认的那类操作。
    """
    text = MIGRATION.read_text(encoding="utf-8")

    assert "def upgrade()" in text and "def downgrade()" in text
    assert "add_column" in text, "upgrade 没加列"
    assert "drop_column" in text, "downgrade 没把列去掉"


def test_the_version_column_is_not_null_with_a_default() -> None:
    """版本列**非空且有默认值**——与 `region` 那一列刻意相反。

    `region` 可空，因为「还不知道这个簇属于哪个区」是一种真实状态。
    版本不是这样：**一行记录永远有一个版本**，`NULL` 在这里没有含义。
    而已经在库里的那些行需要一个起点，所以 `server_default` 是必需的——
    没有它，迁移会在既有行上当场违约。
    """
    text = MIGRATION.read_text(encoding="utf-8")

    assert "nullable=False" in text, "版本列写成了可空——NULL 版本没有含义"
    assert "server_default" in text, "既有行没有起点，迁移会当场违约"


@pytest.mark.compose
def test_the_column_really_exists_in_the_database() -> None:
    """**列真的在库里**——上面几条判的都是文本，这一条打真库。

    只判迁移文件的话，一个从来没跑过的迁移也能让它们全绿。
    """
    import asyncpg

    async def column() -> Any:
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchrow(
                "SELECT is_nullable, column_default FROM information_schema.columns "
                "WHERE table_name = 'projects' AND column_name = 'version'")
        finally:
            await conn.close()

    row = _run(column())

    assert row is not None, "projects 表里没有 version 列——迁移没跑"
    assert row["is_nullable"] == "NO"
    assert row["column_default"] is not None


# ───────────────────────── 二、单写路径行为不变（acceptance⑥）


@pytest.mark.compose
def test_creating_a_project_still_works(created: None) -> None:
    """新建照常成功，且版本从 1 起。"""
    from flint.topic.store import PgProjectStore

    project, version = _run(PgProjectStore(dsn=DSN).load_with_version(PROJECT_ID))

    assert project.project_id == PROJECT_ID
    assert version == 1, f"新建那条的版本不是 1：{version}"


@pytest.mark.compose
def test_a_single_writer_updates_and_the_version_advances(created: None) -> None:
    """无并发时 `save` 照常成功（acceptance⑥），并且**版本往前走**。

    版本不动的话，锁就是个摆设：两次串行的写都会以为自己是第一个。
    """
    from flint.topic.store import PgProjectStore

    store = PgProjectStore(dsn=DSN)
    project, version = _run(store.load_with_version(PROJECT_ID))
    _run(store.save(_project([*project.change_log, {"action": "first"}]),
                    expected_version=version))

    again, next_version = _run(store.load_with_version(PROJECT_ID))

    assert next_version == version + 1
    assert again.change_log == [{"action": "first"}]


@pytest.mark.compose
def test_created_at_is_still_excluded_from_the_update(created: None) -> None:
    """`created_at` **仍然不在更新列里**（`ENTRY-02` 定下的，本卡不改）。

    一次更新把它改成「现在」，等于让这个项目看起来是刚建的。
    """
    from datetime import UTC, datetime

    from flint.topic.store import PgProjectStore

    store = PgProjectStore(dsn=DSN)
    original, version = _run(store.load_with_version(PROJECT_ID))
    moved = _project([{"action": "x"}])
    object.__setattr__(moved, "created_at", datetime(2030, 1, 1, tzinfo=UTC))
    _run(store.save(moved, expected_version=version))

    after, _ = _run(store.load_with_version(PROJECT_ID))

    assert after.created_at == original.created_at, "created_at 被一次更新改掉了"


# ───────────────────────── 三、阴性对照：本卡的核心


@pytest.mark.compose
def test_the_second_writer_hits_a_conflict(created: None) -> None:
    """A 读 → B 读 → A 写 → B 写：**B 拿到冲突**。

    改前 B 那次写会静静成功，并把 A 写的东西覆盖掉。
    """
    from flint.topic.store import PgProjectStore, ProjectVersionConflict

    store = PgProjectStore(dsn=DSN)
    _a, version_a = _run(store.load_with_version(PROJECT_ID))
    _b, version_b = _run(store.load_with_version(PROJECT_ID))
    _run(store.save(_project([{"action": "A"}]), expected_version=version_a))

    with pytest.raises(ProjectVersionConflict) as conflict:
        _run(store.save(_project([{"action": "B"}]), expected_version=version_b))

    assert conflict.value.current_version == version_a + 1


@pytest.mark.compose
def test_the_first_writers_entry_survives_the_conflict(created: None) -> None:
    """**这一组的核心**：冲突之后 A 那条 `change_log` 条目**还在**。

    只断言「抛了异常」不够——一个抛了异常但**已经写下去了**的实现，
    在那条判据下是绿的，而它把这张卡要修的东西（静默丢失）原样留着。
    """
    from flint.topic.store import PgProjectStore, ProjectVersionConflict

    store = PgProjectStore(dsn=DSN)
    _a, version_a = _run(store.load_with_version(PROJECT_ID))
    _b, version_b = _run(store.load_with_version(PROJECT_ID))
    _run(store.save(_project([{"action": "A", "topic_id": "tp-a"}]),
                    expected_version=version_a))
    with pytest.raises(ProjectVersionConflict):
        _run(store.save(_project([{"action": "B", "topic_id": "tp-b"}]),
                        expected_version=version_b))

    log = _run(_read_change_log())

    assert log == [{"action": "A", "topic_id": "tp-a"}], (
        f"A 写的那条不见了或被 B 覆盖了：{log}")


@pytest.mark.compose
def test_the_conflict_carries_the_winners_state(created: None) -> None:
    """异常**携带当前状态**——败者看得见胜者写了什么。

    这是 `LedgerVersionConflict` 的既有形状（`flint/ledger/store.py#_conflict`）。
    只给一句「版本不符」的话，调用方要重试就得自己再读一次，
    而**它读到的可能已经是第三个人写的了**。
    """
    from flint.topic.store import PgProjectStore, ProjectVersionConflict

    store = PgProjectStore(dsn=DSN)
    _a, version_a = _run(store.load_with_version(PROJECT_ID))
    _b, version_b = _run(store.load_with_version(PROJECT_ID))
    _run(store.save(_project([{"action": "A"}], chosen="tp-a"),
                    expected_version=version_a))

    with pytest.raises(ProjectVersionConflict) as conflict:
        _run(store.save(_project([{"action": "B"}], chosen="tp-b"),
                        expected_version=version_b))

    current = conflict.value.current_project
    assert current is not None, "冲突没带上当前状态"
    assert current.chosen_topic_id == "tp-a", "带上的不是胜者的状态"
    assert current.change_log == [{"action": "A"}]


@pytest.mark.compose
def test_creating_something_that_already_exists_is_loud(created: None) -> None:
    """不带版本去写一条**已存在**的记录 → 冲突，NEVER 静默覆盖。

    不带版本的 `save` 语义是「我在新建」。那一行已经在库里时，
    调用方的前提就是错的——而静默覆盖会把它现有的 `change_log` 整段抹掉。
    """
    from flint.topic.store import PgProjectStore, ProjectVersionConflict

    store = PgProjectStore(dsn=DSN)
    _run(store.save(_project([{"action": "A"}]), expected_version=1))

    with pytest.raises(ProjectVersionConflict):
        _run(store.save(_project([])))          # 不带 expected_version

    assert _run(_read_change_log()) == [{"action": "A"}], "已有的 change_log 被抹了"


# ───────────────────────── 四、口径与 LedgerStore 同源


def test_the_lock_is_a_conditional_update_not_a_read_then_write() -> None:
    """条件更新落在 **SQL 的 WHERE 里**，而不是「先读一次再判断」。

    先读后判有竞态窗口：两个写者都读到 version=1，都判「相符」，然后都写。
    `WHERE version = $n` 把判断交给数据库的行锁——**那个窗口不存在**。

    判的是 SQL 字面量，剥注释：改因注释里写着这段话本身。
    """
    code = "\n".join(
        line for line in STORE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))
    statements = re.findall(r'"UPDATE projects[^"]*"|"\s*(?:SET|WHERE)[^"]*"', code)

    joined = " ".join(statements)
    assert "UPDATE projects" in joined, f"没有一条 UPDATE projects：{statements}"
    assert "version = $" in joined and "WHERE" in joined.upper(), (
        f"更新不是按版本条件化的：{statements}")


def test_the_store_did_not_invent_a_second_locking_scheme() -> None:
    """NEVER 另发明一套（acceptance③）。

    两套不同的乐观锁写法会让调用方分不清该怎么重试——
    而重试策略是按冲突来源分派的（冻结件 `LedgerVersionConflict` 的 docstring）。
    """
    code = "\n".join(
        line for line in STORE.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#"))

    for invented in ("pg_advisory", "FOR UPDATE", "SELECT ... FOR", "retry_count",
                     "while True"):
        assert invented not in code, f"引入了另一套并发方案：{invented}"


def test_the_conflict_mirrors_the_ledger_conflict_shape() -> None:
    """异常形状与 `LedgerVersionConflict` 同构：带 `current_version` + 当前状态。"""
    from flint.topic.store import ProjectVersionConflict

    conflict = ProjectVersionConflict(current_version=7, current_project=None)

    assert conflict.current_version == 7
    assert hasattr(conflict, "current_project")
    assert "7" in str(conflict), "报错文本里没有当前版本，调用方要重试得再查一次"
    ledger = LEDGER.read_text(encoding="utf-8")
    assert "current_version" in ledger, "既有那一套不是这个形状（本条判据的前提变了）"


# ───────────────────────── 五、端点把冲突转成 409


def test_the_choose_topic_endpoint_passes_the_version_it_read() -> None:
    """`POST /projects/{id}/chosen-topic` 用它读到的版本去写。

    不传版本的话，那条端点会走「我在新建」那条路 → 每次选主题都冲突。
    **这不是可选的**：`ENTRY-02` 建的正是唯一一条更新路径。
    """
    code = TOPICS_API.read_text(encoding="utf-8")

    assert "load_with_version" in code, "端点还是不带版本地读"
    assert "expected_version" in code, "端点写回时没带版本"


def test_the_endpoint_turns_the_conflict_into_a_409() -> None:
    """冲突 → 409，且用**自己的码**，NEVER 借 `LEDGER_CONFLICT`。

    `LEDGER_CONFLICT` 说的是「这个项目的事实账本变了」，
    与「这个项目行被别人改了」是两件事——借一个已经有主的码去说另一件事
    是 `DEC-034` / `DEC-038` 反复禁的那一条。
    """
    from flint.api.schemas import ERROR_CODES

    code = TOPICS_API.read_text(encoding="utf-8")

    assert "PROJECT_CONFLICT" in ERROR_CODES, "没有属于 project 冲突的码"
    assert "409" in code, "端点没有把冲突转成 409"
    assert "PROJECT_CONFLICT" in code
    assert "ProjectVersionConflict" in code, "端点没有接那个异常"
