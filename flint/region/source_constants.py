"""REGION-SPAN / `DEC-058`：哪些 `region` 值**不是地理事实**——一处定义。

## 为什么要单独一个文件

`DEC-058` 逐字：「『哪些值是源常量』MUST 一处定义他处引用，
NEVER 在 backfill 与前端各写一份」。

改前 `"global"` 这个字面量散在三处：

| 落点 | 它在那里干什么 |
|---|---|
| `flint/api/views.py#SOURCE_CONSTANT_REGIONS` | 筛选面把它与 `NULL` 一起归入未归区 |
| `flint/sources/ghtrend.py` | **写**这个值进库 |
| `flint/sources/arxiv.py` | 同上（默认参数） |

三处各写一份的话，加第二个源常量那天只有一处会跟上，
而**症状是「某个源的热点在筛选面上消失了」**——看起来像查询坏了。

## 它与 `NULL` 恒可分辨

| 值 | 意思 | 谁该做什么 |
|---|---|---|
| `NULL` | **从来没归过区** | 等回填/日更把它判出来 |
| `"global"` | 源自己说「全球」 | 没什么可做的，它就是这样 |

**NEVER 把 `NULL` 回填成 `global`**：回填过的行与本来就是 `global` 的行
从此长得一模一样，而前者原本是可以被判出来的。

## 前端**没有**第二份

筛选面上「未归区」那一项由后端在 query 里合并（`views.py` 那条三分支），
前端只持有 `UNASSIGNED_REGION = "unassigned"`——**那是筛选面的选项名，
不是源常量的清单**。两者刻意不同名也不同物。
"""
from __future__ import annotations

from typing import Final

#: 落在 `region` 列里、但**不是地理事实**的那些值。
#:
#: 今天只有一个：`global` 是 `ghtrend` 写死的源常量
#: （`web/lib/regions.ts` 的原话：「它不是地理事实」）。
#:
#: 加第二个之前先想清楚它是不是真的「不表达地理」——
#: 一个表达地理的值混进来，`DEC-058` 那条「不参与定区」的规则
#: 会开始悄悄丢掉真的地区信息。
SOURCE_CONSTANT_REGIONS: Final[tuple[str, ...]] = ("global",)


def is_source_constant(region: str | None) -> bool:
    """这个值是不是「源自己说的」而不是一个地方。

    `None` 不是源常量——它是「从来没归过区」，另一件事。
    """
    return region in SOURCE_CONSTANT_REGIONS
