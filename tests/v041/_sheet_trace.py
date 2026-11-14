"""单据留痕的共用判法（`GAUGE-16` 从两处逐字重复的副本收成一处）。

## 为什么收

第 9 批给 `test_main_chain_walk.py` 与 `test_workbench_create.py` 各写了一份
`_STATUS_LINE` / `_status_of` / `_assert_sheet_keeps_its_trace`，**逐字相同**。
两份各自漂移的那天，两张单会按两套规矩判——而它们守的是同一条纪律。
更坏的是：修好其中一份的人会以为自己修好了这条纪律。

文件名以 `_` 开头且不叫 `test_*`：pytest 不会把它当判据文件收集。

## 这份判法守的是什么

**不是 `open` 那个字，是留痕。**

第 9 批那两条判据原来钉的是「这张单必须 open」。单据被**正当地做掉**之后
它们当场变红，**而红的原因是活干完了**——那不是判据该说的话。

该守的是：这张单还在、状态行说得出**是谁在哪一天关的**、
关掉那一刻写下了为什么。所以判**形状**而不是判一个字面量。

## NEVER 用行号找状态行

`splitlines()[2]` 那种写法把「状态行在第几行」当成了纪律的一部分——
而它不是：单据头上多一行说明，判据就红，**而红的原因是排版**。
`GAUGE-16` 之前 `test_main_chain_walk.py` 里那条就是这么写的。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]

#: `**状态** <状态> · <日期> · `<卡号>``。三样缺一不可。
_STATUS_LINE = re.compile(
    r"^\*\*状态\*\*[:：]?\s*(open|closed|blocked)\s*·\s*"
    r"(\d{4}-\d{2}-\d{2})\s*·\s*`([^`]+)`")


def status_of(text: str) -> tuple[str, str, str]:
    """单据状态行 →（状态, 日期, 哪张卡）。**读不出就抛**，NEVER 猜一个默认值。

    读不出时抛而不是回 `("unknown", …)`：回默认值的话，调用方那句
    `if state == "closed"` 会安静地走 else 分支，于是一张状态行烂掉的单
    **照样全绿**——而那正是这条判法要拦的事。
    """
    line = next((ln for ln in text.splitlines()
                 if ln.startswith("**状态**")), "")
    hit = _STATUS_LINE.match(line)
    if hit is None:
        raise ValueError(f"状态行读不出「谁在哪一天」：{line!r}")
    return hit.group(1), hit.group(2), hit.group(3)


def assert_sheet_keeps_its_trace(path: Path) -> tuple[str, str, str]:
    """这张单**还在**，且它的状态行留得住痕。关掉的还要写得出关掉的理由。"""
    assert path.exists(), f"这件事没留痕：{path.name}"
    text = path.read_text(encoding="utf-8")
    state, day, card = status_of(text)
    date.fromisoformat(day)          # 日期得是一个真日期，NEVER 是「最近」这种话
    assert card.strip(), "状态行没说是哪张卡"
    if state == "closed":
        # 关掉之后**必须写得出为什么**——只把 open 改成 closed 的那种关法，
        # 与「这张单从来没存在过」在盘上留下的信息一样多。
        assert "## 关闭" in text, f"{path.name} 关掉了，却没写关闭那一节"
        assert card in text.split("## 关闭", 1)[1], (
            f"{path.name} 的关闭那一节没点名 {card}")
    return state, day, card


def assert_every_island_is_accounted_for(
    graph: dict[str, Any], islands: list[str]
) -> None:
    """每座孤岛逐条交代：一条理由 + 一张留得住痕的单。

    ## 为什么单独一个函数

    `GAUGE-16` 之前这段逻辑写在 `assert report.islands == []` 的**下一行**——
    循环体**永远执行不到**。而「每座孤岛要有 `island_reason` 与 `island_sheet`」
    这条纪律，全仓只有那四行在守：等于**今天没有任何东西在守它**。

    抽出来之后，清零那条断言排在它**后面**（先逐条交代，再判清零），
    而阴性对照可以拿一张人造的图直接喂它——不用真的先长出一座孤岛。

    ## 报错 MUST 说得出哪一座缺什么

    只说「有孤岛没交代」的话，读的人还要自己去图里翻。所以先收集、再一次报全。
    """
    by = {s["route"]: s for s in graph["screens"]}
    unaccounted: list[str] = []
    for route in islands:
        screen = by.get(route)
        if screen is None:
            unaccounted.append(f"{route}：图里根本没有这一屏")
            continue
        if not screen.get("island_reason"):
            unaccounted.append(f"{route}：没写为什么走不到（缺 island_reason）")
            continue
        rel = str(screen.get("island_sheet", "")).strip()
        if not rel:
            unaccounted.append(f"{route}：没挂单据（缺 island_sheet）")
            continue
        try:
            state, _day, _card = assert_sheet_keeps_its_trace(REPO / rel)
        except (AssertionError, ValueError) as exc:
            unaccounted.append(f"{route}：单据留不住痕（{exc}）")
            continue
        if state == "closed":
            # **孤岛挂一张已经关掉的单 = 这座岛今天没有主。**
            # 这一条是第 9 批那句 `**状态** open` 断言原本想守的东西——
            # 那时它被写成「单据必须 open」，于是单据被正当关掉时它红，
            # 而红的原因是活干完了。规矩没错，位置错了：
            # 「这张单该不该开着」取决于**有没有一座岛还指着它**，
            # 而不取决于这张单自己。
            unaccounted.append(
                f"{route}：挂的单已经关了（{rel}）——这座岛今天没有主")

    assert unaccounted == [], "这些孤岛没交代清楚：" + " · ".join(unaccounted)
