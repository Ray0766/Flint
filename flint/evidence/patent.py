"""PatentSource 适配器（M2-010，冻结协议 PatentSource）。

meta 携同族规模 family_size 与法律状态 legal_status（B4 专利评分变体分量，
M2-025 消费）；结构漂移抛 ParseDrift。
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


def parse_patents(body: str, now: datetime, source_id: str = "patents") -> list[Doc]:
    try:
        payload: Any = json.loads(body)
        patents = payload["patents"]
    except (json.JSONDecodeError, KeyError, TypeError) as err:
        raise ParseDrift(source_id, f"patent schema mismatch: {err}") from err
    docs: list[Doc] = []
    for item in patents:
        try:
            title = item["title"]
            url = item["url"]
            family_size = int(item["family_size"])
            legal_status = item["legal_status"]
            published = date.fromisoformat(item["date"])
        except (KeyError, TypeError, ValueError) as err:
            raise ParseDrift(source_id, f"patent entry mismatch: {err}") from err
        docs.append(
            Doc(
                doc_id=doc_id_for(url),
                source_id=source_id,
                kind="patent",
                title=title,
                url=url,
                published_at=published,
                meta=base_meta(now, family_size=family_size, legal_status=legal_status),
                origin="retrieved",
                access="public",
            )
        )
    return docs


class PatentSearchSource:
    source_id: str = "patents"

    def __init__(
        self, client: httpx.Client, now: Callable[[], datetime] = _utcnow
    ) -> None:
        self._client = client
        self._now = now

    def search(self, q: Query, since: date | None, limit: int) -> list[Doc]:
        url = f"https://api.patents.example/v1/search?q={plus_query(q.text)}&rows={limit}"
        response = self._client.get(url)
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        docs = parse_patents(response.text, now=self._now(), source_id=self.source_id)
        if since is not None:
            docs = [d for d in docs if d.published_at is not None and d.published_at >= since]
        return docs
