"""Google Trends 适配器（M1-011 建，`CN-04` / `DEC-054` 重建取数路）。

## 为什么整条取数路换掉

原来打的是 `trends/api/dailytrends`（JSON，带 `)]}'` 反劫持前缀）。
`CN-01` 首次实跑时它回 **404**——**那个端点已被 Google 下线**。
`CN-04` 探测（`DEC-052` 窗口，7/20 留痕在 `fixtures/_probe/gtrends/`）实测：

| 端点 | 实测 |
|---|---|
| `trends/api/dailytrends?...`（旧） | 404，已下线 |
| `trending/rss?geo=CN` | **400** |
| `trending/rss?geo=US` / `geo=HK` / `geo=TW` | **200 · `text/xml`** |

## `geo=HK` 采集、`region` 落 `HK`——`DEC-056` 之后两者一致了

**Google 不编大陆榜**（`geo=CN` 回 400）。这是上游边界，换任何客户端都变不出来。

`DEC-054` 当时的裁决是：采 `geo=HK`、`region` 落 `CN`，
把它定义为「华语圈港区榜代理」，并靠三件东西扛住诚实性
（DEC 文本明写代理 · manifest 记真实 URL · 屏上署名「Google 趋势（港区）」）。

**`DEC-056`（owner 2026-08-10）撤销了那条代理口径**——
它触发的正是 `DEC-054` 自己写下的退出条件：「下一版做多区时本代理口径撤销、改真区」。

今天：**CN 区 = 微博，HK 区 = Google 趋势**，`region` 落 `HK`，
采集地区与呈现地区**一致**，不再需要那个代理说法。
`TrendItem.url` 照旧带真实的 `geo=HK` 地址——**那一条从来没变过**。

## `ht:approx_traffic` 是**区间下界**，NEVER 编精确值

上游给的是 `100+` / `200+` 这种形状——它说的是「至少这么多」。
`parse_traffic` 因此**照实存下界**：`"200+"` → `200.0`。
NEVER 把它当精确值，也 NEVER 拿排名倒算一个假热度（`CN-04` acceptance 逐字）。

## 错误分类一一对应（不增不减不改名）

429 → `RateLimitedError`；其余非 200 → `SourceFetchError`；
结构变化 → `ParseDrift`。三类与 `flint/jobs/ingest.py` 的 `DegradationNote`
三类**一处定义**，本次重建一个字都没动它们。
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from xml.etree import ElementTree

import httpx

from flint.domain.models import TrendItem
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError

#: RSS 里 `ht:` 前缀的命名空间（响应根元素上逐字声明的那一个）。
_HT_NS = "https://trends.google.com/trending/rss"

#: **真正去抓的地区**。`DEC-054`：Google 没有大陆榜，本版采港区作代理。
#: 它与 `EMIT_REGION` 分成两个常量而不是一个——两者今天不同，
#: 合成一个的话，下一版「改真区」时没人说得清该改哪一个。
FETCH_GEO = "HK"

#: **落库的地区**。`DEC-056`：HK 区 = Google 趋势（`DEC-054` 的代理口径已撤销）。
EMIT_REGION = "HK"

#: 供 `provenance` 与前端署名用：这一源今天在屏上叫什么。
#:
#: `DEC-056` 之后**去掉了「（港区）」那个后缀**。它当初是 `DEC-054` 代理口径的第三条腿——
#: 那时这一源的数据采自 HK 而**落在 CN 区**，署名是用户那一侧唯一能看出这件事的地方。
#: 两区分家之后 region 本身就是 HK，**再把地区缀进源名字里，是把两根正交轴拧成一根**
#: （`PRINCIPLES#A3`：源与地区各是一根轴）。
SOURCE_DISPLAY_NAME = "Google 趋势"

_TRAFFIC_MULTIPLIERS = {"K": 1_000.0, "M": 1_000_000.0, "B": 1_000_000_000.0}


def board_url(geo: str = FETCH_GEO) -> str:
    """真实抓取地址。**provenance 记的就是这一份**（`DEC-054` 第二件）。"""
    return f"https://trends.google.com/trending/rss?geo={geo}"


def parse_traffic(raw: str) -> float:
    """`'200+'` → `200.0`；`'20K+'` → `20000.0`。

    **回的是区间下界**，不是精确值（`DEC-054`）。上游那个 `+` 说的是「至少」，
    所以这里把它读成下界并原样存下界——**NEVER 补一个中位数或上界猜测**。
    """
    text = raw.strip().rstrip("+").replace(",", "")
    if not text:
        raise ParseDrift("gtrends", f"unparseable approx_traffic: {raw!r}")
    multiplier = 1.0
    if text[-1].upper() in _TRAFFIC_MULTIPLIERS:
        multiplier = _TRAFFIC_MULTIPLIERS[text[-1].upper()]
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError as err:
        raise ParseDrift("gtrends", f"unparseable approx_traffic: {raw!r}") from err


@dataclass
class RequestPacer:
    """Minimum-interval pacing with injectable clock/sleep for fake-clock tests."""

    min_interval: float
    now: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _last: float | None = field(default=None, init=False)

    def acquire(self) -> None:
        if self._last is not None:
            elapsed = self.now() - self._last
            remaining = self.min_interval - elapsed
            if remaining > 0:
                self.sleep(remaining)
        self._last = self.now()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def parse_rss(body: str, *, now: datetime, url: str,
              region: str = EMIT_REGION) -> list[TrendItem]:
    """把一份 `trending/rss` 响应解析成条目。

    结构照 `fixtures/_probe/gtrends/*.body` 里那份**真实响应**写：
    `channel/item` 下有 `title` · `ht:approx_traffic` · `pubDate` · `link`。

    任何偏离都抛 `ParseDrift`——**NEVER 静默产出坏数据**（验收硬条款）。
    缺 `approx_traffic` 也算偏离：热度是这一源存在的理由，
    上游哪天不给了，那是一次结构变化，不是一条热度为 0 的热点。
    """
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as err:
        raise ParseDrift("gtrends", f"rss not parseable: {err}") from err

    items = root.findall("./channel/item")
    if not items:
        raise ParseDrift("gtrends", "rss has no channel/item")

    out: list[TrendItem] = []
    for node in items:
        title = (node.findtext("title") or "").strip()
        traffic = node.findtext(f"{{{_HT_NS}}}approx_traffic")
        if not title:
            raise ParseDrift("gtrends", "item without a title")
        if traffic is None:
            raise ParseDrift("gtrends", f"item {title!r} without ht:approx_traffic")
        out.append(TrendItem(
            keyword=title,
            score=parse_traffic(traffic),
            # `DEC-056` 之后落 `HK`——与 `FETCH_GEO` 一致。
            # 两个常量仍然分开（`CN-04` 刻意为之）：**一致不等于同一件事**，
            # 下一版接别的地区时它们会再次分开。
            region=region,
            # **真实抓取地址**，NEVER 编一个 geo=CN 的假地址（`DEC-054` 第二件）。
            url=url,
            captured_at=now,
        ))
    return out


class GoogleTrendsSource:
    source_id: str = "gtrends"
    #: 屏上署名（`FIX-17` 的 `sourceName` 机制取它）。
    display_name: str = SOURCE_DISPLAY_NAME

    def __init__(
        self,
        client: httpx.Client,
        region: str = EMIT_REGION,
        now: Callable[[], datetime] = _utcnow,
        pacer: RequestPacer | None = None,
        geo: str = FETCH_GEO,
    ) -> None:
        self._client = client
        self._region = region
        self._now = now
        self._pacer = pacer
        self._geo = geo

    def _url(self, day: date) -> str:
        """RSS 那条路**不吃日期**——它给的恒是「当下这一份」。

        旧的 `dailytrends` 有 `ed=YYYYMMDD`，所以签名里留着 `day`；
        新端点没有那个参数，**NEVER 硬拼一个上游不认的 query 去装作能选日期**：
        拼上去它照样回今天那一份，而调用方会以为自己取到了那一天。
        取哪一天由灌库那一层按 UTC 日期归档（`E12`），与这里无关。
        """
        return board_url(self._geo)

    def fetch_daily(self, day: date) -> list[TrendItem]:
        if self._pacer is not None:
            self._pacer.acquire()
        url = self._url(day)
        response = self._client.get(url)
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        return parse_rss(response.text, now=self._now(), url=url,
                         region=self._region)
