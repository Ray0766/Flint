"""NewsSource 适配器（M2-011，冻结协议 NewsSource）。

meta 携媒体等级 media_tier 与独立信源数 independent_sources（B4 新闻评分
变体分量，M2-025 消费）；发布日期解析容错（解析不出返回 None，不猜日期）。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

import httpx

from flint.domain.models import Doc, Query
from flint.evidence.common import base_meta, doc_id_for, plus_query
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError


def _utcnow() -> datetime:
    return datetime.now(UTC)


def parse_published_date(raw: str) -> date | None:
    text = raw.strip()
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


class NewsApiSource:
    source_id: str = "news"

    def __init__(
        self, client: httpx.Client, now: Callable[[], datetime] = _utcnow
    ) -> None:
        self._client = client
        self._now = now

    def search(self, q: Query, since: date | None, limit: int) -> list[Doc]:
        url = f"https://api.news.example/v2/everything?q={plus_query(q.text)}&pageSize={limit}"
        response = self._client.get(url)
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        try:
            payload: Any = json.loads(response.text)
            articles = payload["articles"]
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise ParseDrift(self.source_id, f"news schema mismatch: {err}") from err
        now = self._now()
        docs: list[Doc] = []
        for item in articles:
            try:
                title = item["title"]
                link = item["url"]
                tier = int(item["media_tier"])
                independent = int(item["independent_sources"])
            except (KeyError, TypeError, ValueError) as err:
                raise ParseDrift(self.source_id, f"article entry mismatch: {err}") from err
            published = parse_published_date(str(item.get("publishedAt", "")))
            if since is not None and (published is None or published < since):
                continue
            docs.append(
                Doc(
                    doc_id=doc_id_for(link),
                    source_id=self.source_id,
                    kind="news",
                    title=title,
                    url=link,
                    published_at=published,
                    meta=base_meta(now, media_tier=tier, independent_sources=independent),
                    origin="retrieved",
                    access="public",
                )
            )
        return docs
