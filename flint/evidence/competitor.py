"""CompetitorSource 适配器（M2-012，冻结协议 CompetitorSource）。

- 每条竞品 Doc 必带可达来源 url（B 档「各有可达来源」的素材面）。
- normalize_competitor_name：小写 + 空白折叠 + 尾部标点清理——同名变体
  去重（首见保序），M2-030 竞品抽取复用。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from flint.domain.models import Doc, Query
from flint.evidence.common import base_meta, doc_id_for, plus_query
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError


def _utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_competitor_name(name: str) -> str:
    cleaned = " ".join(name.lower().split())
    cleaned = cleaned.replace(",", "").replace("·", " ")
    while cleaned and cleaned[-1] in ".!?、。":
        cleaned = cleaned[:-1].rstrip()
    return cleaned


class ProductSearchSource:
    source_id: str = "products"

    def __init__(
        self, client: httpx.Client, now: Callable[[], datetime] = _utcnow
    ) -> None:
        self._client = client
        self._now = now

    def search(self, q: Query, limit: int) -> list[Doc]:
        url = f"https://api.products.example/search?q={plus_query(q.text)}&limit={limit}"
        response = self._client.get(url)
        if response.status_code == 429:
            raise RateLimitedError(self.source_id, 429, response.text)
        if response.status_code != 200:
            raise SourceFetchError(self.source_id, response.status_code, response.text)
        try:
            payload: Any = json.loads(response.text)
            results = payload["results"]
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise ParseDrift(self.source_id, f"product schema mismatch: {err}") from err
        now = self._now()
        docs: list[Doc] = []
        seen_names: set[str] = set()
        for item in results:
            try:
                name = item["name"]
                link = item["url"]
                last_activity = item["last_activity"]
            except (KeyError, TypeError) as err:
                raise ParseDrift(self.source_id, f"product entry mismatch: {err}") from err
            if not link:
                raise ParseDrift(self.source_id, f"competitor {name!r} without source url")
            normalized = normalize_competitor_name(name)
            if normalized in seen_names:
                continue
            seen_names.add(normalized)
            docs.append(
                Doc(
                    doc_id=doc_id_for(link),
                    source_id=self.source_id,
                    kind="product",
                    title=name,
                    url=link,
                    published_at=None,
                    meta=base_meta(
                        now,
                        last_activity=last_activity,
                        description=item.get("description", ""),
                    ),
                    origin="retrieved",
                    access="public",
                )
            )
        return docs
