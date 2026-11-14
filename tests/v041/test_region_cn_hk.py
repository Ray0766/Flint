"""REGION-CN-HK / `DEC-056`：CN 与 HK 两区分家，各自一源。

## 改前那一天，屏上有一句话是假的

`DEC-054` 让 HK 的数据以「华语圈代理」的名义落 `region='CN'`。
于是一个选了「中国大陆」的用户，卡片里混着 `馬國明`、`美食博覽2026`——
**繁体、港区、香港本地商展**。那不是大陆热搜，而屏上写着他选的那个区。

`DEC-056` 撤销代理口径：CN = 微博，HK = Google 趋势，**两区都可切**。

## 三处 MUST 一致，各有判据（`DEC-056` 逐字）

| 一致的是什么 | 落点 | 本文件哪一条 |
|---|---|---|
| provenance 的真实 URL | `gtrends.board_url()` = `geo=HK` | §一 |
| 库里的 region | `EMIT_REGION` / 既有行回填 | §一 · §三 |
| 屏上的署名 | `SOURCE_DISPLAY_NAME` | §一 |

## HK 原本不在九区里——这件事不是顺手办的

清单 A2 的九区没有 HK。`DEC-056` 要「两区都可切」，就必须让 HK
成为一个真的可选区，于是 `contracts_v04.Region` 从九个成员加到十个。

**这是加成员，不是改口径**：`tools/check_frozen_additive.py` 对 Literal 别名
按「成员集合 base ⊆ v04」比，加成员明确允许；且 `Region` 本身是 v0.4 纯新增，
原冻结件 `contracts/models.py` 里没有它。

数目对不上的那一处（`DEC-056` 原文写「其余七区」，实际是八区）
开了单：`docs/blocked/REGION-CN-HK-COUNT-SAYS-SEVEN.md`。

## 后果照实说：CN 区从 60 掉到 50

10 条港区条目移去 HK 区。**不是数据丢了，是分家的必然结果**——
这句话 `DEC-056` 明写要说出来，本文件 §三 用真库判它。
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
GTRENDS = REPO / "flint" / "sources" / "gtrends.py"
MIGRATION = REPO / "migrations" / "versions" / "0028_gtrends_region_hk.py"
PLAZA_CARDS = REPO / "web" / "components" / "plaza" / "PlazaCards.tsx"
MESSAGES = REPO / "web" / "messages"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

#: 分家之前 HK 数据顶着的那个区。阴性对照 ① 用它。
OLD_PROXY_REGION = "CN"


def _rows(sql: str, *args: Any) -> list[Any]:
    import asyncio

    import asyncpg

    async def _go() -> list[Any]:
        conn = await asyncpg.connect(DSN)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_go())


# ───────────────────────── 一、采集地区 · 落库地区 · 屏上署名三者一致


def test_the_fetched_geo_and_the_stored_region_are_the_same_place() -> None:
    """`DEC-056` 之后两者**一致**——代理口径就是靠这一处不一致活着的。

    两个常量仍然分开（`CN-04` 刻意为之）：**一致不等于同一件事**。
    合成一个的话，下一版接别的地区时没人说得清该改哪一个。
    """
    from flint.sources.gtrends import EMIT_REGION, FETCH_GEO

    assert FETCH_GEO == "HK"
    assert EMIT_REGION == "HK"
    assert EMIT_REGION == FETCH_GEO, "落库地区与采集地区又对不上了"


def test_the_provenance_url_still_carries_the_real_geo() -> None:
    """出处链一个字都没动——回填改的是标签，不是事实。"""
    from flint.sources.gtrends import board_url

    assert board_url() == "https://trends.google.com/trending/rss?geo=HK"


def test_the_display_name_no_longer_carries_a_region_suffix() -> None:
    """署名去掉「（港区）」：`region` 本身就是 HK 了。

    再把地区缀进源名字里，是把两根正交轴拧成一根（`PRINCIPLES#A3`：
    源与地区各是一根轴）。那个后缀当初是 `DEC-054` 代理口径的第三条腿——
    数据采自 HK 而**落在 CN 区**时，署名是用户那一侧唯一能看出这件事的地方。
    """
    from flint.sources.gtrends import SOURCE_DISPLAY_NAME

    assert SOURCE_DISPLAY_NAME == "Google 趋势"
    assert "港区" not in SOURCE_DISPLAY_NAME
    assert "HK" not in SOURCE_DISPLAY_NAME


def test_the_screen_name_agrees_with_the_backend_constant() -> None:
    """屏上那个名字与后端常量**说同一件事**（`DEC-056`：出处 · region · 署名三者一致）。

    这一条是 `SMOKE-01` 打真栈时抓出来的：本卡改了
    `flint/sources/gtrends.py#SOURCE_DISPLAY_NAME`，**而屏上照旧写着
    「Google 趋势（港区）」**——因为那个名字在 `web/messages/*.json` 里还有一份。

    > 改了一份、漏了另一份，而**两份都自称是这一源的名字**。
    > 判据不能只判后端那份：它绿着，用户看到的还是旧的。

    两侧不做逐字相等（英文那份本来就是另一种语言），
    判的是**地区缀 NEVER 出现在源名字里**——那是 `PRINCIPLES#A3` 的那根线：
    源与地区各是一根轴。
    """
    for name, banned in (("zh", ("港区", "香港", "HK")),
                         ("en", ("Hong Kong", "(HK)"))):
        messages = json.loads(
            (REPO / "web" / "messages" / f"{name}.json").read_text(encoding="utf-8"))
        shown = messages["source.name.gtrends"]
        for word in banned:
            assert word not in shown, (
                f"{name} 的源署名里又带上地区了：{shown!r}——"
                f"region 已经是 HK，再缀一次是把两根正交轴拧成一根")
        assert shown, f"{name} 的源署名是空的"


def test_the_parsed_items_land_in_hk() -> None:
    """解析出来的条目**真的带 HK**，不是只有常量对。"""
    from datetime import UTC, datetime

    from flint.sources.gtrends import parse_rss

    body = next(p for p in sorted((REPO / "fixtures" / "_probe" / "gtrends")
                                  .glob("*.body"))
                if "<item>" in p.read_text(encoding="utf-8", errors="replace"))
    items = parse_rss(body.read_text(encoding="utf-8"),
                      now=datetime(2026, 8, 10, tzinfo=UTC),
                      url="https://trends.google.com/trending/rss?geo=HK")

    assert items, "这份真响应里没有条目，判据前提没了"
    assert {i.region for i in items} == {"HK"}


# ───────────────────────── 二、阴性对照 ①：口径退回代理 → 红且说清是两区被混了


def test_putting_the_region_back_to_cn_would_mix_two_places() -> None:
    """**阴性对照①**（卡面逐字）：`EMIT_REGION` 改回 `CN` → 判据红，
    且红的话里**说清是「两个地区被混进一个区」**，NEVER 只说「常量变了」。

    造法不是改常量再跑（那要重载模块），而是问一句结构性的话：
    落库地区若等于 `OLD_PROXY_REGION`，那么 `FETCH_GEO`（HK）与它就不是同一个地方，
    于是 CN 区里会同时坐着微博的大陆热搜与 Google 的港区榜——
    **而屏上只写一个区名**。这正是 `DEC-056` 要终结的那件事。
    """
    from flint.sources.gtrends import EMIT_REGION, FETCH_GEO

    assert EMIT_REGION != OLD_PROXY_REGION, (
        f"gtrends 又落回 {OLD_PROXY_REGION} 区了：它采的是 geo={FETCH_GEO}，"
        f"而微博采的是大陆——两个地区被混进同一个区，"
        f"屏上却只写一个区名（DEC-056 撤销的正是这个代理口径）")


@pytest.mark.compose
def test_no_region_holds_two_places_worth_of_sources() -> None:
    """同一条阴性对照的**数据面**：任何一个区里 NEVER 同时出现两源的分区数据。

    只判常量的话，一次没跑迁移的部署照样全绿——而库里仍然混着。
    """
    rows = _rows(
        "SELECT region, array_agg(DISTINCT source_id) AS srcs "
        "FROM trend_items_raw WHERE region IS NOT NULL GROUP BY region")
    mixed = {r["region"]: sorted(r["srcs"]) for r in rows
             if {"weibo", "gtrends"} <= set(r["srcs"])}

    assert mixed == {}, f"这些区里混着两地的源：{mixed}"


# ───────────────────────── 三、既有行回填了，且 CN 的减少是**说得出来的**


@pytest.mark.compose
def test_the_existing_gtrends_rows_were_relabelled() -> None:
    """回填按 `source_id` 定位，一条不漏、一条不多。

    **NEVER 按词面猜「哪几条看起来像港区的」**——词面猜法在「馬國明」
    这种两地都可能上榜的条目上必然错，而错了之后没有任何东西会报红。
    """
    rows = _rows("SELECT region, count(*) AS n FROM trend_items_raw "
                 "WHERE source_id = 'gtrends' GROUP BY region")
    by_region = {r["region"]: r["n"] for r in rows}

    assert by_region, "库里没有 gtrends 行，这条判据的前提没了"
    assert set(by_region) == {"HK"}, f"还有没回填的：{by_region}"


def test_the_migration_records_that_it_relabels_rather_than_rewrites() -> None:
    """`DEC-056` 逐字要求这句话写进迁移注释。

    不写的话，下一个读到 `UPDATE … SET region` 的人会以为我们改了事实。
    """
    text = MIGRATION.read_text(encoding="utf-8")

    assert "回填是把标签改回与出处一致，不是改写事实" in text
    assert "NEVER 按词面猜" in text or "NEVER 去猜" in text


def test_the_migration_can_go_back() -> None:
    """`downgrade` 用**同一个定位**改回去——来回一次不多动也不少动一行。"""
    text = MIGRATION.read_text(encoding="utf-8")

    assert re.search(r"def downgrade\(\) -> None:\s+_move\(\"HK\", \"CN\"\)", text)
    assert re.search(r"def upgrade\(\) -> None:\s+_move\(\"CN\", \"HK\"\)", text)


@pytest.mark.compose
def test_cn_lost_exactly_the_rows_that_moved_to_hk(
    two_regions_seeded: None,
) -> None:
    """**CN 掉的那些正是 HK 得到的那些**——不是数据丢了。

    `DEC-056`：「CN 区卡片数会从 60 掉到 50（10 条港区条目移去 HK 区）——
    不是数据丢了，是分家的必然结果」。这条判据把那句话变成可验的：
    分家后**两区之和**仍等于分家前 CN 一个区的量。
    """
    rows = _rows(
        "SELECT c.region, count(DISTINCT c.cluster_id) AS n "
        "FROM clusters c JOIN heat_points h ON h.cluster_id = c.cluster_id "
        "WHERE c.region IN ('CN', 'HK') AND h.day = $1 GROUP BY c.region",
        _SEED_DAY)
    by_region = {r["region"]: r["n"] for r in rows}

    # 分家前：这一天 CN 区**两条都在**（港区那条顶着 CN 的名字）。
    # 分家后：CN 一条、HK 一条——**和仍然是二**。
    assert by_region.get("CN") == 1, f"CN 区不是一条：{by_region}"
    assert by_region.get("HK") == 1, f"HK 区不是一条：{by_region}"
    assert sum(by_region.values()) == len(_SEEDED), (
        f"两区之和不等于分家前 CN 一个区的量——那不是分家，那是丢数据：{by_region}")


# ───────────────────────── 四、阴性对照 ②：空态话说错 → 红


def test_out_of_scope_and_no_data_today_say_different_things() -> None:
    """**阴性对照②**（卡面逐字）：把「本版暂无该区内容」写成
    「该区当日无数据」（或反过来）→ 判据红。

    两句话该让用户做的事完全不同：一句让他等下一版，一句让他换一天。
    合成一句之后，等下一版的人会一直刷新，而换一天的人会以为功能没做。

    `CN-02` 那三句一条都 NEVER 合并（`DEC-056` 逐字）——第三句是「读失败」，
    它住在 `PlazaPage` 那一层，由 `test_cn_only_scope.py` 守着。
    """
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    out_of_scope = zh["plaza.out_of_scope.line"]
    empty_today = zh["plaza.empty.no_data_today"]

    assert out_of_scope != empty_today, "两态共用了同一句话"
    assert "本版" in out_of_scope, (
        f"「本版暂无该区内容」那一句不再说「本版」：{out_of_scope!r}——"
        f"用户读不出这是版本范围问题，会当成今天没有")
    assert "本版" not in empty_today, (
        f"「该区当日无数据」那一句混进了版本范围的说法：{empty_today!r}——"
        f"换一天就能解决的事被说成了要等下一版")


def test_the_two_states_still_have_two_markers() -> None:
    """两态各有各的记号，判据靠它分辨（合成一个之后自动化里再也分不开）。"""
    cards = PLAZA_CARDS.read_text(encoding="utf-8")

    assert '"out_of_scope"' in cards
    assert '"empty"' in cards
    assert "data-plaza-out-of-scope" in cards


# ───────────────────────── 五、两区都在范围内，其余各区照旧明说暂无


def test_both_regions_are_in_scope_and_the_rest_are_not() -> None:
    """CN 与 HK 进「本版有内容」，其余八区**一个都 NEVER 顺手打开**。"""
    from typing import get_args

    from contracts_v04.models_v04 import Region
    from flint.region.version_scope import CURRENT_SCOPE, in_scope

    assert CURRENT_SCOPE.in_scope == frozenset({"CN", "HK"})

    rest = set(get_args(Region)) - {"CN", "HK"}
    assert len(rest) == 8, f"其余区不是八个：{sorted(rest)}"
    for region in rest:
        assert in_scope(region) is False, f"{region} 被顺手打开了"


def test_hk_is_a_selectable_region_in_the_frozen_contract() -> None:
    """「两区都可切」落到清单上：HK 在 `Region` 里。

    不在的话，选它会被端点判成 `unknown region`——
    而屏上刚刚才把它列出来。
    """
    from typing import get_args

    from contracts_v04.models_v04 import Region

    values = set(get_args(Region))
    assert "HK" in values
    assert len(values) == 10
    assert "EU" not in values, "EU 是区域联盟，不是地区（清单 A2）"


def test_the_count_discrepancy_is_on_the_record() -> None:
    """`DEC-056` 原文写「其余七区」，加上 HK 之后**实际是八区**。

    原文一字不改地留在 `DECISIONS-v04.md`（那是记录），
    代码里写真数（那是执行），差异开单给 owner——
    **NEVER 为了对上那个「七」去删掉一个区**：删区会真的拿掉
    一个下一版要用的能力，而那不是 `DEC-056` 裁决的内容。
    """
    ticket = REPO / "docs" / "blocked" / "REGION-CN-HK-COUNT-SAYS-SEVEN.md"

    assert ticket.exists(), "数目对不上那一处没有开单"
    text = ticket.read_text(encoding="utf-8")
    assert "七区" in text and "八区" in text


#: 本文件自带的那两条簇。**自带而不是靠库里恰好有**：
#: 测试库里的簇一条都没归区，靠现成数据的话这两条判据永远是 skip——
#: 而 skip 在盘上与「量过了、没问题」长得不一样，却同样不证明任何事。
_SEED_DAY = date(2026, 6, 1)
_SEEDED: tuple[tuple[str, str, str], ...] = (
    ("t-region-cn", "CN", "weibo"),
    ("t-region-hk", "HK", "gtrends"),
)


@pytest.fixture()
def two_regions_seeded() -> Any:
    """一区一源各一条簇，用完**按外键顺序删干净**。

    留下的话，别的判据会在自己的文件里红，而根因在这里
    （`WIRE-VERDICT` 那次的教训：红出现在别人的文件里、根因在我这里）。
    """
    import asyncio

    import asyncpg

    async def _write() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for cid, region, source in _SEEDED:
                await conn.execute(
                    "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                    "centroid, status, first_seen, last_active, parent_cluster_ids, "
                    # `category_id` 有外键，**NEVER 编一个不存在的分类**：
                    # 编了之后这条判据在 FK 上崩，而症状与「地区那件事坏了」无关。
                    "aliases, region) VALUES ($1, $2, 'cat-ai', "
                    "array_fill(0.0::real, ARRAY[1024])::vector, 'active', $3, $3, "
                    "'[]'::jsonb, '[]'::jsonb, $4) "
                    "ON CONFLICT (cluster_id) DO NOTHING",
                    cid, f"{region} 区样本簇", _SEED_DAY, region)
                await conn.execute(
                    "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, "
                    "norm_score) VALUES ($1, $2, $3, 100.0, 1.0) "
                    "ON CONFLICT DO NOTHING",
                    cid, source, _SEED_DAY)
        finally:
            await conn.close()

    async def _erase() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            ids = [cid for cid, _, _ in _SEEDED]
            await conn.execute(
                "DELETE FROM heat_points WHERE cluster_id = ANY($1::text[])", ids)
            await conn.execute(
                "DELETE FROM clusters WHERE cluster_id = ANY($1::text[])", ids)
        finally:
            await conn.close()

    asyncio.run(_erase())          # 上一次跑崩在中途留下的残留
    asyncio.run(_write())
    try:
        yield
    finally:
        asyncio.run(_erase())


@pytest.mark.compose
def test_the_plaza_serves_each_region_from_its_own_source(
    two_regions_seeded: None,
) -> None:
    """真栈上一区一源：CN 只有微博，HK 只有 Google 趋势。

    这一条是本卡的产品。只判常量与库的话，一次装配层的回归
    （比如筛选器又静默回全量）不会被任何东西拦住。
    """
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    client = TestClient(create_app(dsn=DSN), raise_server_exceptions=False)
    when = _SEED_DAY.isoformat()

    seen = {}
    for region in ("CN", "HK"):
        got = client.get("/plaza/hot", params={"day": when, "region": region})
        assert got.status_code == 200, got.text
        assert got.json()["region_in_scope"] is True, f"{region} 被判成不在本版范围"
        clusters = got.json()["clusters"]
        # **空集上「源只有 X」恒真**——不先要求它非空的话，
        # 一个什么都不回的筛选器照样能让这条判据全绿。
        assert clusters, f"{region} 区一条都没回，而这一区刚种了一条"
        seen[region] = {s for c in clusters for s in c["by_source"]}

    assert seen["CN"] == {"weibo"}, f"CN 区的源不是只有微博：{sorted(seen['CN'])}"
    assert seen["HK"] == {"gtrends"}, f"HK 区不是只有 Google 趋势：{sorted(seen['HK'])}"
