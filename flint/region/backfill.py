"""把簇的 region 判出来——回填与日更共用的**唯一**一条规则。

> 本模块由 **v0.4.1 第 6 批的 `REGION-08`** 建（`docs/steward/tasks-v041-b6.json`）。
> 卡号**刻意不写在首行**：`tools/check_outputs_declared.py` 只读 `tasks-v04.json`，
> 首行自述一个它不认识的卡号，会被报成「自述 X，却不在任何卡的 outputs 里」——
> **而那句话是假的**。让尺子读各批卡面是它自己的事（`GAUGE-14` 那一族），
> 本卡不顺手改别人的尺子；这里按仓里既有约定写
> （`flint/jobs/translate.py` 同一形状，理由也同）。

## 规则出自 `flint/region/bucketing.py`，本模块不另立一套

`ClusterMember` 的原话：**region 随成员走，不靠簇去推断**。
本模块只是把那句话用在库里已有的数据上，NEVER 再发明一套归属规则——
两套规则的后果不是重复劳动，而是**同一个簇在回填与日更里被归到两个区**，
而两次归档之间没有任何东西会告诉你它变过。

## 撞见跨区簇为什么必须停

`PRINCIPLES#B5`：先聚后拆是拆不干净的。一旦两国报道被 embedding 合成一簇，
簇心已经是两国的平均，再按 region 拆开时每一半都不是它自己的。

所以**回填时撞见跨区簇，说明数据面已经破了 B5**——那是一个要人看的信号。
取众数会把它抹平：库里从此有一个标着 `CN` 的簇，而它的簇心是 CN 与 US 的平均，
下游按 region 取「这个区的热点」时拿到的是一个**哪个区都不存在的假热点**。

## 成员是怎么找到的（三跳）

```
cluster → evidence_cards.keyword_ids → keywords.canonical
        → canonicalize 后与之相同的 trend_items_raw 条目 → 它们的 region
```

第三跳要 canonicalize 是因为 `trend_items_raw.keyword` 是原始词面
（「synthetic data curricula for code agents」），而 `keywords.canonical` 是规范形
——这正是 `flint/jobs/ingest.py#_load_day_canonicals` 建立的那条对应关系，
本模块**按同一个方向再走一遍**，NEVER 反过来猜。

## 判不出来的簇留 NULL

三跳断了（该簇的关键词在原始表里找不到对应条目）就是「还不知道」。
`NULL` 说的是实话；填一个「global」之类的兜底值，
会让广场上「这个簇属于全球」与「我们没能判出它属于哪」变成同一个样子。
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from flint.region.source_constants import is_source_constant


class CrossRegionClusterError(Exception):
    """一个簇的成员跨了区 —— MUST 停下上报，NEVER 取众数 [PRINCIPLES#B5]。

    **与 `bucketing.CrossRegionLineageError` 刻意不共用类型**：
    那一个说的是「血缘关系跨了区」，这一个说的是「一个簇内部就跨了区」。
    共用一个类型会让上报的人分不清撞的是哪一条，而两者的处置完全不同。
    """


def region_of_members(cluster_id: str, regions: Sequence[str]) -> str | None:
    """簇的 region = 它成员的 region。

    - 全体一致 → 那个区；
    - 一个都没有 → `None`（**不知道**，NEVER 挑一个）；
    - 不一致 → 抛 `CrossRegionClusterError` 并**点名是哪个簇、撞了哪几个区**
      （不点名的话，上报的人无从去查）。

    ## `DEC-058`：源常量不参与定区

    `global` 是 `ghtrend` 写死的**源常量**，不是一个地方
    （`web/lib/regions.ts` 的原话：「它不是地理事实」）。
    一个不表达地理的值参与定区，本来就说不通——
    改前它会让「ghtrend + gtrends 各出一个成员」的簇被判成跨区，
    而那个簇其实只有一个地理归属。

    **这一条放宽的是判定输入，不是判定纪律。**
    两者的分界要说清楚：

    | | 做的是什么 |
    |---|---|
    | 取众数（**恒禁**） | 拿多数压掉少数——少数那个区的信号被抹平 |
    | 本条 | 把一个**本来就不表达地理**的值排除在输入之外 |

    排除之后**其余成员仍然跨真区时，照旧停下上报**（下面那句 raise 一字未动）。
    全部成员都是源常量时 → `None`（未归区），**NEVER 硬挑一个区**。
    """
    # 源常量先出局：它们不是地方，参与定区只会造出假的「跨区」。
    # 清单来自 `flint/region/source_constants.py`——**一处定义他处引用**
    # （`DEC-058` 逐字：NEVER 在 backfill 与前端各写一份）。
    geographic = [r for r in regions if r and not is_source_constant(r)]
    distinct = sorted(set(geographic))
    if not distinct:
        # 两种情形都落在这里，而**它们在库里恒可分辨**（region 列本身还留着）：
        #   ① 一个成员都没有 → 从来没判过；
        #   ② 成员全是源常量 → 判过了，而它们都不表达地理。
        # 都回 `None`：NEVER 因为「至少有个 global」就把簇归到某个区。
        return None
    if len(distinct) > 1:
        raise CrossRegionClusterError(
            f"簇 {cluster_id} 的成员跨区：{'/'.join(distinct)}。"
            "MUST 停下上报，NEVER 取众数——成员跨区说明数据面已经破了 PRINCIPLES#B5，"
            "取众数只会把这个信号抹平，并留下一个哪个区都不存在的假热点。"
        )
    return distinct[0]


@dataclass
class RegionPlan:
    """回填计划：判出来的、撞车的、判不出来的，**三堆分开**。

    合成一堆的话，「填好了」与「有 37 个没判出来」在日志里长得一模一样。
    """

    assigned: dict[str, str] = field(default_factory=dict)
    conflicts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    unknown: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return len(self.assigned) + len(self.conflicts) + len(self.unknown)


def _canonical_regions(
    keyword_ids: Iterable[str],
    canonical_by_id: dict[str, str],
    regions_by_canonical: dict[str, set[str]],
) -> list[str]:
    found: list[str] = []
    for keyword_id in keyword_ids:
        canonical = canonical_by_id.get(keyword_id)
        if canonical is None:
            continue                      # 三跳断在第二跳：这个词不在 keywords 里
        found.extend(sorted(regions_by_canonical.get(canonical, ())))
    return found


async def plan_cluster_regions(conn: Any, *, only_prefix: str | None = None) -> RegionPlan:
    """算出每个簇该填什么，**只算不写**。

    分成「算」与「写」两步，是因为撞车的那些要先给人看：
    一个 `UPDATE … SET region = …` 跑完之后，跨区的证据就没了。
    """
    from flint.norm.canonical import canonicalize
    from flint.norm.terms import load_term_map

    terms = load_term_map(_TERM_MAP)

    where = "WHERE cluster_id LIKE $1" if only_prefix else ""
    args = [f"{only_prefix}%"] if only_prefix else []
    cluster_rows = await conn.fetch(
        f"SELECT cluster_id FROM clusters {where} ORDER BY cluster_id", *args)

    card_rows = await conn.fetch(
        "SELECT cluster_id, keyword_ids FROM evidence_cards ORDER BY card_id")
    keywords_by_cluster: dict[str, list[str]] = {}
    for row in card_rows:
        ids = json.loads(row["keyword_ids"])
        keywords_by_cluster.setdefault(str(row["cluster_id"]), []).extend(
            str(k) for k in ids)

    canonical_by_id = {
        str(r["keyword_id"]): str(r["canonical"])
        for r in await conn.fetch("SELECT keyword_id, canonical FROM keywords")
    }

    # 第三跳：原始条目的词面按 ingest 的那条路 canonicalize 之后再对齐。
    regions_by_canonical: dict[str, set[str]] = {}
    for row in await conn.fetch(
            "SELECT keyword, region FROM trend_items_raw WHERE region IS NOT NULL"):
        result = canonicalize(str(row["keyword"]), terms)
        if result.canonical:
            regions_by_canonical.setdefault(result.canonical, set()).add(
                str(row["region"]))

    plan = RegionPlan()
    unknown: list[str] = []
    for row in cluster_rows:
        cluster_id = str(row["cluster_id"])
        regions = _canonical_regions(
            keywords_by_cluster.get(cluster_id, ()), canonical_by_id,
            regions_by_canonical)
        try:
            region = region_of_members(cluster_id, regions)
        except CrossRegionClusterError:
            plan.conflicts[cluster_id] = tuple(sorted(set(regions)))
            continue
        if region is None:
            unknown.append(cluster_id)     # 三跳断了：还不知道，NEVER 猜
        else:
            plan.assigned[cluster_id] = region
    plan.unknown = tuple(unknown)
    return plan


async def apply_cluster_regions(conn: Any, plan: RegionPlan) -> int:
    """把**判出来的那些**写进库。撞车与不知道的一个都不写。"""
    written = 0
    for cluster_id, region in sorted(plan.assigned.items()):
        await conn.execute(
            "UPDATE clusters SET region = $2 WHERE cluster_id = $1", cluster_id, region)
        written += 1
    return written


def _term_map_path() -> Any:
    from pathlib import Path

    return Path(__file__).resolve().parents[2] / "assets" / "term-map.yaml"


_TERM_MAP = _term_map_path()
