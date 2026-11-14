"""微博热搜适配器（M1-012 建，`CN-04` 按真实榜单重写解析）。

- 数据端点：`s.weibo.com/top/summary` 榜单 HTML，selectolax 解析。
- 取数前 MUST 先走访客握手（`flint/sources/weibo_visitor.py`，`DEC-053` 授权）——
  不握手的话上游 302 弹到访客系统，拿回来的是一段 JS。
- 429 → `RateLimitedError`；其余非 200 → `SourceFetchError`；
  结构变化 → `ParseDrift`。三类不增不减不改名。

## 真榜有四种行，合成夹具只有一种（`CN-04` 第三轮探测实证）

第一次拿到真页面（`fixtures/_probe/weibo/real-board.html`，52 行）才发现，
`M1-012` 那版解析器是照合成夹具写的，**四种行里有三种会让它当场抛**：

| 行 | 真实长相 | 改前 | 改后 |
|---|---|---|---|
| 置顶行（1 行） | `td-01` 是 `<i class="icon-top">`，**td-02 没有热度 span** | 抛 `ParseDrift` | **不入榜**，计数 |
| 热度空着 | span 在，文本是空的 | 抛 `ParseDrift` | 与置顶同档：**缺席 → 不入榜** |
| 广告行（1 行） | `topic_ad=1`、`href="javascript:void(0);"`、`td-01` 是 `•`、span 空 | 抛 `ParseDrift` | **不入榜**，计数 |
| 带类别前缀（10 行） | `<span>盛典 305559</span>` | `float()` 抛 | 取尾部数字 |
| 纯数字（40 行） | `<span>216585</span>` | 正常 | 正常 |

### 置顶行为什么**不入榜**而不是入榜给个 0

它是一条**真的热搜**（有词面、有链接），只是上游不给热度。
两条 NEVER 卡死了另外两种做法（`CN-04` acceptance 第 11 条）：
**NEVER 因此判整页漂移**（整页扔掉，为的是一行没有数字）、
**NEVER 给它编一个热度**（`0` 不是「没有」，`0` 是「热度为零」，
它会排到榜尾，而它实际上在榜首）。

`TrendItem.score` 是必填 `float`，没有第三态可用。所以选**不入榜**：
少一条真热搜，而**一个字的谎都没说**。它被跳过这件事**是可见的**——
`parse_board` 数得出跳了几行，`skipped_rows()` 交出来。

### 「缺席」与「损坏」分开判

热度**没给**（没有 span，或 span 空着）→ 跳这一行。
热度**给了但不是数**（`<span>敬请期待</span>`）→ `ParseDrift`。

合成一档的话两种都跳：上游哪天把热度换成一段文案，
我们会**安静地少掉半张榜**，而每一条剩下的都看起来是对的。

### 广告行不入榜是另一回事

它**根本不是热搜**：`topic_ad=1` 是上游自己的标记，`href` 是
`javascript:void(0);`（点了不去任何地方）。把它当热点入榜，
广场上会出现一张点不开的卡。判它靠**结构标记**而不是靠「span 是空的」——
靠空 span 的话，哪天上游让某条真热搜的热度暂时空着，它会被当成广告丢掉。

### 底线守卫：跳太多就是漂移

跳过是给**已知的两种非榜行**留的口子，不是给「解析不动」留的。
所以留一条底线：**一条都没读出来**、或者**丢掉的比读到的还多**时抛 `ParseDrift`。

判比例而不是判一个绝对条数：绝对条数是拍出来的——上游哪天把榜缩到 8 行，
写死的下限会把一张完全正常的榜判成漂移（只喂一行的单测也会被它误伤，实测撞上过）。
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx
from selectolax.parser import HTMLParser

from flint.domain.models import TrendItem
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError

_BOARD_URL = "https://s.weibo.com/top/summary?cate=realtimehot"
_BASE = "https://s.weibo.com"


def _utcnow() -> datetime:
    return datetime.now(UTC)


#: 热度 span 的尾部数字。真榜里 10 行长这样：`盛典 305559`。
_HEAT_TAIL = re.compile(r"(\d+)\s*$")


def _is_ad_row(cell: Any) -> bool:
    """广告行：靠**上游自己的结构标记**判，NEVER 靠「热度是空的」判。

    靠空热度判的话，哪天某条真热搜的数字暂时缺了，它会被当成广告丢掉——
    而那是一条真的热点，用户在别处看得到它、在我们这里看不到。
    """
    anchor = cell.css_first("a")
    if anchor is None:
        return False
    attrs = anchor.attributes
    href = attrs.get("href") or ""
    return "topic_ad=1" in (attrs.get("href_to") or "") or href.startswith("javascript:")


def parse_board(html: str, now: datetime) -> list[TrendItem]:
    tree = HTMLParser(html)
    cells = tree.css("td.td-02")
    if not cells:
        raise ParseDrift("weibo", "no td.td-02 cells found on the board page")
    items: list[TrendItem] = []
    skipped: list[str] = []
    for cell in cells:
        anchor = cell.css_first("a")
        if anchor is None:
            raise ParseDrift("weibo", "td-02 cell without keyword anchor")
        keyword = (anchor.text() or "").strip()
        if _is_ad_row(cell):
            # 不是热搜。**不入榜也不算漂移**——它本来就不该在榜上。
            skipped.append(f"ad:{keyword[:20]}")
            continue
        href = anchor.attributes.get("href") or ""
        if not keyword or not href:
            raise ParseDrift("weibo", "empty keyword text or href")
        heat_node = cell.css_first("span")
        heat_text = (heat_node.text() or "").strip() if heat_node is not None else ""
        if not heat_text:
            # **缺席**：置顶行没有 span，某些行 span 空着——两者是同一件事，
            # 上游这一行没给热度。跳过，**NEVER 编一个**（见文件头）。
            skipped.append(f"pinned:{keyword[:20]}")
            continue
        tail = _HEAT_TAIL.search(heat_text)
        if tail is None:
            # **损坏**：字段在，而里面的东西不是热度了。这是真漂移——
            # 与「缺席」分开判：缺席跳一行，损坏喊一声。
            # 合成一档的话，上游把热度换成一段文案时我们会安静地少掉半张榜。
            raise ParseDrift("weibo", f"non-numeric heat value: {heat_text!r}")
        # 真榜里热度前面可能带类别词（`盛典 305559`）。取的是**同一个数**，
        # 不是另算一个——所以这不是编数据，是读对位置。
        score = float(tail.group(1))
        items.append(
            TrendItem(
                keyword=keyword,
                score=score,
                region="CN",
                url=_BASE + href if href.startswith("/") else href,
                captured_at=now,
            )
        )
    # **底线守卫**：跳过是给已知的两种非榜行留的口子，不是给「解析不动」留的。
    #
    # 判的是**比例而不是一个绝对条数**：绝对条数是拍出来的——
    # 真榜今天 52 行，明天上游把榜缩到 8 行的话，一个写死的下限会把
    # 一张完全正常的榜判成漂移；而只喂一行的单测也会被它误伤（实测撞上了）。
    # 「一条都没读出来」与「丢掉的比读到的还多」才是真信号。
    if cells and not items:
        raise ParseDrift(
            "weibo",
            f"no rankable rows out of {len(cells)} (skipped: {skipped[:5]})")
    if len(skipped) > len(items):
        raise ParseDrift(
            "weibo",
            f"skipped {len(skipped)} rows but only ranked {len(items)} "
            f"(skipped: {skipped[:5]}) — the board structure changed")
    _LAST_SKIPPED.clear()
    _LAST_SKIPPED.extend(skipped)
    return items


#: 最近一次解析跳过了哪些行。**跳过必须是可见的**——
#: 不可见的跳过与「上游没给这一条」在盘上长得一模一样。
_LAST_SKIPPED: list[str] = []


def skipped_rows() -> list[str]:
    """最近一次 `parse_board` 跳过的行（置顶 / 广告），供降级说明与判据读。"""
    return list(_LAST_SKIPPED)


class WeiboHotSource:
    """榜单取数。**真实抓取前 MUST 先握手**（`DEC-053`）。

    ## 握手是注进来的，不是写死的

    `before_fetch` 默认 `None`，因为**回放路上没有握手那两跳**：
    夹具里录的只有榜单那一次往返，默认去握手的话，
    每一条回放判据都会因为「找不到 genvisitor 的录制」而红——
    而那条红说的不是真问题。

    所以默认不握，**由真实取数那一侧显式注进来**
    （`fixtures/_record_cn_real.py`）。这与「忘了握手」长得不一样：
    忘了的话上游 302 弹到访客系统，解析当场 `ParseDrift` 并说
    「no td.td-02 cells」——那句话读起来就是「你没握手」。
    """

    source_id: str = "weibo"

    def __init__(
        self,
        client: httpx.Client,
        now: Callable[[], datetime] = _utcnow,
        before_fetch: Callable[[httpx.Client], object] | None = None,
    ) -> None:
        self._client = client
        self._now = now
        self._before_fetch = before_fetch

    def fetch_daily(self, day: date) -> list[TrendItem]:
        if self._before_fetch is not None:
            # 握手失败抛 `VisitorHandshakeFailed`（`SourceFetchError` 的子类）——
            # 降级显示上它与榜单 5xx 是同一件事：这一源今天缺席。
            self._before_fetch(self._client)
        response = self._client.get(_BOARD_URL)
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        return parse_board(response.text, now=self._now())
