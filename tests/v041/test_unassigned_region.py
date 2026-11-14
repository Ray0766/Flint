"""REGION-11：`global` 与 `NULL` 归入显式的「未归区」（`DEC-040`）。

## 实况

steward 实查 `clusters.region` 的分布：**`global = 103` · `CN = 89` · `NULL = 1`**。
`global` 是 `ghtrend` 写死的常量，**不是地理事实**。

`REGION-09` 让筛选器只认冻结件 `contracts_v04.Region` 那九个，
于是 `global` 与 `NULL` 那 104 条**在默认视图之外再也看不见**——
选任何一个区都拿不到它们，而它们占了库里一多半。

## 两条错法各自的样子

- 把 `global` 当第九区（其实是第十个选项）→ 用户在**地理列表**里选到一个不存在的地方；
- 让它们从筛选面消失 → 那 104 条只在「不筛」时出现，**一旦开始筛就蒸发**。

**「未归区」是唯一诚实的说法**：它承认这些簇存在、也承认我们不知道它们的产地。

## 合并只发生在呈现层

库里 `NULL` 与 `global` **保持可分辨**。`NEVER 把 NULL 回填成 global`——
那会抹掉「这条簇从来没归过区」这个事实，**而抹掉之后，抹掉本身也看不见了**：
回填过的行与本来就是 `global` 的行长得一模一样。

`test_the_database_still_tells_the_two_apart` 与
`test_no_migration_backfills_null_into_global` 两条一起钉这件事。

## 「不在任何选项里」是本卡真正要消灭的东西

acceptance④ 那条**九区之和加未归区等于全量**才是核心判据。
只断言「未归区能选、能回 104 条」的话，将来多出一种 region 值
（比如某个源写死 `worldwide`）时它照样绿，而那批簇会重新变得**筛不到**。
所以这里判的是**闭合**：每一条簇 MUST 落在某一个选项里。
"""
from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
VIEWS = REPO / "flint" / "api" / "views.py"
REGIONS_TS = REPO / "web" / "lib" / "regions.ts"
SWITCH = REPO / "web" / "components" / "region-switch" / "RegionSwitch.tsx"
PLAZA_PAGE = REPO / "web" / "app" / "plaza" / "page.tsx"
MIGRATIONS = REPO / "migrations" / "versions"
SHEET = (REPO / "docs" / "blocked"
         / "REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md")

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DAY = date(2026, 7, 21)
VEC = "[" + ",".join(["0"] * 1024) + "]"

# 种子按 steward 实查的形状缩比：两个真区各有数据（空集会让对照恒成立），
# 外加一条 `global` 与一条 `NULL`——**两者都要有**，因为本卡要证明的正是它们合流。
SEED: tuple[tuple[str, str | None], ...] = (
    ("ur-cn-1", "CN"), ("ur-cn-2", "CN"),
    ("ur-us-1", "US"),
    ("ur-gl-1", "global"), ("ur-gl-2", "global"),
    ("ur-none", None),
)
PREFIX = "ur-"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def seeded() -> Any:
    import asyncpg

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(f"DELETE FROM heat_points WHERE cluster_id LIKE '{PREFIX}%'")
            await conn.execute(f"DELETE FROM clusters WHERE cluster_id LIKE '{PREFIX}%'")
        finally:
            await conn.close()

    async def seed() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for cid, region in SEED:
                await conn.execute(
                    "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                    "centroid, status, first_seen, last_active, parent_cluster_ids, "
                    "merged_into, aliases, region) VALUES ($1, $1, 'cat-ai', $2::vector, "
                    "'active', '2026-07-01', $3, '[]'::jsonb, NULL, '[]'::jsonb, $4)",
                    cid, VEC, DAY, region)
                await conn.execute(
                    "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, "
                    "norm_score) VALUES ($1, 'weibo', $2, 0.5, 0.5)", cid, DAY)
        finally:
            await conn.close()

    _run(wipe())
    _run(seed())
    yield
    _run(wipe())


def _get(query: str) -> Any:
    import httpx

    from flint.api.views import ViewsApiDeps, create_views_app

    async def go() -> Any:
        app = create_views_app(ViewsApiDeps(dsn=DSN))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver",
        ) as client:
            return await client.get(query)

    return _run(go())


def _ids(query: str) -> set[str]:
    resp = _get(query)
    assert resp.status_code == 200, resp.text
    return {c["cluster_id"] for c in resp.json()["clusters"]
            if str(c["cluster_id"]).startswith(PREFIX)}


def _sentinel() -> str:
    from flint.api.views import UNASSIGNED_REGION

    return UNASSIGNED_REGION


# ───────────────────────── 一、未归区是一个真能选的值


@pytest.mark.compose
def test_the_unassigned_option_is_accepted(seeded: None) -> None:
    """选未归区回 200，而不是「这个区不存在」。"""
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region={_sentinel()}")

    assert resp.status_code == 200, resp.text


