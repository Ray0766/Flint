"""CN-02 / `DEC-045`（`DEC-056` 修订前半）：本版做 CN 与 HK 两区，其余八区推迟下一版。

owner 2026-08-09 原话：「**不同地区不同信息源的问题下一个版本再解决。
这个版本，先把所有接口接上，先做中国区的内容**」。

`DEC-056`（owner 2026-08-10）**提前执行了后半句**：本版做 CN 与 HK 两区、各用各的源
（CN = 微博，HK = Google 趋势）。`DEC-045` 的其余部分（默认区为 CN、
其余各区明说「本版暂无该区内容」）继续有效，本文件因此**跟着改数、不被删**：
它守的三态、反向保留、一处真相，一条都没有松动。

## 收窄的是**呈现**，不是能力

`REGION-08~12` 建的分区列、query 与分列**一律保留不拆**（`DEC-045`：NEVER 删代码）。
所以本卡的判据里有一整组是**反向**的：断言那些东西**还在**。
一张「本版只做 CN」的卡最容易做成「把别的区删了」，而那是下一版要用的东西。

## 三态 NEVER 混

| 屏上那一片空白 | `data-plaza-state` | 用户该做什么 |
|---|---|---|
| 本版暂无该区内容 | `out_of_scope` | 等下一版 |
| 该区当日无数据 | `empty` | 换一天 / 换一个区 |
| 读失败 | （`data-plaza-error`，在 `PlazaPage` 那一层） | 重试 |

合成一个之后，等下一版的人会一直刷新，而换一天的人会以为功能没做。

## 推迟落成机读记录

`DEC-045` 写死：推迟本身要落成机读记录（形如 `legal_policy` 的 `RECORD_ONLY`），
**NEVER 只留在对话里**。落点是 `flint/region/version_scope.py#CURRENT_SCOPE`。
只留在对话里的话，下一版接手的人无从知道哪些是**被推迟的**、哪些是**没做的**——
两者在代码里长得一模一样。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCOPE_MODULE = REPO / "flint" / "region" / "version_scope.py"
VIEWS = REPO / "flint" / "api" / "views.py"
PLAZA_PAGE = REPO / "web" / "app" / "plaza" / "page.tsx"
PLAZA_CARDS = REPO / "web" / "components" / "plaza" / "PlazaCards.tsx"
MESSAGES = REPO / "web" / "messages"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")


# ───────────────────────── 一、推迟落成了机读记录


def test_the_deferral_is_a_machine_readable_record() -> None:
    """`DEC-045` 的硬要求：推迟**不能只留在对话里**。

    形如 `legal_policy.RECORD_ONLY`：谁、什么时候、什么范围、为什么、何时解除。
    """
    from flint.region.version_scope import CURRENT_SCOPE

    assert CURRENT_SCOPE.in_scope == frozenset({"CN", "HK"})
    assert CURRENT_SCOPE.decided_by == "owner"
    assert CURRENT_SCOPE.decided_on.isoformat() == "2026-08-10"
    assert len(CURRENT_SCOPE.rationale) > 60, "只写结论等于没记"


def test_the_record_says_when_the_narrowing_lifts() -> None:
    """**触发条件写成「下一版」**（卡面原话）。

    不写解除条件的话，下一版接手的人不知道这是「推迟」还是「就这样了」。
    """
    from flint.region.version_scope import CURRENT_SCOPE

    assert "下一版" in CURRENT_SCOPE.lifts_when


def test_the_record_is_frozen_so_it_cannot_drift_at_runtime() -> None:
    """运行期被改写的话，产物上写的说法与代码里实际执行的就对不上了
    （与 `LegalDecision` 同一条理由）。"""
    import dataclasses

    from flint.region.version_scope import CURRENT_SCOPE

    with pytest.raises(dataclasses.FrozenInstanceError):
        CURRENT_SCOPE.in_scope = frozenset({"US"})  # type: ignore[misc]


def test_the_deferred_regions_can_be_enumerated() -> None:
    """**哪些区被推迟了**要可枚举。

    散在各处 `if region != "CN"` 的话，下一版解除收窄时没人找得全。
    """
    from flint.region.version_scope import deferred_regions

    selectable = frozenset({"CN", "HK", "US", "JP", "unassigned"})

    # `HK` **不在**被推迟的那一堆里（`DEC-056`）——它今天有内容。
    assert deferred_regions(selectable) == frozenset({"US", "JP", "unassigned"})


def test_not_choosing_a_region_is_always_in_scope() -> None:
    """不选区 = 看全部，**恒在范围内**。

    判成「不在范围」的话，首屏什么都不选时会显示「本版暂无该区内容」——
    而那时屏上明明有一整库的东西。
    """
    from flint.region.version_scope import in_scope

    assert in_scope(None) is True
    assert in_scope("") is True
    assert in_scope("CN") is True
    assert in_scope("HK") is True, "DEC-056：HK 这一版有内容"
    assert in_scope("JP") is False


# ───────────────────────── 二、多区能力**一律保留不拆**（反向判据）


def test_the_multi_region_query_is_still_there() -> None:
    """`REGION-09` 那条真的筛的 query **一行没删**。

    `DEC-045` 原话：本版是收窄**呈现**，NEVER 删代码。
    删了之后下一版要从头再建一次，而那条 query 是 `DEC-035`
    「一个静静地什么都不筛的筛选器比没有筛选器更坏」换来的。
    """
    code = VIEWS.read_text(encoding="utf-8")

    assert "_selectable_regions()" in code, "筛选面清单没了"
    assert "unassigned" in code, "未归区那一支没了（REGION-11）"
    assert "region IS NULL" in code, "REGION-08 留 NULL 的那一支没了"


def test_the_filter_still_offers_every_region() -> None:
    """其余八区与未归区**留在筛选器里**，NEVER 悄悄隐藏。

    隐藏之后用户**不知道这个能力存在**，而它下一版就要用（`DEC-045` 原话）。
    所以广场那个筛选器的清单仍然是「十区 + 未归区」，一个都不少。
    """
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "withUnassigned(" in page, "筛选面清单被改小了"
    assert "options?.region" in page, "地区清单不再从 /settings/locale 取"
    for hiding in ("filter((r) => r === ", '=== "CN"', "onlyCN"):
        assert hiding not in page, f"筛选器被收窄了：{hiding}"


@pytest.mark.compose
def test_the_region_column_still_exists_in_the_database() -> None:
    """`clusters.region` 这一列还在——收窄呈现不动数据层。"""
    import asyncio

    import asyncpg

    async def _columns() -> list[str]:
        conn = await asyncpg.connect(DSN)
        try:
            rows = await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'clusters'")
        finally:
            await conn.close()
        return [r["column_name"] for r in rows]

    assert "region" in asyncio.run(_columns())


# ───────────────────────── 三、默认区是 CN


def test_the_plaza_defaults_to_cn() -> None:
    """acceptance②：**广场默认区为 CN**。

    改前默认是空串（= 全部区），于是首屏混着 `global` 那 103 条一起显示，
    而本版做的是中国区。
    """
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert "DEFAULT_REGION" in page, "默认区不是从一处真相取的"
    assert 'params.has("region")' in page, (
        "没有区分「URL 上显式给了 region」与「没带这个参数」")


def test_an_explicit_empty_region_is_not_forced_back_to_cn() -> None:
    """URL 上显式的 `?region=` **是用户要看全部**，与「没带这个参数」是两件事。

    把他打回 CN 的话，「看全部」这个动作就没法表达了——
    而筛选器里那些区还留着正是为了让他能看。
    """
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert 'params.has("region") ? (params.get("region") ?? "")' in page


def test_the_backend_default_region_is_one_truth() -> None:
    """后端那一份默认区与机读记录住在一起。"""
    from flint.region.version_scope import CURRENT_SCOPE, DEFAULT_REGION

    assert DEFAULT_REGION == "CN"
    assert DEFAULT_REGION in CURRENT_SCOPE.in_scope


# ───────────────────────── 四、三态 NEVER 混


def test_the_endpoint_answers_whether_the_region_is_in_scope() -> None:
    """服务端回答「这一区在不在本版范围内」——**一处真相**。

    让前端自己判的话，下一版解除收窄时会有一处忘了跟上（`LOC-01` 同一条理由）。
    """
    code = VIEWS.read_text(encoding="utf-8")

    assert '"region_in_scope"' in code
    assert '"scope_lifts_when"' in code
    assert "from flint.region.version_scope import" in code


@pytest.mark.compose
def test_the_endpoint_really_says_false_for_a_deferred_region() -> None:
    """真打一次端点：`JP` 回 `region_in_scope: false`，`CN` 回 `true`。

    只判源码里有那个键的话，一个恒 `true` 的实现也能全绿。
    """
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    client = TestClient(create_app(dsn=DSN), raise_server_exceptions=False)

    cn = client.get("/plaza/hot", params={"day": "2026-07-04", "region": "CN"})
    jp = client.get("/plaza/hot", params={"day": "2026-07-04", "region": "JP"})
    every = client.get("/plaza/hot", params={"day": "2026-07-04"})

    assert cn.json()["region_in_scope"] is True, cn.text
    assert jp.json()["region_in_scope"] is False, jp.text
    assert every.json()["region_in_scope"] is True, "不选区被判成了不在范围内"


@pytest.mark.compose
def test_the_deferred_region_still_returns_a_real_query_not_an_error() -> None:
    """**不在范围** ≠ **报错**：`JP` 照旧走真 query、回 200 + 空列表。

    回 4xx 的话，「这一版不做这个区」会被前端当成「请求写错了」，
    而那两件事该让人做的完全不同。
    """
    from fastapi.testclient import TestClient

    from flint.api.app import create_app

    client = TestClient(create_app(dsn=DSN), raise_server_exceptions=False)
    jp = client.get("/plaza/hot", params={"day": "2026-07-04", "region": "JP"})

    assert jp.status_code == 200, jp.text
    assert jp.json()["clusters"] == []


def test_the_three_states_have_three_different_markers() -> None:
    """屏上三态**各有各的记号**，判据靠它分辨。

    共用一个记号的话，「本版不做」与「今天没有」在自动化里就再也分不开了——
    而分不开正是这条 acceptance 要防的事。
    """
    cards = PLAZA_CARDS.read_text(encoding="utf-8")
    page = PLAZA_PAGE.read_text(encoding="utf-8")

    assert '"out_of_scope"' in cards, "少了「本版暂无该区内容」那一态"
    assert '"empty"' in cards, "「该区当日无数据」那一态没了"
    assert "data-plaza-error" in page, "「读失败」那一态没了"
    assert "data-plaza-out-of-scope" in cards


def test_out_of_scope_is_decided_before_empty() -> None:
    """判断顺序：**先判范围，再判空**。

    不在范围内时结果**必然**是空的，先判空的话 `out_of_scope` 永远走不到，
    而屏上会说「该区当日无数据」——一句在这一版里永远为真、
    因而什么都没告诉用户的话。
    """
    cards = PLAZA_CARDS.read_text(encoding="utf-8")
    state = cards.split("data-plaza-state={")[1].split("}")[0]

    assert state.index("out_of_scope") < state.index("empty"), (
        f"顺序反了：{state}")


def test_a_missing_scope_flag_is_treated_as_in_scope() -> None:
    """老录制回放夹具里没有这一格——**NEVER 默认成「不在范围」**。

    默认成不在范围的话，一个正常的空结果会被说成「本版不做这个区」，
    而那是一句假话。
    """
    cards = PLAZA_CARDS.read_text(encoding="utf-8")

    assert "regionInScope === false" in cards, (
        "不是「显式为 false 才算不在范围」——undefined 会被当成不在范围")


# ───────────────────────── 五、话说清楚了，且两种语言都有


def test_the_copy_says_what_it_is_and_when_it_lifts() -> None:
    """只说「暂无」的话，用户不知道该等还是该放弃。"""
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))
    en = json.loads((MESSAGES / "en.json").read_text(encoding="utf-8"))

    for key in ("plaza.out_of_scope.line", "plaza.out_of_scope.lifts_when",
                "plaza.out_of_scope.next_version"):
        assert key in zh, f"zh 缺词条 {key}"
        assert key in en, f"en 缺词条 {key}"
    assert "本版" in zh["plaza.out_of_scope.line"]


def test_the_copy_is_not_the_same_as_the_empty_one() -> None:
    """两态的话**不一样**——一样的话，屏上分不出它们。"""
    zh = json.loads((MESSAGES / "zh.json").read_text(encoding="utf-8"))

    assert zh["plaza.out_of_scope.line"] != zh["plaza.empty.no_data_today"]
