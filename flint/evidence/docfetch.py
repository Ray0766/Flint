"""Feature B-2：源无关可插拔文档抓取器（门 2=R1：仅 github + arxiv 公网免费 API）。

- `DocFetcherRegistry` = 复刻 `sources/registry` 的插槽范式：按 source_id 注册 fetcher，
  按 URL 域名分派。weibo/news/付费源**未注册 → UnregisteredSourceError**（缓办，日后
  注册新 fetcher 即接，NEVER 现在实现，问题单登记通道）。
- R1 两家走**官方 API**（api.github.com / export.arxiv.org，ToS 许可的程序化访问）：
  github 取 repo `description`（一行）；arxiv 取 Atom `summary`（摘要）。二者结构化返回，
  非 HTML 正文抓取。限流复用 `sources/throttle`（每源令牌桶）；错误复用 `sources/errors`。
- 抓取只回**内存态** `FetchedSource`（含 summary 供 B-3 抽短 quote_span）；**全文 NEVER 落库**
  （§3.5，问题单 209）——落库仅 Doc 元信息 + Citation 短段（B-1/B-3）。
- 抓取一律走 M1-008 录制回放（S2-7 CI 零联网）：先录真实响应当 fixture，测试离线回放。
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from urllib.parse import urlparse

import httpx

from flint.domain.models import DocKind
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError
from flint.sources.throttle import SourceThrottle

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


@dataclass(frozen=True)
class FetchedSource:
    """抓取结果（内存态）：Doc 元信息 + summary（供 B-3 抽短 span，NEVER 落库全文）。"""

    source_id: str
    kind: DocKind
    title: str
    url: str                 # 规范 html/abs 链接（= 卡 top_link / dedup 键）
    published_at: date | None
    summary: str             # 原始描述/摘要，仅内存；只有短 quote_span 会落库


class DocFetcher(Protocol):
    source_id: str

    def supports(self, url: str) -> bool: ...

    def fetch(self, url: str) -> FetchedSource: ...


class UnregisteredSourceError(Exception):
    """URL 域名无已注册 fetcher（weibo/news/付费源缓办——注册新源即接）。"""


def _parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


class GithubRepoFetcher:
    """github.com/{owner}/{repo} → api.github.com/repos/{owner}/{repo}（repo 元信息）。"""

    source_id = "github"

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def supports(self, url: str) -> bool:
        p = urlparse(url)
        return p.netloc in {"github.com", "www.github.com"} and len(
            [s for s in p.path.split("/") if s]) >= 2

    def _owner_repo(self, url: str) -> tuple[str, str]:
        parts = [s for s in urlparse(url).path.split("/") if s]
        return parts[0], parts[1].removesuffix(".git")

    def fetch(self, url: str) -> FetchedSource:
        owner, repo = self._owner_repo(url)
        api = f"https://api.github.com/repos/{owner}/{repo}"
        resp = self._client.get(api, headers={"Accept": "application/vnd.github+json"})
        if resp.status_code == 429:
            raise RateLimitedError(self.source_id, 429, resp.text)
        if resp.status_code != 200:
            raise SourceFetchError(self.source_id, resp.status_code, resp.text)
        try:
            d = json.loads(resp.text)
            full_name = str(d["full_name"])
            html_url = str(d["html_url"])
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise ParseDrift(self.source_id, f"github repo schema mismatch: {err}") from err
        description = d.get("description")
        return FetchedSource(
            source_id=self.source_id, kind="repo", title=full_name, url=html_url,
            published_at=_parse_date(str(d.get("pushed_at") or "")),
            summary="" if description is None else str(description))


class ArxivFetcher:
    """arxiv.org/abs/{id} → export.arxiv.org/api/query?id_list={id}（Atom 摘要）。"""

    source_id = "arxiv"

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def supports(self, url: str) -> bool:
        p = urlparse(url)
        return p.netloc in {"arxiv.org", "www.arxiv.org"} and "/abs/" in p.path

    def _arxiv_id(self, url: str) -> str:
        return urlparse(url).path.split("/abs/", 1)[1].strip("/")

    def fetch(self, url: str) -> FetchedSource:
        arxiv_id = self._arxiv_id(url)
        api = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
        resp = self._client.get(api)
        if resp.status_code == 429:
            raise RateLimitedError(self.source_id, 429, resp.text)
        if resp.status_code != 200:
            raise SourceFetchError(self.source_id, resp.status_code, resp.text)
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as err:
            raise ParseDrift(self.source_id, f"invalid Atom XML: {err}") from err
        entry = root.find(f"{_ATOM_NS}entry")
        if entry is None:
            raise ParseDrift(self.source_id, "no Atom entry for id")
        title_node = entry.find(f"{_ATOM_NS}title")
        summary_node = entry.find(f"{_ATOM_NS}summary")
        published_node = entry.find(f"{_ATOM_NS}published")
        if title_node is None or title_node.text is None:
            raise ParseDrift(self.source_id, "entry without title")
        summary = "" if summary_node is None or summary_node.text is None else \
            " ".join(summary_node.text.split())
        published = None if published_node is None or published_node.text is None else \
            _parse_date(published_node.text)
        return FetchedSource(
            source_id=self.source_id, kind="paper",
            title=" ".join(title_node.text.split()),
            url=f"https://arxiv.org/abs/{arxiv_id}",
            published_at=published, summary=summary)


class DocFetcherRegistry:
    """按 URL 分派到已注册 fetcher；未注册域名 → UnregisteredSourceError（缓办源）。

    限流可选注入（SourceThrottle）：fetch 前 try_acquire(source_id)，耗尽抛 RateLimitedError。
    """

    def __init__(self, throttle: SourceThrottle | None = None) -> None:
        self._fetchers: list[DocFetcher] = []
        self._throttle = throttle

    def register(self, fetcher: DocFetcher) -> None:
        self._fetchers.append(fetcher)

    def supports(self, url: str) -> bool:
        return any(f.supports(url) for f in self._fetchers)

    def _pick(self, url: str) -> DocFetcher:
        for f in self._fetchers:
            if f.supports(url):
                return f
        raise UnregisteredSourceError(
            f"no registered fetcher for {url!r}; registered: "
            + ", ".join(sorted(f.source_id for f in self._fetchers)))

    def fetch(self, url: str) -> FetchedSource:
        fetcher = self._pick(url)
        if self._throttle is not None and not self._throttle.try_acquire(fetcher.source_id):
            raise RateLimitedError(fetcher.source_id, 429, "throttle bucket exhausted")
        return fetcher.fetch(url)
