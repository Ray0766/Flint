"""CN-02 / `DEC-045`：本版做哪些区——**收窄呈现的机读记录**。

owner 2026-08-09 原话：「**不同地区不同信息源的问题下一个版本再解决。
这个版本，先把所有接口接上，先做中国区的内容**」。

## 这个文件是「推迟」这件事的落点

`DEC-045` 写死：推迟本身要落成**机读记录**（形如 `legal_policy` 的 `RECORD_ONLY`），
写明触发条件是「下一版」，**NEVER 只留在对话里**。
只留在对话里的话，下一版接手的人无从知道哪些东西是**被推迟的**、
哪些是**没做的**——两者在代码里长得一模一样。

所以这里与 `flint/region/legal_policy.py` 同一个形状：
**谁、什么时候、什么范围、为什么、什么条件下解除**。

## 收窄的是**呈现**，不是能力

`REGION-08~12` 建的九区列、query 与分列**一律保留不拆**（`DEC-045` 原话：
**NEVER 删代码**）。本模块不删任何东西，它只回答一个问题：

> 这个区在**本版**有没有内容？

答案是「没有」时，屏上说的是「**本版暂无该区内容**」——
那是一句**关于版本范围**的话，不是一句关于数据的话。

## 三态 NEVER 混

| 屏上那一片空白 | 真相 | 用户该做什么 |
|---|---|---|
| 本版暂无该区内容 | **这一版不做这个区** | 等下一版 |
| 该区当日无数据 | 做了，查过了，今天确实没有 | 换一天 / 换一个区 |
| 读失败 | 没查成 | 重试 / 报错 |

合成一个之后，「等下一版」的人会一直刷新，而「换一天」的人会以为功能没做。

## 为什么不是把八个区从筛选器里摘掉

摘掉之后**用户不知道这个能力存在**，而它下一版就要用（`DEC-045` 原话）。
筛选器里留着、选中时如实说明——**这是「诚实」与「藏起来」的分界线**。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final


@dataclass(frozen=True)
class VersionScope:
    """一条范围裁决：**谁、什么时候、这一版做哪些区、为什么、什么时候解除**。

    `frozen`：运行期被改写的话，产物上写的说法与代码里实际执行的就对不上了
    （与 `LegalDecision` 同一条理由）。
    """

    decided_on: date
    decided_by: str
    #: 本版**有内容**的区。其余区的能力照旧在，只是这一版没有内容。
    in_scope: frozenset[str]
    #: 解除条件。写成人话，因为读它的是下一版接手的人。
    lifts_when: str
    rationale: str


CN_ONLY: Final[VersionScope] = VersionScope(
    decided_on=date(2026, 8, 9),
    decided_by="owner",
    in_scope=frozenset({"CN"}),
    lifts_when="下一版（不同地区用不同信息源那一件做完时）",
    rationale=(
        "owner 2026-08-09：「不同地区不同信息源的问题下一个版本再解决。"
        "这个版本，先把所有接口接上，先做中国区的内容」。"
        "收窄的是呈现不是能力：REGION-08~12 建的九区列、query 与分列一律保留不拆，"
        "其余八区与未归区留在筛选器里并如实说明本版暂无该区内容——"
        "隐藏之后用户不知道这个能力存在，而它下一版就要用"
    ),
)

#: 现行范围。改这一个名字就能解除收窄（与 `legal_policy.OWNER_DECISION` 同一个开关形态）。
#: `DEC-056`（owner 2026-08-10）：CN 与 HK 两区分家，各自一源。
#:
#: **`CN_ONLY` 那一条原样留着**——它是 `DEC-045` 当时的范围，
#: 本仓有 trace 直接引用它。新范围**另起一条**，两者的差别看得见。
#:
#: ## 数目对不上的那一处，写在这里而不是被抹平
#:
#: `DEC-056` 原文写「其余七区」。而 **HK 原本不在清单 A2 的九区里**，
#: 把它加进 `Region` 之后地区一共十个，CN 与 HK 之外**是八个**。
#: 原文一字不改地留在 `DECISIONS-v04.md`（那是记录），
#: 代码里写**真数**（那是执行）——两处不一致的地方开了单：
#: `docs/blocked/REGION-CN-HK-COUNT-SAYS-SEVEN.md`。
#:
#: NEVER 为了对上那个「七」去删掉一个区：`DEC-056` 的裁决是
#: 「其余各区照旧暂无内容」，那一句在八个区上照样成立，
#: 而删区会真的拿掉一个下一版要用的能力。
CN_AND_HK: Final[VersionScope] = VersionScope(
    decided_on=date(2026, 8, 10),
    decided_by="owner",
    in_scope=frozenset({"CN", "HK"}),
    lifts_when="下一版（其余八区各自的源接上时）",
    rationale=(
        "owner 2026-08-10（`DEC-056`）：CN = 微博热搜，HK = Google 趋势，两区都可切。"
        "`CN-04` 探明 Google 不编大陆榜（`geo=CN` 回 400），"
        "`DEC-054` 因此让 HK 数据以「华语圈代理」的名义落 CN 区；"
        "owner 判断两区分开更清晰，且今天两源各自的地域归属本来就不同。"
        "其余八区（US/AU/SG/JP/KR/GB/IT/FR）照旧明说「本版暂无该区内容」——"
        "`DEC-045` 的这一半没有被修订，NEVER 顺手打开，那是下一版的事"
    ),
)

CURRENT_SCOPE: Final[VersionScope] = CN_AND_HK

#: 广场默认落在哪个区（`DEC-045`：默认区为 CN）。
DEFAULT_REGION: Final[str] = "CN"


def in_scope(region: str | None, *, scope: VersionScope | None = None) -> bool:
    """这个区在本版**有没有内容**。

    `None` / 空串 = 没有选区（全部），**恒 True**——不选区时屏上该显示的是
    库里所有东西，而不是一句「本版暂无」。
    """
    if not region:
        return True
    return region in (scope or CURRENT_SCOPE).in_scope


def deferred_regions(
    selectable: frozenset[str], *, scope: VersionScope | None = None
) -> frozenset[str]:
    """筛选面上**被推迟**的那些区。

    入参是**筛选面**（九区 + 未归区），不是地理词表——
    未归区也在筛选面上，它同样不在本版范围内。

    这个函数存在的意义是让「哪些区被推迟了」可被枚举：
    散在各处 `if region != "CN"` 的话，下一版解除收窄时没人找得全。
    """
    return frozenset(selectable) - (scope or CURRENT_SCOPE).in_scope
