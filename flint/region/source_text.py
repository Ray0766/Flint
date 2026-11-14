"""REGION-12：每个源对同一个热点**说了什么**——原文词面，NEVER 归一化。

## 广场手上缺的正是这一样

`GET /plaza/hot` 每条簇回 `by_source`（`{源: 分值}`）与 `by_source_region`
（`{源: 区}`）。而 `SourceColumns`（`HOTSPOT-07`）要的是

```ts
SourceStatement { sourceId, region, text }     // text 契约逐字：「原文；NEVER 是译文」
```

**分值不是词面。** 把分值塞进 `text`，就是拿一个已经有主的槽去说另一件事
（`DEC-034` / `DEC-038` 反复禁的那一条）：屏上会出现一列「来源说法」写着 `100.0`。

真正缺的是 `trend_items_raw.keyword`——微博说「脑机接口」、GitHub 说 `bci`，
**同一个热点两种说法**。那正是 `PRINCIPLES#B4`「把话还给说话的人」要的东西：
两国对同一件事说法不一致时，读者失去「谁说的」就失去了唯一能判断可信度的东西。

## 三跳，与 `flint/region/backfill.py` 同一个方向

```
cluster → lineage_results 当日成员（keyword_ids） → keywords.canonical
        → canonicalize 后与之相同的 trend_items_raw 条目 → 它们的 keyword 原文
```

第三跳要 canonicalize，是因为 `trend_items_raw.keyword` 是**原始词面**
（`synthetic data curricula for code agents`），而 `keywords.canonical` 是规范形。
这条对应关系由 `flint/jobs/ingest.py#_step_heat` 建立，本模块**按同一个方向再走一遍**，
NEVER 反过来猜。

## 为什么不直接调 ingest 那段

`_step_heat` 是作业内的一段，绑着 `IngestDeps`（DSN、term map、embed、聚类阈值）
与它自己的事务。把它 import 进 API 模块，等于把整张作业依赖图拖进一个只读端点——
而且 `flint/jobs/ingest.py` 是 v0.4 已 verified 的文件（`DEC-021`：NEVER 再改）。

所以这里是**纯函数**：不碰数据库、不碰配置，输入是已经取好的行。
两处做的是同一个 join、不同的聚合（那边求和成热度，这里取词面），
join 本身由 `cluster_of_canonical` 一处表达。

## 一个源对一个簇可能说过好几句

同一天里 `weibo` 可能有两条都落进同一个簇（不同词面、都指同一件事）。
**取第一条（按 `item_index` 序），并把条数记下来**——NEVER 拼接：
拼起来的那句话没有任何一个来源说过，那就是 `B4` 禁的合成句，只是换了个地方合成。
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RawItem:
    """`trend_items_raw` 的一行里本模块用得到的部分。**按 `item_index` 升序喂进来。**"""

    source_id: str
    keyword: str


@dataclass(frozen=True)
class SourceWording:
    """一个源对一个簇的说法。"""

    source_id: str
    text: str
    """原文词面，**逐字**——NEVER 归一化空白或全半角，NEVER 翻译。"""
    also_said: int = 0
    """同一天里这个源还说过几条落进同一个簇的。0 = 就这一条。"""


def cluster_of_canonical(
    membership: Mapping[str, Sequence[str]],
    canonical_by_keyword_id: Mapping[str, str],
) -> dict[str, str]:
    """canonical 规范形 → cluster_id。

    与 `_step_heat` 建的那张表逐字同构。一个 canonical 落在多个簇上时**后写的赢**，
    与那边 `dict` 推导式的行为一致——NEVER 在这里另定一套优先级：
    两处对同一份数据给出不同的归属，屏上的词面就会与热度分对不上号。
    """
    return {
        canonical_by_keyword_id[kid]: cluster_id
        for cluster_id, keyword_ids in membership.items()
        for kid in keyword_ids
        if kid in canonical_by_keyword_id
    }


def wordings_by_cluster(
    items: Iterable[RawItem],
    cluster_by_canonical: Mapping[str, str],
    canonicalize: Callable[[str], str],
) -> dict[str, dict[str, SourceWording]]:
    """{cluster_id: {source_id: 这个源的原文词面}}。

    `canonicalize` 由调用方注入（它要 term map，而本模块不读配置）。
    """
    out: dict[str, dict[str, SourceWording]] = {}
    for item in items:
        cluster_id = cluster_by_canonical.get(canonicalize(item.keyword))
        if cluster_id is None:
            continue
        per_source = out.setdefault(cluster_id, {})
        seen = per_source.get(item.source_id)
        if seen is None:
            per_source[item.source_id] = SourceWording(
                source_id=item.source_id, text=item.keyword)
        else:
            # 第二条起只记数，**NEVER 拼接**：拼起来的那句话没有任何一个来源说过。
            per_source[item.source_id] = SourceWording(
                source_id=seen.source_id, text=seen.text,
                also_said=seen.also_said + 1,
            )
    return out


def as_payload(
    wordings: Mapping[str, SourceWording],
) -> dict[str, str]:
    """端点回给前端的形状：`{源: 原文}`。

    **没查到词面的源不出现在这里**，而不是给一个空串——
    空串在屏上与「这个源说了一句空话」长得一模一样，
    而真相是「我们没能把它的原话找回来」（`DEC-032` 的诚实态纪律）。
    """
    return {source_id: w.text for source_id, w in sorted(wordings.items())}
