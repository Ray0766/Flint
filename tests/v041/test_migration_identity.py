"""AUTH-01 · 迁移 0020：`users` / `orgs` / `memberships` 三张表。

## 这一批的地基

`WIRE-01` 拒绝挂四族路由，根因是拿不到一个诚实的 `role_resolver`——
而 `flint/jobs/runner.py` 文件头第 9 行早就写着：

> 角色解析经注入 `RoleResolver`（**memberships 表随身份任务落库后接 SQL 实现**）

**这张卡就是那个「身份任务」。** 三个类型（`User` / `Org` / `Membership`）
在冻结件里躺了很久，只是没有表。本卡只落表，**NEVER 改 `contracts/`**。

## 判据两侧都钉

「列按冻结件逐字」这句话，只判一侧是不够的：

- 只判「表的列 == 冻结件的字段」→ 有人改了冻结件，判据跟着改，照样绿；
- 只判「表的列 == 手抄的那串名字」→ 冻结件改了而表没跟上，判据也绿。

所以这里**两侧各钉一次**：字段名对着卡面的字面量钉住冻结件，
列名对着冻结件的 `dataclasses.fields` 钉住表。两侧同时动才骗得过——
而那种改动没人会不小心做出来。

## `role` 的取值域在**库层**拒

`Role = Literal["owner", "admin", "member", "viewer"]` 是 Python 侧的事实。
一条 `INSERT ... role='god'` 绕过应用直接进库时，Python 的类型不在场——
所以取值域 MUST 是一条 `CHECK`。判据真发一次越界写入，看库拒不拒。
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any, get_args

import asyncpg
import pytest

from contracts.models import Membership, Org, Role, User

pytestmark = pytest.mark.compose

REPO = Path(__file__).resolve().parents[2]
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
MIGRATION = REPO / "migrations" / "versions" / "0020_identity.py"
PREFIX = "auth01-"
# 卡面写死的那一串——**对着它钉冻结件**（见模块 docstring 的「两侧都钉」）。
FROZEN_FIELDS = {
    "users": ("user_id", "email", "display_name", "created_at"),
    "orgs": ("org_id", "name", "created_at"),
    "memberships": ("user_id", "org_id", "role"),
}
TYPES = {"users": User, "orgs": Org, "memberships": Membership}


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def _org(suffix: str = "org", name: str = "AUTH-01 夹具组织") -> str:
    return (f"INSERT INTO orgs (org_id, name, created_at) "
            f"VALUES ('{PREFIX}{suffix}', '{name}', now())")


def _user(suffix: str) -> str:
    return (f"INSERT INTO users (user_id, email, display_name, created_at) "
            f"VALUES ('{PREFIX}{suffix}', '{suffix}@auth01.invalid', "
            f"'{suffix}', now())")


def _member(user: str, org: str, role: str) -> str:
    return (f"INSERT INTO memberships (user_id, org_id, role) "
            f"VALUES ('{PREFIX}{user}', '{PREFIX}{org}', '{role}')")


_ORG = _org()


def _alembic_env() -> dict[str, str]:
    """alembic 子进程 MUST 迁移 DSN 指的那个库（先例 `tests/m3/test_m3_001.py`）。

    不显式传 `DATABASE_URL` 的话，`migrations/env.py` 的默认值指向 **demo 库**——
    下面那次 downgrade 就会 DROP 到 demo 上去。
    """
    return {**os.environ, "DATABASE_URL": DSN.replace(
        "postgresql://", "postgresql+asyncpg://", 1)}


def alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO, check=True, capture_output=True, env=_alembic_env())


async def _sql(statements: list[str]) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        for stmt in statements:
            await conn.execute(stmt)
    finally:
        await conn.close()


async def _columns(table: str) -> list[str]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = $1 ORDER BY ordinal_position", table)
    finally:
        await conn.close()
    return [r["column_name"] for r in rows]


async def _tables() -> set[str]:
    conn = await asyncpg.connect(DSN)
    try:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'")
    finally:
        await conn.close()
    return {r["table_name"] for r in rows}


@pytest.fixture(autouse=True)
def at_head() -> Any:
    alembic("upgrade", "head")
    run(_sql([
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
    ]))
    yield
    run(_sql([
        f"DELETE FROM memberships WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM users WHERE user_id LIKE '{PREFIX}%'",
        f"DELETE FROM orgs WHERE org_id LIKE '{PREFIX}%'",
    ]))


# ───────────────────────── acceptance①⑤：列按冻结件逐字，两侧都钉


def test_the_frozen_types_still_say_what_the_card_says() -> None:
    """**一侧**：冻结件的字段就是卡面写的那三串。

    只判「表 == 冻结件」的话，有人改冻结件时判据会跟着改而照样绿。
    这一条把冻结件本身钉在卡面的字面量上——本卡 NEVER 改 `contracts/`。
    """
    for table, expected in FROZEN_FIELDS.items():
        got = tuple(f.name for f in fields(TYPES[table]))
        assert got == expected, f"{TYPES[table].__name__} 的字段变了：{got}"


def test_every_table_has_exactly_the_frozen_columns() -> None:
    """**另一侧**：表的列 == 冻结件的字段，一列不多一列不少、顺序一致。

    多一列意味着表里有冻结件不知道的事实；少一列意味着有字段无处可存。
    """
    for table, expected in FROZEN_FIELDS.items():
        assert run(_columns(table)) == list(expected), table


# ───────────────────────── acceptance②：越界 role 在库层被拒


def test_the_four_frozen_roles_all_insert() -> None:
    """**正例**：冻结件 `Role` 的四个值逐个写得进去。

    没有这一条，「越界被拒」可能是「什么都被拒」换来的。
    """
    roles = get_args(Role)
    assert set(roles) == {"owner", "admin", "member", "viewer"}, roles

    run(_sql([_ORG]))
    for i, role in enumerate(roles):
        run(_sql([
            (f"INSERT INTO users (user_id, email, display_name, created_at) "
             f"VALUES ('{PREFIX}u{i}', 'u{i}@auth01.invalid', 'U{i}', now())"),
            (f"INSERT INTO memberships (user_id, org_id, role) "
             f"VALUES ('{PREFIX}u{i}', '{PREFIX}org', '{role}')"),
        ]))


def test_a_role_outside_the_frozen_literal_is_refused_by_the_database() -> None:
    """越界值**在库层**被拒——NEVER 只靠 Python 那一侧。

    一条绕过应用的 `INSERT ... role='god'` 打进来时，`Literal` 不在场。
    """
    run(_sql([_ORG, _user("bad")]))

    with pytest.raises(asyncpg.CheckViolationError):
        run(_sql([_member("bad", "org", "god")]))


# ───────────────────────── acceptance③：同一人同一组织只有一条角色行


def test_the_same_person_cannot_hold_two_roles_in_one_org() -> None:
    """`(user_id, org_id)` 复合主键。

    两条角色行意味着「他是什么角色」有两个答案，而解析器只会取到其中一个——
    取到哪一个取决于扫描顺序，那是**看起来正常的越权**。
    """
    run(_sql([_ORG, _user("dup"), _member("dup", "org", "member")]))

    with pytest.raises(asyncpg.UniqueViolationError):
        run(_sql([_member("dup", "org", "admin")]))


def test_the_composite_key_is_on_both_columns_not_just_the_user() -> None:
    """**对照**：同一个人在**另一个**组织里可以有另一个角色。

    主键只落在 `user_id` 上的话，上面那条也会红——而那是另一种错。
    """
    run(_sql([
        _ORG, _org("org2", "B"), _user("two"),
        _member("two", "org", "admin"), _member("two", "org2", "viewer"),
    ]))


# ───────────────────────── acceptance④：up / down 都真跑


def test_downgrade_removes_the_tables_and_upgrade_brings_them_back() -> None:
    """**两个方向都真跑一遍**：down 之后三张表不在，up 之后回来。

    只跑 upgrade 的话，`downgrade()` 里写错什么都没人知道——
    而回滚是出事那天唯一的退路。
    """
    identity = {"users", "orgs", "memberships"}
    assert identity <= run(_tables())

    alembic("downgrade", "0019")
    assert identity.isdisjoint(run(_tables())), "downgrade 之后表还在"

    alembic("upgrade", "head")
    assert identity <= run(_tables())


def test_the_revision_follows_0019_without_skipping() -> None:
    """迁移号接 0019，NEVER 跳号。

    跳号的那天，两个分支各建一张表，谁先跑谁定，另一条永远上不去。
    """
    text = MIGRATION.read_text(encoding="utf-8")

    assert 'revision = "0020"' in text
    assert 'down_revision = "0019"' in text
