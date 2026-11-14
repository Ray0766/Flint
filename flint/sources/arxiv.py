"""arXiv 适配器（M1-014，TrendSource 侧）。

- 数据端点：export.arxiv.org Atom API；stdlib ElementTree 解析（S3 清单外零新增依赖）。
- 当日关键词候选：每 entry 产出一条 TrendItem（keyword=标题小写、url=abs 链接、
  score=1.0——arXiv 无热度量纲，计数语义留给热度层的源内归一，A2）。
- 类目过滤配置化：categories 集合注入（None = 不过滤）；XML 结构偏离抛 ParseDrift。
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import httpx

from flint.domain.models import TrendItem
from flint.region.source_constants import (
    SOURCE_CONSTANT_REGIONS,
)
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError

_ATOM_NS = "{http://www.w3.org/2005/Atom}"
#: OpenSearch 命名空间。`CN-05` 实测：真响应的根元素上逐字声明着它，
#: 而 `<opensearch:totalResults>` 是**分辨「查过了、那天没有」与「结构变了」的唯一信号**。
_OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"

DEFAULT_CATEGORIES: frozenset[str] = frozenset({"cs.AI", "cs.LG"})


def _utcnow() -> datetime:
    return datetime.now(UTC)


def parse_atom(
    body: str,
    categories: frozenset[str] | None,
    now: datetime | None = None,
    region: str = SOURCE_CONSTANT_REGIONS[0],
) -> list[TrendItem]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as err:
        raise ParseDrift("arxiv", f"invalid Atom XML: {err}") from err
    if root.tag != f"{_ATOM_NS}feed":
        raise ParseDrift("arxiv", f"root element is {root.tag!r}, expected Atom feed")

    # ## 「查过了、那天没有」与「结构变了」NEVER 合并（`CN-05`）
    #
    # 改前：feed 里一条 entry 都没有时，这里安安静静地回 `[]`——
    # 而**那与「查询写坏了」「上游改了结构」在盘上长得一模一样**。
    #
    # `CN-05` 实测把这件事逼了出来：查昨天（2026-08-09，**周日**）回 0 条，
    # 而查一周前那一天回 120 条、不带日期过滤回 19 万条。
    # 也就是说**查询写法是对的，是 arXiv 周末不发布**——
    # 而当时唯一能看出这一点的办法是人工再打两发。
    #
    # `totalResults` 就是那个信号：它在且为 0 = 查过了、那天确实没有；
    # **它整个不在 = 上游换了结构**，那时回 `[]` 才是撒谎。
    total = root.find(f"{_OPENSEARCH_NS}totalResults")
    if total is None or not (total.text or "").strip().isdigit():
        raise ParseDrift(
            "arxiv",
            "feed without opensearch:totalResults —— "
            "拿不到它就分不出「那天没有」与「查询坏了」")
    captured_at = now if now is not None else _utcnow()
    items: list[TrendItem] = []
    for entry in root.findall(f"{_ATOM_NS}entry"):
        title_node = entry.find(f"{_ATOM_NS}title")
        id_node = entry.find(f"{_ATOM_NS}id")
        if title_node is None or id_node is None or not title_node.text or not id_node.text:
            raise ParseDrift("arxiv", "entry without title or id")
        terms = {
            c.get("term", "")
            for c in entry.findall(f"{_ATOM_NS}category")
        }
        if categories is not None and not (terms & categories):
            continue
        items.append(
            TrendItem(
                keyword=" ".join(title_node.text.split()).lower(),
                score=1.0,
                region=region,
                url=id_node.text.strip(),
                captured_at=captured_at,
            )
        )
    return items


class ArxivSource:
    source_id: str = "arxiv"

    def __init__(
        self,
        client: httpx.Client,
        now: Callable[[], datetime] = _utcnow,
        categories: frozenset[str] = DEFAULT_CATEGORIES,
    ) -> None:
        self._client = client
        self._now = now
        self._categories = categories

    #: 回看几天，且**不含当天**。
    #:
    #: arXiv 有**公告延迟**：当天提交的论文当天并不可按 `submittedDate` 检索到，
    #: 周末更是整天不公告（`CN-05` 实测：查 2026-08-09 周日回 0 条，
    #: 而同一写法查一周前那天回 120 条）。
    #: 以「当天」为窗口时，凌晨跑必空、周末跑必空——**那不是「今天没有」，
    #: 是这个窗口问不出东西来**。
    #: 7 天覆盖得住公告延迟与整个周末；再宽的话当日榜会被上周的论文占满。
    LOOKBACK_DAYS = 7

    def _url(self, day: date) -> str:
        """近 `LOOKBACK_DAYS` 天提交、**截到昨天**（见 `LOOKBACK_DAYS` 的理由）。"""
        since = (day - timedelta(days=self.LOOKBACK_DAYS)).strftime("%Y%m%d")
        until = (day - timedelta(days=1)).strftime("%Y%m%d")
        return (
            "https://export.arxiv.org/api/query"
            f"?search_query=cat:cs.AI+AND+submittedDate:[{since}0000+TO+{until}2359]"
            "&max_results=50"
        )

    def fetch_daily(self, day: date) -> list[TrendItem]:
        response = self._client.get(self._url(day))
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        return parse_atom(response.text, categories=self._categories, now=self._now())