@pytest.mark.compose
def test_the_unassigned_option_returns_both_global_and_null(seeded: None) -> None:
    """**本卡的核心**：`global` 与 `NULL` 两种都在里面。

    只回其中一种的话，另一种仍然是「筛不到」——
    而那正是这张单要消灭的东西。
    """
    got = _ids(f"/plaza/hot?day={DAY.isoformat()}&region={_sentinel()}")

    assert got == {"ur-gl-1", "ur-gl-2", "ur-none"}, f"未归区回的不对：{sorted(got)}"


@pytest.mark.compose
def test_the_unassigned_option_is_a_proper_subset(seeded: None) -> None:
    """未归区是全量的**真子集**——它没有顺手把九区的簇也捞进来。"""
    whole = _ids(f"/plaza/hot?day={DAY.isoformat()}")
    got = _ids(f"/plaza/hot?day={DAY.isoformat()}&region={_sentinel()}")

    assert got < whole, f"未归区不是全量的真子集：{sorted(got)}"
    assert "ur-cn-1" not in got and "ur-us-1" not in got


# ───────────────────────── 二、acceptance④：闭合——没有簇落在任何选项之外


@pytest.mark.compose
def test_the_nine_regions_plus_unassigned_cover_everything(seeded: None) -> None:
    """**九区之和加未归区 == 全量。**

    这一条比「未归区能选」值钱得多：将来多出一种 region 值
    （某个源写死 `worldwide`），「未归区能选」照样绿，
    而那批簇会重新变得筛不到。**这里判的是闭合。**
    """
    from flint.api.views import _known_regions

    whole = _ids(f"/plaza/hot?day={DAY.isoformat()}")
    covered: set[str] = set()
    for option in sorted(_known_regions()) + [_sentinel()]:
        covered |= _ids(f"/plaza/hot?day={DAY.isoformat()}&region={option}")

    assert whole, "全量是空的——这条判据在空转"
    assert covered == whole, (
        f"有簇落在所有选项之外：{sorted(whole - covered)}；"
        f"或选项之和超出了全量：{sorted(covered - whole)}"
    )


@pytest.mark.compose
def test_the_options_do_not_overlap(seeded: None) -> None:
    """选项之间**互不重叠**：一条簇只出现在一个选项里。

    重叠的话「加起来等于全量」也可能成立（多算一次、漏算一次相互抵消），
    而屏上同一条热点会在两个区里各出现一次。
    """
    from flint.api.views import _known_regions

    seen: dict[str, str] = {}
    for option in sorted(_known_regions()) + [_sentinel()]:
        for cid in _ids(f"/plaza/hot?day={DAY.isoformat()}&region={option}"):
            assert cid not in seen, f"{cid} 同时属于 {seen[cid]} 与 {option}"
            seen[cid] = option


# ───────────────────────── 三、库里两者保持可分辨（NEVER 回填）


@pytest.mark.compose
def test_the_database_still_tells_the_two_apart(seeded: None) -> None:
    """合并只在呈现层。库里 `NULL` 还是 `NULL`，`global` 还是 `global`。

    回填过的行与本来就是 `global` 的行长得一模一样——
    **抹掉之后，抹掉本身也看不见了**。
    """
    import asyncpg

    async def read() -> list[Any]:
        conn = await asyncpg.connect(DSN)
        try:
            return list(await conn.fetch(
                f"SELECT cluster_id, region FROM clusters "
                f"WHERE cluster_id LIKE '{PREFIX}%' ORDER BY cluster_id"))
        finally:
            await conn.close()

    rows = {str(r["cluster_id"]): r["region"] for r in _run(read())}

    assert rows["ur-none"] is None, "从来没归过区的那条被回填了"
    assert rows["ur-gl-1"] == "global", "global 被改写了"


