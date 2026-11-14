"""两道前置闸：**编码**（ENV-01）与**测试库**（compose 用例）。

## 编码那道闸（ENV-01）

本机标准输出不是 UTF-8 时，27 条走 subprocess 的判据会**假红**，
报的全是 `TypeError: argument of type 'NoneType' is not iterable`。
那句话与代码坏了长得一模一样——**下一个会话会以为自己撞上了 27 条回归，
然后去修没坏的东西**。所以这里在开跑前就拦住，并把正确跑法打出来。

判的是 `sys.stdout.encoding` 的实况，不是「那个环境变量在不在」：
Linux/CI 上默认就是 UTF-8，判变量会误报；变量设成 `gbk` 也算「在」，而那照样炸。
细节与那句人话在 `tools/check_encoding_env.py`。

---

## 测试库前置闸：compose 用例开跑前，确认连的是 **flint_test** 且它真的存在。

## 为什么要这道闸

演示库与测试库曾共用一个 PG（都叫 flint）。各 compose 用例的 wipe fixture 会
`DELETE FROM projects / topics / deliverables / snapshots ...`，于是每跑一次
`pytest -q`，demo 数据就被清空一次——这个坑咬了六次。

分库（flint_test）之后最危险的不是「库不存在」，而是**悄悄回落到 flint**：
那等于把 bug 原样装回去，而且再也不会有人发现。所以这里 NEVER 回落——
库不存在就大声失败，并把建库命令直接打出来。

## 何时生效

只在本次收集到 **compose 标记**的用例时才连库。CI 的 `pytest -q -m "not compose"`
阶段一条 compose 用例都不收集，这道闸对它是空操作（那一阶段本就不需要 PG）。
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

TEST_DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
DEMO_DB_NAME = "flint"

_CREATE_CMDS = """\
  docker compose up -d postgres
  python scripts/provision_test_db.py
这一条脚本做完三件事且都幂等：建库（先查 pg_database 再 CREATE——PG 没有
IF NOT EXISTS）、alembic upgrade head、种 12 个大类。
第三步不能省：clusters.category_id 有外键指向 categories，空库缺这 12 行，
用例会以 ForeignKeyViolationError 失败——那不是断言不过，是库没备齐。
start-demo.ps1 已包含这一步，跑一次它也行。"""


def _database_name(dsn: str) -> str:
    return dsn.rsplit("/", 1)[-1].split("?", 1)[0]


async def _probe(dsn: str) -> str | None:
    """返回 None = 一切就绪；否则返回该报给人的原因。"""
    import asyncpg

    try:
        conn = await asyncpg.connect(dsn)
    except asyncpg.InvalidCatalogNameError:
        return (
            f"测试库不存在：{_database_name(dsn)}\n"
            "NEVER 回落到 demo 库 flint——那正是要根治的 bug。请先建库并迁移：\n"
            f"{_CREATE_CMDS}"
        )
    except (OSError, asyncpg.CannotConnectNowError) as err:
        return (
            f"连不上 PostgreSQL：{err}\n"
            "compose 栈没起来。先 `docker compose up -d postgres redis`，"
            "或用 `pytest -q -m \"not compose\"` 跑不需要 PG 的那部分。"
        )
    try:
        migrated: bool = await conn.fetchval("SELECT to_regclass('public.jobs') IS NOT NULL")
    finally:
        await conn.close()
    if not migrated:
        return (
            f"测试库 {_database_name(dsn)} 存在但没迁移（找不到 jobs 表）。请跑：\n"
            f"{_CREATE_CMDS}"
        )
    return None


def pytest_configure(config: pytest.Config) -> None:
    """ENV-01：编码那道闸**在收集之前**就拦。

    放在 `pytest_configure` 而不是某一条用例里：那 27 条一旦开跑，
    满屏 `TypeError` 就已经把这句说明淹没了——而它正是用来防止那种误读的。
    """
    del config
    from tools.check_encoding_env import hazard

    problem = hazard()
    if problem is not None:
        pytest.exit("\n" + problem + "\n", returncode=1)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    session: pytest.Session, config: pytest.Config, items: list[Any]
) -> None:
    if not any(item.get_closest_marker("compose") for item in items):
        return
    if _database_name(TEST_DSN) == DEMO_DB_NAME:
        pytest.exit(
            f"FLINT_TEST_DSN 指向了 demo 库（{TEST_DSN}）。测试会把它清空——拒绝开跑。",
            returncode=1,
        )
    reason = asyncio.run(_probe(TEST_DSN))
    if reason is not None:
        pytest.exit(f"\n{reason}\n", returncode=1)
