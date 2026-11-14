"""REGION-12：`SourceColumns` 拿到的是**原文词面**，不是分数。

## `PLAZA-02` 那张单剩下的最后一条缺口

缺口一（`region` query）由 `REGION-08/09/10` 建成。缺口二是这个：

```ts
SourceStatement { sourceId: string; region: string; text: string }
                                                    ^^^^ 契约逐字：「原文；NEVER 是译文」
```

而广场每个源手上只有**分值**（`by_source`）与**地区**（`by_source_region`）。
把分值塞进 `text`，就是拿一个已经有主的槽去说另一件事
（`DEC-034` / `DEC-038` 反复禁的那一条）——屏上会出现一列「来源说法」写着 `100.0`。

真正缺的是 `trend_items_raw.keyword`：微博说「脑机接口」、GitHub 说 `bci`，
**同一个热点两种说法**。那正是 `PRINCIPLES#B4` 要的东西——
两国对同一件事说法不一致时，读者失去「谁说的」就失去了唯一能判断可信度的东西。

## 本卡 NEVER 改 `SourceColumns` 本身

`web/components/source-columns/` 是 v0.4 已 verified（`HOTSPOT-07`，2026-08-02）。
`worker.md` §9.2 / `DEC-021`：**已 verified 的实现与判据 NEVER 再改**。

所以「词面缺失时如实标注缺」这一条落在**调用方**：
缺词面的源 NEVER 被塞一个占位串进 `text`（那个槽契约上是原文），
而是由 `ClusterSourceLines` 另起一行如实说「这些源的原话没查到」。

## 逐字是这张卡的核心

`clean()` 会把空白与全半角归一——那是**入库前**的事。
词面回给屏上时 NEVER 再归一化一次：微博那条 `#高考录取结果#` 带着井号，
去掉井号之后它就不再是微博说的那句话了。
`test_the_wording_is_verbatim_not_normalised` 用一条带首尾空格与全角括号的种子钉这件事。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
VIEWS = REPO / "flint" / "api" / "views.py"
COLUMNS = REPO / "web" / "components" / "source-columns" / "SourceColumns.tsx"
LINES = REPO / "web" / "components" / "plaza" / "ClusterSourceLines.tsx"
BLACKLIST = REPO / "flint" / "region" / "by_source_region.py"
SHEET = (REPO / "docs" / "blocked"
         / "PLAZA-02-REGION-QUERY-AND-SOURCE-REGION-NOT-BUILT.md")

DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DAY = date(2026, 7, 22)
VEC = "[" + ",".join(["0"] * 1024) + "]"

# 一个**两源分歧**的簇：两个源对同一件事各说各的话，且分属两个区。
# 这正是 B4 要的那种情形——只有一个源的话，「把话还给说话的人」无从演示。
CLUSTER = "sc-brain"
WORDINGS: tuple[tuple[str, str, str], ...] = (
    # (source_id, region, 原文词面)
    ("weibo", "CN", "  ＃脑机接口＃ 临床试验  "),   # 首尾空格 + 全角井号：逐字判据用
    ("ghtrend", "US", "brain-computer-interface"),
)
# 第三个源有热度、**没有词面**（它当天的原始条目找不回来）——如实标注缺的那一条。
SOURCE_WITHOUT_WORDING = "gtrends"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _canonical_of(raw: str) -> str:
    """种子里的 `keywords.canonical` **用产线那个函数算出来**，NEVER 手写一个。

    手写的话，这份种子会与真实数据的形状悄悄分家：
    判据绿着，而线上那条链一条词面都对不上——
    **而「对不上」的症状是屏上什么都不显示，看起来像没数据。**
    """
    from flint.api.views import _term_map
    from flint.norm.canonical import canonicalize

    return canonicalize(raw, _term_map()).canonical


@pytest.fixture()
def seeded() -> Any:
    import asyncpg

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            for table, col in (("heat_points", "cluster_id"), ("clusters", "cluster_id"),
                               ("evidence_cards", "cluster_id")):
                await conn.execute(f"DELETE FROM {table} WHERE {col} LIKE 'sc-%'")
            await conn.execute("DELETE FROM keywords WHERE keyword_id LIKE 'sc-kw-%'")
            await conn.execute("DELETE FROM trend_items_raw WHERE day = $1", DAY)
            await conn.execute("DELETE FROM lineage_results WHERE day = $1", DAY)
        finally:
            await conn.close()

    async def seed() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute(
                "INSERT INTO clusters (cluster_id, canonical_name, category_id, "
                "centroid, status, first_seen, last_active, parent_cluster_ids, "
                "merged_into, aliases, region) VALUES ($1, $1, 'cat-ai', $2::vector, "
                "'active', '2026-07-01', $3, '[]'::jsonb, NULL, '[]'::jsonb, 'CN')",
                CLUSTER, VEC, DAY)
            # 两个源两种说法 → 两个 canonical → **两个 keyword 落进同一个簇**。
            # 这正是真实形态：ingest 先 canonicalize 原始词面，再靠 embedding
            # 把它们聚到一起。种一个 keyword 顶两条的话，判据测不出「两种说法」。
            keyword_ids: list[str] = []
            for index, (source_id, _region, text) in enumerate(WORDINGS):
                keyword_id = f"sc-kw-{index}"
                keyword_ids.append(keyword_id)
                await conn.execute(
                    "INSERT INTO keywords (keyword_id, canonical, lang, aliases, "
                    "embedding, first_seen) "
                    "VALUES ($1, $2, 'en', '[]'::jsonb, $3::vector, $4)",
                    keyword_id, _canonical_of(text), VEC, DAY)
            # `lineage_results` 的九列全 NOT NULL——阈值那三列照 `S5` 的初值填，
            # 本卡不读它们（只读 `events`），但 NEVER 为了插进去而改表约束。
            await conn.execute(
                "INSERT INTO lineage_results (lineage_id, day, events, "
                "dormant_cluster_ids, drift_audits, tau_match, tau_link, "
                "dormant_after_days, generated_at) "
                "VALUES ('sc-lin-1', $1, $2::jsonb, '[]'::jsonb, '[]'::jsonb, "
                "0.82, 0.75, 14, now())",
                DAY, json.dumps([
                    {"kind": "continued", "cluster_id": CLUSTER,
                     "keyword_ids": keyword_ids},
                ]))
            for source_id, _region, _text in WORDINGS:
                await conn.execute(
                    "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, "
                    "norm_score) VALUES ($1, $2, $3, 0.5, 0.5)", CLUSTER, source_id, DAY)
            await conn.execute(
                "INSERT INTO heat_points (cluster_id, source_id, day, raw_value, "
                "norm_score) VALUES ($1, $2, $3, 0.5, 0.5)",
                CLUSTER, SOURCE_WITHOUT_WORDING, DAY)
            for index, (source_id, region, text) in enumerate(WORDINGS):
                await conn.execute(
                    "INSERT INTO trend_items_raw (day, source_id, item_index, keyword, "
                    "score, region, url, captured_at) "
                    "VALUES ($1, $2, $3, $4, 1.0, $5, 'https://example.test/x', now())",
                    DAY, source_id, index, text, region)
        finally:
            await conn.close()

    _run(wipe())
    _run(seed())
    yield
    _run(wipe())


def _cluster_row() -> Any:
    import httpx

    from flint.api.views import ViewsApiDeps, create_views_app

    async def go() -> Any:
        app = create_views_app(ViewsApiDeps(dsn=DSN))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver",
        ) as client:
            return await client.get(f"/plaza/hot?day={DAY.isoformat()}")

    resp = _run(go())
    assert resp.status_code == 200, resp.text
    rows = [c for c in resp.json()["clusters"] if c["cluster_id"] == CLUSTER]
    assert rows, f"种子那条簇没进榜：{[c['cluster_id'] for c in resp.json()['clusters']]}"
    return rows[0]


# ───────────────────────── 一、端点回的是词面，不是分数


@pytest.mark.compose
def test_the_endpoint_returns_each_sources_own_wording(seeded: None) -> None:
    """**本卡的核心**：每个源带自己那句原话。"""
    row = _cluster_row()

    assert "by_source_text" in row, "端点还是只回分数，没有词面"
    got = row["by_source_text"]
    for source_id, _region, text in WORDINGS:
        assert got.get(source_id) == text, (
            f"{source_id} 的词面不对：{got.get(source_id)!r} != {text!r}")


@pytest.mark.compose
def test_the_wording_is_verbatim_not_normalised(seeded: None) -> None:
    """**逐字**：首尾空格与全角字符原样带回。

    `clean()` 归一化是**入库前**的事。回给屏上时再归一一次，
    微博那句 `＃脑机接口＃ 临床试验` 就不再是微博说的那句话了——
    而屏上仍然写着「微博说：」。
    """
    row = _cluster_row()
    weibo = row["by_source_text"]["weibo"]

    assert weibo.startswith("  ") and weibo.endswith("  "), f"首尾空白被吃掉了：{weibo!r}"
    assert "＃" in weibo, f"全角井号被归一成半角了：{weibo!r}"


@pytest.mark.compose
def test_the_two_sources_disagree_and_both_are_kept(seeded: None) -> None:
    """两个源说法**不同**，两句都在——这就是「分列 ≥2 列」的数据前提。

    只判「字段存在」的话，两个源回同一句话也能过，
    而那时屏上两列写着一模一样的东西，`B4` 想让人看见的分歧就没了。
    """
    texts = _cluster_row()["by_source_text"]

    assert len(set(texts.values())) >= 2, f"两个源说的是同一句话：{texts}"


@pytest.mark.compose
def test_a_source_without_wording_is_absent_not_empty(seeded: None) -> None:
    """查不到词面的源**不出现在 `by_source_text` 里**，而不是给一个空串。

    空串在屏上与「这个源说了一句空话」长得一模一样，
    而真相是「我们没能把它的原话找回来」（`DEC-032` 的诚实态纪律）。
    """
    row = _cluster_row()

    assert SOURCE_WITHOUT_WORDING in row["by_source"], "种子那条没词面的源不在热度里"
    assert SOURCE_WITHOUT_WORDING not in row["by_source_text"], (
        "没查到词面的源被塞了一个占位值")


@pytest.mark.compose
def test_the_score_channel_is_untouched(seeded: None) -> None:
    """`by_source` 的形状**一字未改**（`HOTSPOT-07` 的分列判据按它读）。

    往里塞一个对象，那些判据会在**读到分值的地方拿到一个 dict**——
    它们不会报错，只会算出一个错的列高。
    """
    row = _cluster_row()

    for value in row["by_source"].values():
        assert isinstance(value, (int, float)), f"by_source 的形状被改了：{row['by_source']}"


# ───────────────────────── 二、纯函数：同一个源说了两条时 NEVER 拼接


def test_a_second_statement_from_the_same_source_is_counted_not_concatenated() -> None:
    """同一天同一个源有两条落进同一个簇时，**取第一条并记数**。

    拼起来的那句话没有任何一个来源说过——**那就是 `B4` 禁的合成句，
    只是换了个地方合成**。
    """
    from flint.region.source_text import RawItem, wordings_by_cluster

    got = wordings_by_cluster(
        [RawItem("weibo", "脑机接口"), RawItem("weibo", "脑机接口 临床")],
        {"c": "cluster-1"}, lambda _s: "c")

    wording = got["cluster-1"]["weibo"]
    assert wording.text == "脑机接口", f"取的不是第一条：{wording.text!r}"
    assert wording.also_said == 1
    assert "临床" not in wording.text, "两条被拼成了一句"


def test_an_item_that_maps_to_no_cluster_is_dropped_quietly() -> None:
    """映射不到簇的条目**丢掉**，NEVER 归到某个簇上。

    归错一次，屏上会出现「微博对这个热点说过某句话」——而它说的是别的事。
    """
    from flint.region.source_text import RawItem, wordings_by_cluster

    got = wordings_by_cluster([RawItem("weibo", "别的事")], {}, lambda s: s)

    assert got == {}


def test_the_canonical_map_matches_the_ingest_shape() -> None:
    """`cluster_of_canonical` 与 `_step_heat` 建的那张表**同构**。

    两处对同一份数据给出不同的归属，屏上的词面就会与热度分对不上号——
    而那是一种没有任何报错的错。
    """
    from flint.region.source_text import cluster_of_canonical

    got = cluster_of_canonical({"c1": ["k1", "k2"], "c2": ["k3"]},
                               {"k1": "alpha", "k2": "beta", "k3": "gamma"})

    assert got == {"alpha": "c1", "beta": "c1", "gamma": "c2"}


# ───────────────────────── 三、调用方：缺词面时如实标注，NEVER 顶替


def test_the_caller_never_puts_a_score_into_the_text_slot() -> None:
    """`text` 槽里 NEVER 出现分数。

    判的是**源码**：`ClusterSourceLines` 里 `text:` 的右值只能来自词面那一路。
    """
    assert LINES.exists(), "广场还没有把 SourceColumns 接上"
    code = "\n".join(
        line for line in LINES.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("//"))

    for forbidden in ("by_source[", "bySource[", "heat", "total_heat"):
        assert f"text: {forbidden}" not in code, f"分数被塞进了 text 槽：{forbidden}"
    assert "by_source_text" in code or "bySourceText" in code, "词面那一路没接上"


def test_the_caller_reports_missing_wording_on_its_own_line() -> None:
    """缺词面的源**另起一行如实说**，NEVER 塞占位串进 `text`。

    那个槽契约上是「原文」。塞 `—` 或「暂无」进去，
    屏上会写着「微博说：暂无」——而微博没说过这句话。
    """
    code = LINES.read_text(encoding="utf-8")

    assert "source.wording.missing" in code, "没有「原话没查到」这一态"
    assert "data-testid=\"source-wording-missing\"" in code


def test_the_frozen_component_was_not_touched() -> None:
    """`SourceColumns` 是 v0.4 已 verified（`HOTSPOT-07`）——**本卡一个字没改它**。

    `worker.md` §9.2 / `DEC-021`。所以「缺词面」那一态落在调用方，
    而不是给这个组件加一个 `text?: string | null`。
    """
    code = COLUMNS.read_text(encoding="utf-8")

    assert "text: string;" in code, "SourceStatement.text 的类型被动过"
    assert "source.wording.missing" not in code, "缺词面那一态被塞进了冻结组件"
    assert "UNKNOWN_REGION_KEY" in code


# ───────────────────────── 四、合成句黑名单零命中（既有判据不倒）


@pytest.mark.compose
def test_no_synthesised_sentence_reaches_the_wire(seeded: None) -> None:
    """端点回的词面里，合成句黑名单**零命中**。

    黑名单本身在 `flint/region/by_source_region.py`（`REGION-08` 建），
    这里**读它**而不是抄一份：抄一份的话，那边加一条模式这边不会跟上。
    """
    from flint.region.by_source_region import SYNTHESIS_BLACKLIST

    texts = list(_cluster_row()["by_source_text"].values())

    assert texts, "一句词面都没有，这条判据在空转"
    for pattern in SYNTHESIS_BLACKLIST:
        for text in texts:
            assert not re.search(pattern, text, re.IGNORECASE), (
                f"词面里有合成句：{text!r} 命中 {pattern}")


def test_the_blacklist_would_catch_a_synthesised_sentence() -> None:
    """**阴性对照**：同一把尺子对一句真的合成句必须报红。

    没有这一条，「零命中」可能只是尺子不认得任何东西。
    """
    from flint.region.by_source_region import SYNTHESIS_BLACKLIST

    fake = "综合各国观点，总体而言这一赛道前景向好"
    hits = [p for p in SYNTHESIS_BLACKLIST if re.search(p, fake, re.IGNORECASE)]

    assert hits, "黑名单认不出一句典型的合成句"


def test_the_endpoint_does_not_carry_its_own_blacklist_copy() -> None:
    """端点侧 NEVER 抄一份黑名单。

    副本的风险是漂移——`HOTSPOT-07` 为前端那份副本专门配了漂移检测，
    而后端这一侧本来就能直接 import，没有抄的理由。
    """
    text = VIEWS.read_text(encoding="utf-8")

    assert "综合各" not in text, "views.py 里抄了一份黑名单模式"


# ───────────────────────── 五、单据关掉（两条缺口都清了）


def test_the_sheet_is_closed_now_that_both_gaps_are_gone() -> None:
    text = SHEET.read_text(encoding="utf-8")
    head = "\n".join(text.splitlines()[:8])

    assert "**状态** closed" in head, f"单据还开着：{head!r}"
    assert "REGION-12" in text, "没写清缺口二是被哪张卡关的"
    for earlier in ("REGION-08", "REGION-09", "REGION-10"):
        assert earlier in text, f"缺口一的结案记录被删了：{earlier}"