def test_no_migration_backfills_null_into_global() -> None:
    """**静态守卫**：迁移目录里 NEVER 出现把 `NULL` 写成 `global` 的 UPDATE。

    上面那条是跑出来的（种子进去什么样、读出来什么样）；
    这一条挡的是**将来某次迁移**——那种回填一旦跑过就再也看不出来了，
    所以它必须在写进仓库的那一刻被拦住。

    判的是**剥掉注释之后的 SQL**：本卡在迁移里留了说明这条禁令的话，
    连注释一起扫的话，写清楚禁令的人会被自己的尺子罚（本仓第九次撞见同一形状）。
    """
    import re

    offenders: list[str] = []
    for path in sorted(MIGRATIONS.glob("*.py")):
        code = "\n".join(
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#"))
        code = re.sub(r'"""tuple.*?"""', "", code, flags=re.DOTALL)
        for match in re.finditer(r"UPDATE\s+clusters[^\"']*", code, re.IGNORECASE):
            statement = match.group(0)
            if "region" in statement and "global" in statement:
                offenders.append(f"{path.name}: {statement[:120]}")

    assert offenders == [], "迁移里有把区回填成 global 的语句：\n" + "\n".join(offenders)


# ───────────────────────── 四、`global` 本身仍然不是一个可选的区


@pytest.mark.compose
def test_global_is_still_not_a_selectable_region(seeded: None) -> None:
    """选 `global` 仍然 400。

    这不是遗漏，是本卡的立场：**`global` 不是一个地方。**
    用户选的是「未归区」——一个承认「我们不知道产地」的选项，
    而不是一个叫「全球」的地方。
    """
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region=global")

    assert resp.status_code == 400, "global 被当成了一个合法的区"


@pytest.mark.compose
def test_an_unknown_value_is_still_rejected_with_the_full_option_list(
    seeded: None,
) -> None:
    """无效值回 400，且清单里**要有未归区**——它现在是一个可选项了。

    清单漏了它的话，调用方照着报错信息把请求改一遍，还是选不到那 104 条。
    """
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region=ZZ")

    assert resp.status_code == 400
    message = resp.json()["message"]
    assert "CN" in message
    assert _sentinel() in message, f"报错信息里没有未归区这个选项：{message}"


# ───────────────────────── 五、前后端用的是同一个记号


def test_the_frontend_and_backend_agree_on_the_sentinel() -> None:
    """前端那个记号与后端逐字相同。

    两处各写一份的话，改名那天只有一处会跟上——
    而症状是「选了未归区什么都没有」，看起来像后端坏了。
    """
    assert REGIONS_TS.exists(), "前端没有一处定义这个记号"
    text = REGIONS_TS.read_text(encoding="utf-8")

    assert f'"{_sentinel()}"' in text or f"'{_sentinel()}'" in text, (
        f"前端记号与后端对不上（后端是 {_sentinel()!r}）：{text[:200]}"
    )


def test_the_option_is_labelled_as_not_a_geographic_region() -> None:
    """屏上那一项**标注它不是地理区**（acceptance③）。

    只写「未归区」三个字不够：它排在九个国家代码旁边，
    读起来像第十个国家。文案要说清它是什么。
    """
    import json

    zh = json.loads((REPO / "web" / "messages" / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((REPO / "web" / "messages" / "en.json").read_text(encoding="utf-8"))
    key = "region.unassigned.label"

    assert key in zh and key in en, f"文案 key {key} 没登记"
    assert "未归区" in zh[key]
    assert "不是" in zh[key], f"中文没说清它不是一个地理区：{zh[key]}"
    assert "not" in en[key].lower(), f"英文没说清它不是一个地理区：{en[key]}"


def test_the_switch_renders_the_label_instead_of_the_raw_sentinel() -> None:
    """下拉里显示的是文案，不是 `unassigned` 这个内部记号。

    `FB-10` 的分界：**A 类脚手架 = 开发要看的东西跑到了产品面**，
    内部 id 点名在内。
    """
    text = SWITCH.read_text(encoding="utf-8")

    assert "regionOptionLabel" in text, "下拉还是原样打印选项值"


def test_the_plaza_appends_the_option_to_the_list_from_the_backend() -> None:
    """地区清单**仍然只有一处真相**（`LOC-01`）：`GET /settings/locale`。

    未归区是**筛选面**上多出来的那一项，由广场在取到那份清单之后追加——
    NEVER 把它塞进 `options.region`：那是 locale 的词表，
    `PUT /settings/locale` 拿它校验用户偏好，塞进去等于允许把「未归区」存成一个人的常住地。
    """
    text = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "withUnassigned" in text, "广场没有把未归区追加进筛选清单"
    assert "options?.region" in text, "地区清单不再来自 /settings/locale"


def test_the_unassigned_option_never_entered_the_locale_vocabulary() -> None:
    """未归区**不是一个地区**——它 NEVER 进 `contracts_v04.Region`。

    这一条守的从来不是「那份清单有几项」，而是**未归区没混进地理词表**：
    混进去等于允许把「未归区」存成一个人的常住地
    （`PUT /settings/locale` 拿这份词表校验偏好）。

    `DEC-056` 把 HK 加进词表那天这条判据**照旧绿**——加的是一个真地区。
    改前它写的是「集合逐字等于那九个」，于是加任何真地区都会红在这里，
    而红的话与未归区没有半点关系。
    """
    from typing import get_args

    import contracts_v04.models_v04 as m
    from flint.api.views import UNASSIGNED_REGION

    vocabulary = set(get_args(m.Region))

    assert UNASSIGNED_REGION not in vocabulary
    assert "unassigned" not in vocabulary
    assert "global" not in vocabulary, "源常量也不是地区（REGION-11）"
    assert "CN" in vocabulary and "HK" in vocabulary


# ───────────────────────── 六、单据关掉


def test_the_sheet_is_closed_and_records_the_ruling() -> None:
    text = SHEET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:8])

    assert "**状态** closed" in head, f"单据还开着：{head!r}"
    assert "DEC-040" in text
    assert "REGION-11" in text
    assert "回填" in text, "单子里没记下「NEVER 把 NULL 回填成 global」这一条"
