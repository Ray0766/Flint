"""证伪素材通道（M2-016，PDD v0.2 §4.2 B2）。

三类素材：撤稿记录 / archived 开源项目 / 产品关停新闻。每条产出 Doc，
meta 统一带 refute_intent=True + negative_kind，供 intent="refute" 检索
（M2-020 模板族）与竞品 active_last_12m 反证（M2-031）消费。
"""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import httpx

from flint.domain.models import Doc
from flint.evidence.common import base_meta, doc_id_for
from flint.evidence.news import parse_published_date
from flint.sources.errors import ParseDrift, SourceFetchError

NegativeKind = Literal["retraction", "archived", "shutdown"]


@dataclass(frozen=True)
class NegativeSignal:
    kind: NegativeKind
    doc: Doc


def _get_json(client: httpx.Client, url: str, source_id: str) -> Any:
    response = client.get(url)
    if response.status_code != 200:
        raise SourceFetchError(source_id, response.status_code, response.text)
    try:
        return json.loads(response.text)
    except json.JSONDecodeError as err:
        raise ParseDrift(source_id, f"non-JSON payload: {err.msg}") from err


def fetch_retractions(
    client: httpx.Client, query: str, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> list[NegativeSignal]:
    url = f"https://api.retractions.example/search?q={query.replace(' ', '+')}"
    payload = _get_json(client, url, "retractions")
    signals: list[NegativeSignal] = []
    for item in payload.get("retractions", []):
        doc = Doc(
            doc_id=doc_id_for(item["url"]),
            source_id="retractions",
            kind="paper",
            title=item["title"],
            url=item["url"],
            published_at=parse_published_date(str(item.get("date", ""))),
            meta=base_meta(
                now(),
                refute_intent=True,
                negative_kind="retraction",
                retraction_of=item["original_doi"],
                reason=item.get("reason", ""),
            ),
            origin="retrieved",
            access="public",
        )
        signals.append(NegativeSignal(kind="retraction", doc=doc))
    return signals


def fetch_archived_projects(
    client: httpx.Client, query: str, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> list[NegativeSignal]:
    url = f"https://api.products.example/search?q={query.replace(' ', '+')}&status=archived"
    payload = _get_json(client, url, "products")
    signals: list[NegativeSignal] = []
    for item in payload.get("results", []):
        if not item.get("archived"):
            continue
        doc = Doc(
            doc_id=doc_id_for(item["url"]),
            source_id="products",
            kind="repo",
            title=item["name"],
            url=item["url"],
            published_at=None,
            meta=base_meta(
                now(),
                refute_intent=True,
                negative_kind="archived",
                archived=True,
                last_activity=item.get("last_activity", ""),
            ),
            origin="retrieved",
            access="public",
        )
        signals.append(NegativeSignal(kind="archived", doc=doc))
    return signals


def fetch_shutdown_news(
    client: httpx.Client, query: str, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> list[NegativeSignal]:
    url = (
        f"https://api.news.example/v2/everything?q={query.replace(' ', '+')}+shutdown"
        "&pageSize=5"
    )
    payload = _get_json(client, url, "news")
    signals: list[NegativeSignal] = []
    for item in payload.get("articles", []):
        doc = Doc(
            doc_id=doc_id_for(item["url"]),
            source_id="news",
            kind="news",
            title=item["title"],
            url=item["url"],
            published_at=parse_published_date(str(item.get("publishedAt", ""))),
            meta=base_meta(
                now(),
                refute_intent=True,
                negative_kind="shutdown",
                media_tier=int(item.get("media_tier", 3)),
            ),
            origin="retrieved",
            access="public",
        )
        signals.append(NegativeSignal(kind="shutdown", doc=doc))
    return signals
