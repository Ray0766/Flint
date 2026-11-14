"""`web/app/globals.css` 的**小节边界**，以及三条按小节判的样式规则。

> 本模块由 v0.4.1 第 6 批的 `FIX-13` 建（`docs/steward/tasks-v041-b6.json`）。

## 它治的是什么

`globals.css` 是**追加式**的：`UI-01` 写完之后，`DS-02` 追加了卡面版式、
`PLAZA-01` 追加了堆叠与网格、`CHAIN-03` 追加了主题两屏、`REGION-10` 追加了筛选器。

而 `UI-01` 那三条判据取的是「起点标记 → **文件尾**」——
于是**后来每一段都被当成 UI-01 判**。第 5 批就地收敛成「起点 → 下一条分隔线」，
本卡把这件事固化：边界只有一处定义，四份判据共用它。

## 为什么必须只有一处

改前有**四份**判据各写一遍同一个切法，且都带着同一个魔数：

```python
end = body.find("/* ─────", 8)      # 那个 8 是「跳过自己这条分隔线」
```

四份抄件的后果不是重复劳动，而是**它们迟早不一致**——
而不一致时红的那一份看起来像「产品坏了」。

## 小节长什么样

一条**分隔线注释**开一段，段名写在它下一行（或同一行）里：

```
/* ───────────────────────── DS-02 · 热点卡片 ─────────────────────────
   …说明…
*/
.hotspot-card { … }
```

文件开头到第一条分隔线之间是**头段**（`UI-01` 那一段就在里面）。
`UI-01` 另有自己的起点标记，因为头段里还有 `FB-01`/`FB-02`/`K6-01` 三段前身。
"""
from __future__ import annotations

import re
from typing import Final

#: 分隔线注释的开头。**一处定义**——判据与工具都引它，NEVER 各写一遍。
SECTION_BREAK: Final[str] = "/* ─────"

_COLOUR: Final[re.Pattern[str]] = re.compile(
    r"#[0-9A-Fa-f]{3,8}\b|\brgba?\([^)]*\)|\bhsla?\([^)]*\)")
_SIZE: Final[re.Pattern[str]] = re.compile(r"(?<![-\w])\d+(\.\d+)?(px|rem|em)\b")
_HAIRLINE: Final[re.Pattern[str]] = re.compile(r"\b[12]px\s+(solid|dashed)\b")
_TOKEN_USE: Final[re.Pattern[str]] = re.compile(r"var\((--[a-z0-9-]+)")


def section_starts(css: str) -> list[int]:
    """每条分隔线的起始下标（升序）。头段不在其中——它从 0 开始。"""
    return [m.start() for m in re.finditer(re.escape(SECTION_BREAK), css)]


def section_after(css: str, marker: str) -> str:
    """从 `marker` 起、到**下一条分隔线**为止的那一段。

    这就是改前四份判据各抄一遍的那个切法，现在只有这一处。
    `marker` 找不到时抛——**NEVER 悄悄返回全文**：返回全文的话，
    判据会把整份 css 当成这一段判，而它看起来仍然是绿的（多半没有违规），
    直到某天别的段里出现一处违规，红在一张不相干的卡上。
    """
    start = css.find(marker)
    if start == -1:
        raise ValueError(f"globals.css 里找不到小节起点标记：{marker!r}")
    end = css.find(SECTION_BREAK, start + len(marker))
    return css[start:] if end == -1 else css[start:end]


def strip_comments(css: str) -> str:
    """整块剥掉注释再判。

    `ln.split("/*")[0]` 只砍得掉「注释与代码同一行」那种，砍不掉**跨行的注释块**
    ——而本仓的注释里写着算式与反例（`width: 342px` 是反例），
    不剥的话，**说明问题的那句话会被当成犯下问题**。
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def colour_literals(css: str) -> list[str]:
    """这一段里写死的色值。颜色一律走 `var(--…)`——写死一个 `#1B2A2E`
    的那一刻，暗色主题就在这一处失效了：token 换了它不会跟着换。"""
    return _COLOUR.findall(strip_comments(css))


def bare_sizes(css: str, allowed: tuple[str, ...] = ()) -> list[str]:
    """这一段里写死的字号/间距。

    放行的只有两类：

    1. **1px / 2px 的描边**——`_ds` 没有为发丝线单独出 token，
       把 1px 写成变量只会多一层间接，不会多一分一致性；
    2. **调用方逐个列名的几何值**（`allowed`）：台面高、透视距、网格列底之类，
       `_ds` 的刻度里没有对应 token。

    第 2 类**由调用方给且必须逐个列名**——名单少一条即红，多一条要有人解释。
    在这里给一份公共白名单会让所有段共享同一批例外，
    那时「这个 420px 是谁的」就没人说得清了。
    """
    return [
        line.strip() for line in strip_comments(css).splitlines()
        if _SIZE.search(line)
        and not _HAIRLINE.search(line)
        and not any(value in line for value in allowed)
    ]


def tokens_used(css: str) -> set[str]:
    """这一段引用到的 `--token` 名。"""
    return set(_TOKEN_USE.findall(strip_comments(css)))
