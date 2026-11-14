"""建/迁移**测试库** flint_test —— 演示库与测试库分家的落地脚本。

## 为什么要有它

demo 库与测试库曾是同一个 `flint`。跑一次 `pytest -q`：
  · 各 compose 用例的 wipe fixture `DELETE FROM projects / topics / deliverables ...`；
  · tests/m3/test_m3_001.py 还会 `alembic downgrade 0007` —— 那是 **DROP TABLE**，
    deliverables / blocks / projects / topics / origins 整张表没掉。
于是每跑一次测试，demo 数据就得重建一次（已咬六次）。分库把这条路彻底断掉。

## 幂等

三步都可以重复跑：
  ① CREATE DATABASE —— Postgres **没有** IF NOT EXISTS，MUST 先查 pg_database 再建；
  ② alembic upgrade head —— 已在 head 就是空操作；
  ③ seed 12 个大类 —— ON CONFLICT DO UPDATE。

第 ③ 步不是可选项：categories 是人工固定资产（assets/categories.yaml），
clusters.category_id 有外键指过去。空库缺这 12 行，fe_views / centroid 等用例
会以 ForeignKeyViolationError 失败——那不是断言不过，是库没备齐。

## 留的口子：真实证据卡（owner 未拍板，故 NEVER 自作主张实现）

`tests/topic/test_ts_010_combo_api.py` 有一条用例按设计写着「本机 PG 不足 2 个跨簇
证据卡就 skip」。分库前它连 demo 库（1027 张真卡）→ 从不 skip；分库后在**全新**
flint_test 上第一次跑会 skip 一条（跑过一轮后有别的用例灌进卡，就不再 skip）。

两条路都有代价，交给 owner 拍：
  · 造合成卡 → 那条用例的语义从「真卡」变成「假卡」，等于改测试语义；
  · 从 demo 库**拷**真卡（categories → clusters → evidence_cards 按外键序）→ 语义
    不变，但测试库又与 demo 库的内容挂上钩，把刚断的耦合接回来一截。
要实现就加在 main() 里 _seed 之后，一个 `_copy_real_cards(demo_dsn, test_dsn, n)`。

## 为什么不靠 compose 的 initdb 脚本

`docker-entrypoint-initdb.d` 只在**数据卷首次创建**时执行。owner 的 pgdata 卷早就存在，
往里放脚本对既有环境是空操作 → NEVER 依赖它，本脚本走运行时路径。
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from flint.repo.categories import load_categories, seed_categories

TEST_DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test"
)
MAINTENANCE_DB = "postgres"
CATEGORIES_YAML = REPO_ROOT / "assets" / "categories.yaml"


def _split(dsn: str) -> tuple[str, str]:
    """(不含库名的前缀, 库名)。"""
    base, _, dbname = dsn.rpartition("/")
    return base, dbname.split("?", 1)[0]


async def _ensure_database(dsn: str) -> bool:
    """库不在就建。返回 True = 本次新建。"""
    base, dbname = _split(dsn)
    conn = await asyncpg.connect(f"{base}/{MAINTENANCE_DB}")
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", dbname)
        if exists:
            return False
        # 库名来自受控常量/env，不是用户输入；CREATE DATABASE 不接受参数占位符。
        await conn.execute(f'CREATE DATABASE "{dbname}"')
        return True
    finally:
        await conn.close()


def _migrate(dsn: str) -> None:
    url = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT, env={**os.environ, "DATABASE_URL": url},
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(f"alembic upgrade head 失败（{dsn}）")


async def _seed(dsn: str) -> int:
    categories = load_categories(CATEGORIES_YAML)
    await seed_categories(dsn, categories)
    return len(categories)


def main() -> int:
    _base, dbname = _split(TEST_DSN)
    created = asyncio.run(_ensure_database(TEST_DSN))
    print(f"[provision] {dbname}: {'已新建' if created else '已存在'}")
    _migrate(TEST_DSN)
    print(f"[provision] {dbname}: alembic upgrade head 完成")
    count = asyncio.run(_seed(TEST_DSN))
    print(f"[provision] {dbname}: 大类种子 {count} 条（幂等）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
