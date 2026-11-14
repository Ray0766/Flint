"""REGION-09：`GET /plaza/hot?region=` 真的筛。

## 改前

规格 `#2.14` 白纸黑字写着这条 query【已建】，而 `flint/api/views.py` 的签名只有 `day`。
**FastAPI 对未声明的 query 静默忽略**——带 `region=CN` 回的是全量 154 条，
与不带**逐字相同**。

`DEC-035` 的原话：**一个静静地什么都不筛的筛选器比没有筛选器更坏**——
用户会把「全国的热点」读成「这个区的热点」，并据此做判断。

## 阴性对照是这张卡的核心

只断言「参数被接受」的话，**改前那一版照样绿**（它回 200）。
所以这里断言的是：两个区返回的**簇集合不同**，且**都是全量的真子集**。

## 合法值取自冻结件词表，不是「表里现在有什么」

本卡第一版拿 `SELECT DISTINCT region FROM clusters` 当合法值清单。**那是错的**，
而错处直到 `REGION-10` 把筛选器接上屏才现形：`GET /settings/locale` 给屏上
九个区（`contracts_v04.Region`），其中八个一点就报 400——
用户看到「这个区不存在」，而真相是「这个区今天没热点」。

**两件事必须分开**：合法性看词表（`AU` 是一个区），有没有数据看当天
（`AU` 今天没热点 → 200 + 空 → 规格 #2.14 已建的「该区当日无数据」态）。

顺带的结果是：库里那个 `global` **不在词表里**，所以它筛不出来。
**那是对的、也是要的**——它让
`docs/blocked/REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION.md`
那个问题留在明面上，而不是被一个能用的筛选器盖过去。

## 对照为什么用两个都非空的区

拿一个空区做对照，「两个集合不同」会因为**一边是空集**而恒成立，
判据就退化成「查空区返回空」——**它测不出筛选器有没有在工作**。
所以种子里 `CN` 与 `US` 都有数据。
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
DSN = os.environ.get("FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")
DAY = date(2026, 7, 20)
VEC = "[" + ",".join(["0"] * 1024) + "]"
# 两个都非空的真值。空集会让「集合不同」恒成立（见模块 docstring）。
LEFT, RIGHT = "CN", "US"
# 库里那个 `global` 不在产品词表里（见本文件末两条），单独测。
OUT_OF_VOCAB = "global"


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


@pytest.fixture()
def seeded() -> Any:
    import asyncpg

    async def wipe() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            await conn.execute("DELETE FROM heat_points WHERE cluster_id LIKE 'rq-%'")
            await conn.execute("DELETE FROM clusters WHERE cluster_id LIKE 'rq-%'")
        finally:
            await conn.close()

    async def seed() -> None:
        conn = await asyncpg.connect(DSN)
        try:
            rows = [("rq-cn-1", LEFT), ("rq-cn-2", LEFT),
                    ("rq-us-1", RIGHT), ("rq-gl-1", OUT_OF_VOCAB),
                    ("rq-none", None)]
            for cid, region in rows:
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
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            return await client.get(query)

    return _run(go())


def _ids(query: str) -> set[str]:
    resp = _get(query)
    assert resp.status_code == 200, resp.text
    return {c["cluster_id"] for c in resp.json()["clusters"] if c["cluster_id"].startswith("rq-")}


# ───────────────────────── 一、参数是真的（不是被静默忽略）


def test_the_query_parameter_is_declared() -> None:
    """签名里真有它。

    FastAPI 对**未声明**的 query 静默忽略——那正是改前的实况：
    带 `region=CN` 回 200 且与不带逐字相同。
    """
    text = VIEWS.read_text(encoding="utf-8")
    signature = text[text.index('@app.get("/plaza/hot")'):]
    signature = signature[: signature.index("-> Response")]

    assert "region" in signature, "plaza 的签名里还是没有 region"


# ───────────────────────── 二、阴性对照（本卡的核心）


@pytest.mark.compose
def test_two_regions_return_different_sets(seeded: None) -> None:
    """**两个区的簇集合不同**。

    只断言「参数被接受」的话，改前那一版照样绿（它回 200）。
    """
    left = _ids(f"/plaza/hot?day={DAY.isoformat()}&region={LEFT}")
    right = _ids(f"/plaza/hot?day={DAY.isoformat()}&region={RIGHT}")

    assert left, f"{LEFT} 区一条都没有——对照会因为空集而恒成立"
    assert right, f"{RIGHT} 区一条都没有"
    assert left != right, "两个区返回同一批簇——筛选器没在工作"
    assert left.isdisjoint(right), "同一个簇同时属于两个区"


@pytest.mark.compose
def test_each_region_is_a_proper_subset_of_the_whole(seeded: None) -> None:
    """两个区**都是全量的真子集**。

    这一条挡的是另一种假筛：把 `region` 当成排序键或后置装饰，
    结果集不变而顺序变了——「集合不同」那条会绿，这一条不会。
    """
    whole = _ids(f"/plaza/hot?day={DAY.isoformat()}")

    for region in (LEFT, RIGHT):
        got = _ids(f"/plaza/hot?day={DAY.isoformat()}&region={region}")
        assert got < whole, f"{region} 不是全量的真子集：{got} vs {whole}"


@pytest.mark.compose
def test_a_cluster_with_no_region_is_in_neither(seeded: None) -> None:
    """判不出区的簇（`NULL`）**哪个区都不属于**，NEVER 被塞进某一个。

    `REGION-08` 把它留成 `NULL` 就是为了这一刻：塞进任何一个区，
    用户看到的都是一条我们并不知道产地的热点。
    """
    whole = _ids(f"/plaza/hot?day={DAY.isoformat()}")
    left = _ids(f"/plaza/hot?day={DAY.isoformat()}&region={LEFT}")
    right = _ids(f"/plaza/hot?day={DAY.isoformat()}&region={RIGHT}")

    assert "rq-none" in whole, "没有区的簇在全量里也不见了——那是另一种漏"
    assert "rq-none" not in left | right


# ───────────────────────── 三、不传时与今天逐字相同（增量不破坏）


@pytest.mark.compose
def test_omitting_the_parameter_changes_nothing(seeded: None) -> None:
    """规格 `#2.14` 的增量口径：不传 `region` 时行为与基线**逐字相同**。"""
    base = _get(f"/plaza/hot?day={DAY.isoformat()}").json()
    again = _get(f"/plaza/hot?day={DAY.isoformat()}&region=").json()

    assert base == again, "空 region 与不传 region 不一样"
    assert len([c for c in base["clusters"] if c["cluster_id"].startswith("rq-")]) == 5


# ───────────────────────── 四、无效值大声拒，NEVER 静默回全量


@pytest.mark.compose
def test_an_unknown_region_is_rejected_by_name(seeded: None) -> None:
    """无效值回 400 并**点名可选值**。

    静默回全量是最坏的：用户拼错一个区名，拿到的是全世界的热点，
    而屏上写着他选的那个区。
    """
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region=ZZ")

    assert resp.status_code == 400, f"无效 region 没被拒：{resp.status_code}"
    body = resp.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert LEFT in body["message"], "没告诉调用方有哪些区可选"


@pytest.mark.compose
def test_the_options_come_from_the_frozen_vocabulary(seeded: None) -> None:
    """可选值取自冻结件 `contracts_v04.Region`，与 `GET /settings/locale` **同源**。

    **本卡第一版拿的是「表里现在有什么」（`SELECT DISTINCT region`），那是错的**：
    它把「`AU` 不是一个区」（假）与「`AU` 今天没数据」（真）混成了一件事。
    后果在 `REGION-10` 上现形——`/settings/locale` 给屏上九个区，
    其中八个一点就报 400，用户看到「这个区不存在」，而真相是「今天没热点」。
    """
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region=ZZ")
    message = resp.json()["message"]

    for expected in ("CN", "US", "JP"):
        assert expected in message, f"清单不是冻结件那九个：{message}"
    text = VIEWS.read_text(encoding="utf-8")
    assert "get_args" in text, "清单不是 get_args 取的——那就是抄了一份"


@pytest.mark.compose
def test_a_valid_region_with_no_data_returns_empty_not_an_error(seeded: None) -> None:
    """**阴性对照**：合法区 + 今天没数据 → 200 + 空，NEVER 400。

    这一条挡的正是上面那条注释里的错法。空结果落到规格 #2.14 已建的
    「该区当日无数据」态；报 400 的话，屏上会说这个区不存在。
    """
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region=JP")

    assert resp.status_code == 200, f"合法但无数据的区被拒了：{resp.text}"
    assert [c for c in resp.json()["clusters"] if c["cluster_id"].startswith("rq-")] == []


@pytest.mark.compose
def test_a_value_outside_the_vocabulary_is_still_rejected(seeded: None) -> None:
    """`global` **不在**产品词表里（`ghtrend` 写死的常量，不是一个区）。

    所以它筛不出来——**那是对的、也是要的**：它让
    `REGION-08-GLOBAL-IS-A-SOURCE-CONSTANT-NOT-A-REGION` 那个问题留在明面上，
    而不是被一个能用的筛选器盖过去。
    """
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region={OUT_OF_VOCAB}")

    assert resp.status_code == 400, "global 被当成了一个合法的区"


# ───────────────────────── 五、by_source 带地区维度（既有分列判据不倒）


@pytest.mark.compose
def test_by_source_carries_each_sources_region(seeded: None) -> None:
    """acceptance④：每个源带地区维度。

    **另开一个键而不是改 `by_source` 的形状**：`by_source` 是
    `{source_id: 分值}`，`HOTSPOT-07` 的分列判据按这个形状读。
    往里塞一个对象会让那些判据在**读到分值的地方拿到一个 dict**——
    而它们不会报错，只会算出一个错的列高。
    """
    resp = _get(f"/plaza/hot?day={DAY.isoformat()}&region={LEFT}")
    row = next(c for c in resp.json()["clusters"] if c["cluster_id"] == "rq-cn-1")

    assert isinstance(row["by_source"]["weibo"], (int, float)), "by_source 的形状被改了"
    assert row["by_source_region"]["weibo"] == LEFT


def test_the_existing_split_column_judgement_still_stands() -> None:
    """`HOTSPOT-07` 的既有分列判据还在**且本卡一个字没改它**。

    点名文件而不是「某处有 by_source」：后者在判据被整份删掉时，
    只要别的文件里还写着这四个字就照样绿。
    """
    existing = REPO / "tests" / "v04" / "region" / "test_by_source_regions.py"

    assert existing.exists(), "HOTSPOT-07 的分列判据文件不见了"
    text = existing.read_text(encoding="utf-8")
    assert "by_source" in text
    assert "REGION-09" not in text, "本卡改动了既有判据——它应当原样通过"
