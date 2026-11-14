"""REGION-SPAN / `DEC-058`：源常量不参与定区。

## 那一条簇

`c-20260629-108`（脑机接口）的成员来自 `ghtrend`（`region='global'`）与
`gtrends`（`HK`）。`region_of_members` 按既有口径把它判成**跨区**、
拒绝取众数、留 `NULL`——于是它在筛选面上只出现在「未归区」，
选 HK 或 CN 的人都看不到它。

`DEC-058`（owner 2026-08-11）：**`global` 是源常量，不是一个地方**
（`web/lib/regions.ts` 原话：「它不是地理事实」）。
一个不表达地理的值参与定区，本来就说不通。

## 这一条放宽的是判定输入，不是判定纪律

判据要守住的正是这条分界：

| | 做的是什么 | 本文件哪一条 |
|---|---|---|
| 取众数（**恒禁**） | 拿多数压掉少数——少数那个区被抹平 | §三 |
| `DEC-058` | 把一个**本来就不表达地理**的值排除在输入之外 | §二 |

排除之后**其余成员仍跨真区时照旧停下上报**——那句 raise 一字未动，§三 判它。

## 一处定义他处引用

`DEC-058` 逐字：「『哪些值是源常量』MUST 一处定义他处引用，
NEVER 在 backfill 与前端各写一份」。落点 `flint/region/source_constants.py`，
§一 判**全仓没有第二份**。
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from flint.region.backfill import CrossRegionClusterError, region_of_members
from flint.region.source_constants import (
    SOURCE_CONSTANT_REGIONS,
    is_source_constant,
)

REPO = Path(__file__).resolve().parents[2]
TRUTH = REPO / "flint" / "region" / "source_constants.py"
DSN = os.environ.get(
    "FLINT_TEST_DSN", "postgresql://flint:flint@localhost:55432/flint_test")

#: `DEC-058` 回填的那一条（实查全库混源簇只有它）。
SPANNING_CLUSTER = "c-20260629-108"


# ───────────────────────── 一、源常量清单只有一处


def test_the_list_lives_in_exactly_one_place() -> None:
    """`"global"` 这个字面量**只在那一处文件里**出现在清单里。

    改前它散在三处（`views.py` 的清单 · `ghtrend` 写库 · `arxiv` 默认参数），
    加第二个源常量那天只有一处会跟上——
    **而症状是「某个源的热点在筛选面上消失了」**，看起来像查询坏了。
    """
    holders: list[str] = []
    for path in sorted((REPO / "flint").rglob("*.py")):
        if path == TRUTH or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        code = "\n".join(ln for ln in text.splitlines()
                         if not ln.strip().startswith("#"))
        # 只找**赋值/字面量**形态，不找 docstring 里提到这个词
        if re.search(r'=\s*\(?\s*"global"', code) or '["global"]' in code:
            holders.append(path.relative_to(REPO).as_posix())

    assert holders == [], f"这些文件里还有第二份源常量：{holders}"


def test_the_readers_share_the_very_same_object() -> None:
    """筛选面那一侧与定区那一侧拿到的是**同一个对象**，不是两份长得一样的。

    两份内容相同的清单在今天分不出来，而它们会各自漂移。
    """
    from flint.api.views import SOURCE_CONSTANT_REGIONS as from_views

    assert from_views is SOURCE_CONSTANT_REGIONS


def test_the_writers_use_it_too() -> None:
    """**写库那一侧也引用同一份**：`ghtrend` 写进去的值就是清单里的那个。

    写的人自带一个字面量的话，改清单时库里已有的行不会跟着变，
    而「清单里没有这个值」与「库里存着这个值」会同时为真。
    """
    ghtrend = (REPO / "flint" / "sources" / "ghtrend.py").read_text(encoding="utf-8")
    arxiv = (REPO / "flint" / "sources" / "arxiv.py").read_text(encoding="utf-8")

    for name, text in (("ghtrend", ghtrend), ("arxiv", arxiv)):
        assert "SOURCE_CONSTANT_REGIONS" in text, f"{name} 没引用那一份"


def test_the_frontend_option_is_a_different_thing() -> None:
    """前端 `UNASSIGNED_REGION` **不是**源常量清单——两者刻意不同名也不同物。

    合成一件事的话，「未归区」这个筛选选项会开始被当成一个可以写进库的值。
    """
    regions_ts = (REPO / "web" / "lib" / "regions.ts").read_text(encoding="utf-8")

    assert 'UNASSIGNED_REGION = "unassigned"' in regions_ts
    assert "unassigned" not in SOURCE_CONSTANT_REGIONS


# ───────────────────────── 二、规则本身


def test_a_source_constant_does_not_decide_the_region() -> None:
    """`global` + `HK` → **HK**（改前：跨区抛错）。"""
    assert region_of_members("c-x", ["global", "HK"]) == "HK"
    assert region_of_members("c-x", ["HK", "global", "HK"]) == "HK"


def test_all_source_constants_stay_unassigned() -> None:
    """全部成员都是源常量 → `None`，**NEVER 硬挑一个区**（`DEC-058` 边界逐字）。

    挑一个的话，屏上会出现一条我们并不知道产地的热点。
    """
    assert region_of_members("c-x", ["global"]) is None
    assert region_of_members("c-x", ["global", "global"]) is None


def test_no_members_is_still_unknown() -> None:
    """一个成员都没有 → 照旧 `None`。这一支本卡一字没动。"""
    assert region_of_members("c-x", []) is None
    assert region_of_members("c-x", ["", ""]) is None


def test_is_source_constant_says_none_is_not_one() -> None:
    """`None` 不是源常量——它是「从来没归过区」，另一件事。

    合并的话，`NULL` 会开始被当成「源说了全球」，
    而前者原本是可以被判出来的。
    """
    assert is_source_constant("global") is True
    assert is_source_constant(None) is False
    assert is_source_constant("HK") is False


# ───────────────────────── 三、判定纪律**一字未松**


def test_two_real_regions_still_stop_and_name_names() -> None:
    """**其余成员仍跨真区 → 照旧抛，且点名**（`DEC-058` 边界逐字）。

    这一条是本卡最要紧的：放宽输入极容易顺手把纪律也放宽了。
    """
    with pytest.raises(CrossRegionClusterError) as caught:
        region_of_members("c-span", ["CN", "HK"])

    said = str(caught.value)
    assert "c-span" in said, "没点名是哪个簇"
    assert "CN" in said and "HK" in said, "没点名撞了哪几个区"
    assert "NEVER 取众数" in said


def test_a_source_constant_never_rescues_a_real_conflict() -> None:
    """混进一个 `global` **不会**让跨真区变得可以判。

    这是本条规则最容易被写坏的方向：把源常量排除之后顺手
    「那就取剩下的第一个」——那就是取众数换了个名字。
    """
    with pytest.raises(CrossRegionClusterError):
        region_of_members("c-span", ["global", "CN", "HK"])


def test_the_docstring_states_the_boundary() -> None:
    """「放宽的是判定输入，不是判定纪律」这句 MUST 写在规则旁边。

    只写在 DEC 里的话，下一个改这个函数的人看不到它。
    """
    text = (REPO / "flint" / "region" / "backfill.py").read_text(encoding="utf-8")

    assert "放宽的是判定输入，不是判定纪律" in text
    assert "DEC-058" in text


# ───────────────────────── 四、回填只动那一条


def _rows(sql: str, *args: Any) -> list[Any]:
    async def _go() -> list[Any]:
        conn = await asyncpg.connect(DSN)
        try:
            return list(await conn.fetch(sql, *args))
        finally:
            await conn.close()

    return asyncio.run(_go())


@pytest.mark.compose
def test_no_cluster_was_silently_recomputed() -> None:
    """**NEVER 顺手重算全库**（`DEC-058` 边界逐字）。

    这条判据量的是「有没有一批簇被一次性改了区」：
    回填只该动混源那一条，而混源簇实查全库只有一条。

    判的是**混源簇的数目**而不是「那一条的 region 等于 HK」——
    后者在测试库上永远拿不到（那条簇是 demo 库的数据）。
    一次顺手重算会让混源簇的数目变化，而那正是要拦的事。
    """
    mixed = _rows("""
        SELECT c.cluster_id FROM clusters c
        JOIN heat_points h ON h.cluster_id = c.cluster_id
        GROUP BY c.cluster_id
        HAVING count(DISTINCT h.source_id) > 1""")

    assert len(mixed) <= 1, (
        f"混源簇变多了（{len(mixed)} 条）——`DEC-058` 只授权回填当时那一条，"
        f"多出来的要重新上报，NEVER 照着同一条规则顺手都改了")


def test_the_backfill_scope_is_written_down() -> None:
    """「只处理今天这一条」这句 MUST 落在 trace 里，且带实查数字。

    只说「回填了」的话，下一个人无从判断它动了一条还是全库。
    """
    trace = (REPO / "docs" / "trace" / "REGION-SPAN.md").read_text(encoding="utf-8")

    assert SPANNING_CLUSTER in trace
    assert "NEVER 顺手重算全库" in trace
    assert "DEC-058" in trace
