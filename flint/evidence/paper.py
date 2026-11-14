"""PaperSource 适配器：Crossref works（M2-009，冻结协议 PaperSource）。

- Doc 全字段非空、origin=retrieved/access=public；meta 携 cited_by/venue/
  fetched_at（统一溯源）。
- dedupe_by_doi_url：DOI 优先、URL 兜底的合并去重（多 query 合并的共用件，
  M2-019 复用）；首见保序。
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


def dedupe_by_doi_url(docs: list[Doc]) -> list[Doc]:
    seen: set[str] = set()
    result: list[Doc] = []
    for doc in docs:
        key = str(doc.meta.get("doi") or "") or doc.url
        if key in seen:
            continue
        seen.add(key)
        result.append(doc)
    return result


class CrossrefPaperSource:
    source_id: str = "crossref"

    def __init__(
        self, client: httpx.Client, now: Callable[[], datetime] = _utcnow
    ) -> None:
        self._client = client
        self._now = now

    def _url(self, q: Query, limit: int) -> str:
        return f"https://api.crossref.org/works?query={plus_query(q.text)}&rows={limit}"

    def search(self, q: Query, since: date | None, limit: int) -> list[Doc]:
        response = self._client.get(self._url(q, limit))
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        try:
            payload: Any = json.loads(response.text)
            items = payload["message"]["items"]
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise ParseDrift(self.source_id, f"works schema mismatch: {err}") from err
        now = self._now()
        docs: list[Doc] = []
        for item in items:
            try:
                title = item["title"][0]
                url = item["URL"]
                doi = item["DOI"]
                parts = item["published"]["date-parts"][0]
            except (KeyError, IndexError, TypeError) as err:
                raise ParseDrift(self.source_id, f"work entry mismatch: {err}") from err
            published = date(parts[0], parts[1] if len(parts) > 1 else 1,
                             parts[2] if len(parts) > 2 else 1)
            if since is not None and published < since:
                continue
            docs.append(
                Doc(
                    doc_id=doc_id_for(url),
                    source_id=self.source_id,
                    kind="paper",
                    title=title,
                    url=url,
                    published_at=published,
                    meta=base_meta(
                        now,
                        doi=doi,
                        cited_by=item.get("is-referenced-by-count", 0),
                        venue=(item.get("container-title") or [""])[0],
                    ),
                    origin="retrieved",
                    access="public",
                )
            )
        return dedupe_by_doi_url(docs)
