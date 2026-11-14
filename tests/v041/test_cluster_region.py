"""REGION-08：`clusters` 加 region 列 + 回填 + 日更写入（迁移 0021）。

## 为什么必须走迁移

规格 `#2.14` 写着 `GET /plaza/hot?region=`【已建，增 query】，而端点签名只有 `day`——
FastAPI 对未声明的 query **静默忽略**，带 `region=CN` 回的是全量。
`DEC-035` 的原话：**一个静静地什么都不筛的筛选器比没有筛选器更坏**。

要真筛就得有列。实查：`clusters` 十列没有 region、`heat_points` 也没有；
region 今天只活在 `trend_items_raw`（0004）与 `flint/region/bucketing.py` 的
`RegionCluster`（模块内 dataclass，**从没落过库**）。

## 回填的那条硬规矩

`region` **随成员走、NEVER 靠簇去推断**（`bucketing.py` 自己的原话）。
撞见成员跨区的簇 → **停下上报**，NEVER 取众数：

`PRINCIPLES#B5` 说先聚后拆是拆不干净的——一旦两国报道被 embedding 合成一簇，
簇心已经是两国的平均。**回填时撞见跨区簇，说明数据面已经破了 B5**。
取众数会把这件事抹平：库里从此有一个标着 `CN` 的簇，而它的簇心是 CN 与 US 的平均，
下游按 region 取「这个区的热点」时拿到的是一个**哪个区都不存在的假热点**。

## 成员是怎么找到的

`clusters` 与 region 之间隔着三跳，本文件把它钉住：

```
cluster → evidence_cards.keyword_ids → keywords.canonical
        → canonicalize(trend_items_raw.keyword) 相同的那些原始条目 → 它们的 region
```
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "migrations" / "versions" / "0021_cluster_region.py"
MIGRATIONS = REPO / "migrations" / "versions"
BACKFILL = REPO / "flint" / "region" / "backfill.py"
INGEST = REPO / "flint" / "jobs" / "ingest.py"
BUCKETING = REPO / "flint" / "region" / "bucketing.py"

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ───────────────────────── 一、迁移本身：接号、两个方向都跑得通


def test_the_migration_continues_the_numbering() -> None:
    """接 0020，**NEVER 跳号**。

    跳号的迁移在 `alembic history` 上仍然是一条线（它按 down_revision 串），
    所以跳号不会当场报错——**它只会让下一个人算错水位**。
    """
    assert MIGRATION.exists(), "迁移 0021 不在"
    numbers = sorted(
        int(m.group(1)) for p in MIGRATIONS.glob("*.py")
        if (m := re.match(r"(\d{4})_", p.name))
    )

    # 水位跟着事实走：`LOCK-01`（第 7 批）加了 0022，本卡守的是**本迁移接 0020**
    # 与**全序无断档**，那两条一字未改——钉死一个过期的水位，
    # 只会让下一次正常落号被判成错。
    assert numbers[-1] >= 21, f"0021 不见了：{numbers}"
    assert numbers == list(range(numbers[0], numbers[-1] + 1)), f"迁移号有断档：{numbers}"


def test_the_migration_chains_onto_0020() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert re.search(r'down_revision\s*[:=].*"0020', text), "没接在 0020 后面"
    assert re.search(r'revision\s*[:=].*"0021', text)


def test_both_directions_are_implemented() -> None:
    """`downgrade` 不是摆设：加错了列要能退回去。

    只写 `upgrade` 的迁移，出问题时唯一的退路是**手写 SQL 改生产库**——
    而那正是 S2-10 要人工确认的那类操作。
    """
    text = MIGRATION.read_text(encoding="utf-8")

    assert "def upgrade()" in text and "def downgrade()" in text
    assert "add_column" in text, "upgrade 没加列"
    assert "drop_column" in text, "downgrade 没把列去掉"


def test_the_column_is_nullable_on_purpose() -> None:
    """列**可空**，而且这是有意的。

    非空的话，回填就必须给每一条都填一个值——包括那些**成员里根本没有 region**
    的簇。那会逼出一个默认值，而默认值就是「猜一个区」，
    正是本卡 acceptance③ 禁止的事。`NULL` 的意思是「还不知道」，它说的是实话。
    """
    text = MIGRATION.read_text(encoding="utf-8")

    assert "nullable=True" in text, "region 列被写成非空——那会逼出一个默认区"
    assert "server_default" not in text, "给了默认值 = 给每个簇猜了一个区"


# ───────────────────────── 二、region 随成员走（本卡的核心）


def test_a_single_region_cluster_takes_that_region() -> None:
    from flint.region.backfill import region_of_members

    assert region_of_members("c1", ["CN", "CN", "CN"]) == "CN"


def test_a_cluster_with_no_member_region_stays_unknown() -> None:
    """成员一个 region 都没有 → `None`（不知道），NEVER 挑一个。"""
    from flint.region.backfill import region_of_members

    assert region_of_members("c1", []) is None


def test_a_cross_region_cluster_stops_the_backfill() -> None:
    """**本卡最要紧的一条**：成员跨区 → 抛错并点名，NEVER 取众数。

    多数派看起来是「合理的近似」，而它抹掉的正是**数据面已经破了 B5** 这个信号。
    """
    from flint.region.backfill import CrossRegionClusterError, region_of_members

    with pytest.raises(CrossRegionClusterError) as err:
        region_of_members("c-42", ["CN", "CN", "CN", "US"])

    message = str(err.value)
    assert "c-42" in message, "没点名是哪个簇——那让人无从去查"
    assert "CN" in message and "US" in message, "没说清是哪几个区撞上了"


def test_the_majority_is_never_taken() -> None:
    """**阴性对照**：三票 CN 一票 US，NEVER 回 `CN`。

    没有这一条，上面那条判据换成 `return Counter(...).most_common(1)` 之后
    仍然会抛（只要实现里留着那个 raise），而真正的错法是**先取众数再不抛**。
    """
    from flint.region.backfill import CrossRegionClusterError, region_of_members

    for members in (["CN"] * 9 + ["US"], ["US", "CN"]):
        with pytest.raises(CrossRegionClusterError):
            region_of_members("c1", members)

    # `DEC-058` 之后源常量不参与定区，所以「5 个 global + 1 个 CN」不再是跨区。
    # **这一例翻面之后反而更硬**：`global` 在这里是**多数**，
    # 而结果是 `CN`——也就是说连「按多数」这条错法都被这一例挡住了。
    assert region_of_members("c1", ["global"] * 5 + ["CN"]) == "CN"

    # 而真区之间的多数照旧不取：混进源常量也救不了它。
    with pytest.raises(CrossRegionClusterError):
        region_of_members("c1", ["global"] * 5 + ["CN"] * 3 + ["US"])


def test_the_rule_is_quoted_from_bucketing_not_reinvented() -> None:
    """口径出处在 `bucketing.py`——本模块 NEVER 另立一套 region 归属规则。

    两套归属规则的后果不是重复，而是**同一个簇在回填与日更里被归到两个区**。
    """
    text = BACKFILL.read_text(encoding="utf-8")

    assert "bucketing" in text, "没写明口径出自哪里"
    assert "随成员走" in text
    # 判**引入面**而不是全文：本模块的 docstring 里逐字写着
    # 「与 CrossRegionLineageError 刻意不共用类型」——判全文的话，
    # 判据会把**解释为什么不复用的那句话**当成复用本身。
    imported = re.findall(r"^\s*(?:from|import)\s+.*$", text, re.MULTILINE)
    assert not any("CrossRegionLineageError" in line for line in imported), (
        "复用了血缘那个异常——血缘跨区与簇成员跨区是两件事，"
        "共用一个类型会让上报的人分不清撞的是哪一条"
    )


def test_the_existing_lineage_rule_still_stands() -> None:
    """acceptance⑤：血缘不跨区的既有判据不倒。"""
    from flint.region.bucketing import CrossRegionLineageError

    assert issubclass(CrossRegionLineageError, Exception)
    assert "link_lineage" in BUCKETING.read_text(encoding="utf-8")


# ───────────────────────── 三、回填走真栈（库 → 三跳 → region）


@pytest.fixture()
def seeded() -> Any:
    import asyncpg

    vec = "[" + ",".join(["0"] * 1024) + "]"

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM evidence_cards WHERE cluster_id LIKE 'rg-%'")
            await conn.execute("DELETE FROM clusters WHERE cluster_id LIKE 'rg-%'")
            await conn.execute("DELETE FROM keywords WHERE keyword_id LIKE 'rg-kw%'")
            await conn.execute(
                "DELETE FROM trend_items_raw WHERE keyword LIKE 'rgseed%'")
        finally:
            await conn.close()

    async def seed() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for cid in ("rg-cn", "rg-mixed", "rg-orphan"):
                await conn.execute(
                    "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                    "centroid, status, first_seen, last_active, parent_cluster_ids, "
                    "merged_into, aliases) VALUES ($1, $1, 'cat-ai', $2::vector, "
                    "'active', '2026-07-01', '2026-07-01', '[]'::jsonb, NULL, '[]'::jsonb)",
                    cid, vec)
            # 词面 `rgseed…` 已是规范形，canonicalize 之后仍是它自己 —— 三跳可闭合。
            for kw_id, canonical in (("rg-kw-a", "rgseedalpha"), ("rg-kw-b", "rgseedbeta")):
                await conn.execute(
                    "INSERT INTO keywords (keyword_id, canonical, lang, aliases, "
                    "embedding, first_seen) VALUES ($1, $2, 'en', '[]'::jsonb, "
                    "$3::vector, '2026-07-01')", kw_id, canonical, vec)
            for cid, kws in (("rg-cn", ["rg-kw-a"]), ("rg-mixed", ["rg-kw-a", "rg-kw-b"]),
                             ("rg-orphan", ["rg-kw-missing"])):
                await conn.execute(
                    "INSERT INTO evidence_cards (card_id, cluster_id, keyword_ids, "
                    "flags, top_links) VALUES ($1, $2, $3::jsonb, '[]'::jsonb, '[]'::jsonb)",
                    f"card-{cid}", cid,
                    "[" + ",".join(f'"{k}"' for k in kws) + "]")
            # `item_index` 用**枚举序**，NEVER 用 `hash(keyword)`：
            # Python 的字符串 hash **逐进程随机**（PYTHONHASHSEED），
            # 于是同一份种子在两次运行里落到不同的主键上，还可能自撞——
            # 而它撞的时候报的是 `UniqueViolationError`，
            # 读起来像「上一轮没清干净」，与真正的清理漏洞长得一模一样。
            for index, (keyword, region) in enumerate(
                    (("rgseedalpha", "CN"), ("rgseedbeta", "US")), start=900):
                await conn.execute(
                    "INSERT INTO trend_items_raw (day, source_id, item_index, keyword, "
                    "score, region, url, captured_at) VALUES ('2026-07-01', 'weibo', "
                    "$1, $2, 1.0, $3, 'http://x', now())",
                    index, keyword, region)
        finally:
            await conn.close()

    _run(wipe())
    _run(seed())
    yield
    _run(wipe())


def _plan() -> Any:
    import asyncpg

    from flint.region.backfill import plan_cluster_regions

    async def go() -> Any:
        conn = await asyncpg.connect(DSN)
        try:
            return await plan_cluster_regions(conn, only_prefix="rg-")
        finally:
            await conn.close()

    return _run(go())


@pytest.mark.compose
def test_the_backfill_resolves_a_single_region_cluster(seeded: None) -> None:
    plan = _plan()

    assert plan.assigned["rg-cn"] == "CN"


@pytest.mark.compose
def test_the_backfill_reports_the_cross_region_cluster_by_name(seeded: None) -> None:
    """跨区簇进 `conflicts` 并点名，**NEVER 进 assigned**。

    进了 assigned 就等于取了个数——哪一个都行，而它们都是错的。
    """
    plan = _plan()

    assert "rg-mixed" in plan.conflicts, "跨区簇没被报出来"
    assert "rg-mixed" not in plan.assigned, "跨区簇被填了一个区"
    assert set(plan.conflicts["rg-mixed"]) == {"CN", "US"}


@pytest.mark.compose
def test_a_cluster_whose_members_carry_no_region_is_left_null(seeded: None) -> None:
    """三跳断了的簇留 `NULL` 并进 `unknown`——NEVER 猜，也 NEVER 静静跳过。"""
    plan = _plan()

    assert "rg-orphan" in plan.unknown
    assert "rg-orphan" not in plan.assigned


@pytest.mark.compose
def test_the_column_really_exists_after_the_migration(seeded: None) -> None:
    """迁移真的跑过：列在库里。"""
    import asyncpg

    async def go() -> Any:
        conn = await asyncpg.connect(DSN)
        try:
            return await conn.fetchval(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'clusters' AND column_name = 'region'")
        finally:
            await conn.close()

    assert _run(go()) is not None, "clusters 还没有 region 列——迁移没跑"


@pytest.mark.compose
def test_applying_the_plan_writes_only_the_resolved_ones(seeded: None) -> None:
    import asyncpg

    from flint.region.backfill import apply_cluster_regions

    plan = _plan()          # 先算完再进事件循环：`_plan` 自己是 `asyncio.run`

    async def go() -> Any:
        conn = await asyncpg.connect(DSN)
        try:
            await apply_cluster_regions(conn, plan)
            rows = await conn.fetch(
                "SELECT cluster_id, region FROM clusters WHERE cluster_id LIKE 'rg-%'")
            return {r["cluster_id"]: r["region"] for r in rows}
        finally:
            await conn.close()

    got = _run(go())
    assert got["rg-cn"] == "CN"
    assert got["rg-mixed"] is None, "跨区簇被写进库了"
    assert got["rg-orphan"] is None


# ───────────────────────── 四、日更写入：NEVER 留一条只在回填时才有区的路


def test_the_daily_ingest_writes_region_for_new_clusters() -> None:
    """acceptance④。

    只回填不写日更的话，**今天之后新建的每一个簇都没有区**——
    而广场那个筛选器会把它们全部漏掉，看起来像「这个区今天没热点」。
    """
    text = INGEST.read_text(encoding="utf-8")
    upsert = text[text.index("async def _upsert_cluster"):]
    upsert = upsert[: upsert.index("\n\n\n")]

    assert "region" in upsert, "日更写簇时没带 region"
    assert "INSERT INTO clusters" in upsert and "region" in upsert.split("VALUES")[0], (
        "region 不在 INSERT 的列清单里"
    )


def test_the_daily_ingest_uses_the_same_rule_not_a_second_one() -> None:
    """日更判区**转调** `flint/region/backfill.py` 的那一个函数。

    自己写一遍的后果不是重复，而是同一个簇在回填与日更里被归到两个区——
    而两次归档之间没有任何东西会告诉你它变过。
    """
    text = INGEST.read_text(encoding="utf-8")

    assert "region_of_members" in text, "日更没转调既有归属规则"


# ───────────────────────── 五、回填在真库上的实况（撞车那一条要留着证据）


@pytest.mark.compose
def test_the_conflict_found_on_the_demo_db_is_on_file() -> None:
    """回填在 demo 库上撞见一条跨区簇——**单子必须在，且必须还开着**。

    它撞的不是「CN 与 US」，而是「有区」与「不适用」：`ghtrend` 把 region
    写死成 `global`（源不分区），`gtrends` 给的是真的区。两种断言同住一列。

    **改前这条断言单据仍然 open**——`DEC-040`（owner 2026-08-08）裁完、
    `REGION-11` 执行之后它红了：**红的是自己描述的那个状态过去了**。

    这条判据守的是**那个发现不被弄丢**，那一条一字未改：单子关了，
    但「哪个簇、`ghtrend` 把 region 写死成 `global`、两种断言同住一列」
    这三样必须还在文里——它们是这次裁决的全部依据。
    """
    sheet = REPO / "docs" / "blocked" / (
        "REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md")

    assert sheet.exists(), "跨区簇的发现没有单"
    text = sheet.read_text(encoding="utf-8")
    state = next(ln for ln in text.splitlines()[:6] if ln.startswith("**状态**"))

    assert state.startswith("**状态** closed"), f"单据状态不对：{state!r}"
    assert "DEC-040" in text and "REGION-11" in text, "关单没写依据与执行卡"
    assert "c-20260629-108" in text, "单子里没点名是哪个簇"
    assert "ghtrend" in text and "global" in text, "单子里没说清两种断言撞在哪"


def test_the_two_source_region_semantics_are_still_different() -> None:
    """**这张单子的前提是可复核的**：两个源给 region 的方式确实不是一回事。

    判源码而不是判单子里的转述——哪天 `ghtrend` 不再写死 `global` 了，
    这条会红，那正是该回去关单的时候。
    """
    ghtrend = (REPO / "flint" / "sources" / "ghtrend.py").read_text(encoding="utf-8")
    weibo = (REPO / "flint" / "sources" / "weibo.py").read_text(encoding="utf-8")
    gtrends = (REPO / "flint" / "sources" / "gtrends.py").read_text(encoding="utf-8")

    # `DEC-058` 之后 `ghtrend` 不再自带字面量，而是引用**那一处真相**
    # （`flint/region/source_constants.py`）——**它写的仍然是源常量**，
    # 语义一个字没变，所以那张单**不该关**。
    #
    # 改前这里判的是字面量 `region="global"`，于是「搬走副本」这件事
    # 会被它读成「ghtrend 不再写死 global 了」。判据要判的是**语义**：
    # ghtrend 写的是一个源常量，而不是一个地方。
    assert "SOURCE_CONSTANT_REGIONS" in ghtrend, (
        "ghtrend 不再写源常量了——那时才该回去关那张单")
    assert "region=" in ghtrend
    assert 'region="CN"' in weibo
    assert "region=self._region" in gtrends, "gtrends 不再按区取了"


def test_a_cross_region_cluster_never_kills_the_whole_day() -> None:
    """日更撞见跨区簇 → 那一条留 `NULL` 并大声记一笔，**NEVER 终止当天**。

    这一条是本卡开工后**改出来的**：第一版让 `region_of_members` 的异常直接冒到
    日更批里，于是 `tests/m1` 的 30 天回放整批红了——一条簇跨区把当天
    **其余全部热点**一起丢掉。

    两处的正确处置不一样，而这不是双重标准：
    **回填是一次性动作**，停下来给人看是对的（证据还在库里，随时能重跑）；
    **日更是每天跑的批**，停下来的代价是那一天没有热点，而缺一个区标记的代价
    只是那一条簇不参与区筛选。
    """
    text = INGEST.read_text(encoding="utf-8")
    section = text[text.index("except CrossRegionClusterError"):]
    section = section[: section.index("await _upsert_cluster")]

    assert "region = None" in section, "跨区时没有留 NULL"
    assert "region_conflicts[" in section, "跨区的簇没被记下来"
    assert "warning" in section, "跨区没有告警——那就成了一次静默的降级"
    assert "most_common" not in text and "Counter" not in text, "日更里出现了取众数"
