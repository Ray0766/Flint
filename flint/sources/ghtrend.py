"""GitHub Trending 适配器（M1-013，TrendSource 协议）。

- 数据端点：GitHub search API（按 created+stars 排序）——响应含
  full_name / topics / description，支撑关键词映射三来源（验收硬条款）。
- 映射规则：name（仓库短名，-/_ 归一为空格）> topic（原样小写）>
  description（字母词元、停用词过滤、长度 >=3）；同词多来源按此优先级去重。
- 429 → RateLimitedError；5xx → SourceFetchError；schema 偏离 → ParseDrift。
"""
from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import httpx

from flint.domain.models import TrendItem
from flint.region.source_constants import (
    SOURCE_CONSTANT_REGIONS,
)
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError

KeywordOrigin = Literal["name", "topic", "description"]

_STOPWORDS = frozenset(
    {"for", "and", "the", "with", "via", "from", "into", "onto", "using"}
)


@dataclass(frozen=True)
class DerivedKeyword:
    text: str
    origin: KeywordOrigin


def _name_keyword(full_name: str) -> str:
    short = full_name.rsplit("/", 1)[-1]
    return " ".join(short.replace("-", " ").replace("_", " ").split()).lower()


def _description_terms(description: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for ch in description.lower():
        if ch.isalpha():
            current.append(ch)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    seen: list[str] = []
    for tok in tokens:
        if len(tok) >= 3 and tok not in _STOPWORDS and tok not in seen:
            seen.append(tok)
    return seen


def map_repo_keywords(repo: Mapping[str, Any]) -> list[DerivedKeyword]:
    """Three-origin keyword mapping with name > topic > description precedence."""
    result: list[DerivedKeyword] = []
    seen: set[str] = set()

    def add(text: str, origin: KeywordOrigin) -> None:
        if text and text not in seen:
            seen.add(text)
            result.append(DerivedKeyword(text=text, origin=origin))

    add(_name_keyword(str(repo.get("full_name", ""))), "name")
    for topic in repo.get("topics", []) or []:
        add(str(topic).strip().lower(), "topic")
    for term in _description_terms(str(repo.get("description") or "")):
        add(term, "description")
    return result


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GitHubTrendingSource:
    source_id: str = "ghtrend"

    def __init__(
        self,
        client: httpx.Client,
        now: Callable[[], datetime] = _utcnow,
        per_page: int = 15,
    ) -> None:
        self._client = client
        self._now = now
        self._per_page = per_page

    #: 回看几天。**7 天**：GitHub 的「trending」本来就是一个窗口概念，
    #: 一天太窄（`created` 精确到日，当天新建又拿到星标的仓极少），
    #: 一个月太宽（榜会被一两个爆款钉死，看不出「最近在热什么」）。
    #: 这个数写在这里而不是散在调用方——改它是一次口径变更，要有人来这里改。
    LOOKBACK_DAYS = 7

    def _url(self, day: date) -> str:
        """近 `LOOKBACK_DAYS` 天创建、按星标排序。

        ## 改前那个窗口**结构上恒空**

        改前是 `created:>{day}`——查的是「创建晚于**今天**」的仓。
        以「今天」为下界时，能落进这个窗口的只有当天当刻之后新建的仓；
        `CN-06` 那次真跑（UTC 03:37）实测 `total_count: 0`。

        **它不是「今天恰好没有」，是这个查询问不出东西来。**
        而当时回执照旧记 `ok`——盘上看不出这一源是空的（`CN-07` 治的正是这个）。
        """
        since = day - timedelta(days=self.LOOKBACK_DAYS)
        return (
            "https://api.github.com/search/repositories"
            f"?q=created:>{since.isoformat()}&sort=stars&order=desc"
            f"&per_page={self._per_page}"
        )

    def fetch_daily(self, day: date) -> list[TrendItem]:
        response = self._client.get(self._url(day))
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        try:
            payload: Any = json.loads(response.text)
            repos = payload["items"]
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise ParseDrift(self.source_id, f"search schema mismatch: {err}") from err
        captured_at = self._now()
        items: list[TrendItem] = []
        emitted: set[str] = set()
        for repo in repos:
            try:
                stars = float(repo["stargazers_count"])
                html_url = repo["html_url"]
            except (KeyError, TypeError) as err:
                raise ParseDrift(self.source_id, f"repo entry mismatch: {err}") from err
            if stars <= 0 or not html_url:
                raise ParseDrift(self.source_id, "empty stars or html_url")
            for derived in map_repo_keywords(repo):
                if derived.text in emitted:
                    continue
                emitted.add(derived.text)
                items.append(
                    TrendItem(
                        keyword=derived.text,
                        score=stars,
                        region=SOURCE_CONSTANT_REGIONS[0],
                        url=html_url,
                        captured_at=captured_at,
                    )
                )
        return items
