"""Feature B-6：Gate① 真实 Searcher（Path A）——github/arxiv 搜索 → Doc。

复用 fetcher 地基与 R1 源（github/arxiv 官方搜索 API）实现 gate1 的
`Searcher = Callable[[Query], list[Doc]]`，可注入 `Gate1Deps.searcher` 替换 `_offline_searcher`
（占位 .example）。本卡只建**可注入的真实 searcher + 离线回放测试**；是否把生产 Gate① 默认切到
真实源（涉真实抓取 + weibo/news 缓办覆盖面）= owner 决策，NEVER 在此改 gate1 默认。

门 1=C：Searcher 只回 Doc 元信息（title/url/date），quote_span 归 B-3（Gate① 对齐另取）。
抓取走 M1-008 录制回放（S2-7 CI 零联网）；限流复用 sources/throttle。
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast
from urllib.parse import quote_plus

import httpx

from flint.domain.models import Doc, Query
from flint.evidence.common import base_meta, doc_id_for
from flint.evidence.docfetch import _parse_date
from flint.sources.errors import ParseDrift, RateLimitedError, SourceFetchError

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def github_search_url(text: str, per_page: int) -> str:
    return (f"https://api.github.com/search/repositories?q={quote_plus(text)}"
            f"&per_page={per_page}")


def arxiv_search_url(text: str, max_results: int) -> str:
    return (f"https://export.arxiv.org/api/query?search_query=all:{quote_plus(text)}"
            f"&max_results={max_results}")


class GithubArxivSearcher:
    """gate1 Searcher：对 query.text 搜 github+arxiv，合并回真实 Doc（元信息）。"""

    def __init__(
        self, client: httpx.Client, now: datetime, per_source: int = 3,
        resilient: bool = False,
        auth_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = client
        self._now = now
        self._n = per_source
        # resilient=True：单源限流/失败（403/429/5xx）跳过该源、继续另一源（M1-015 单源降级），
        # 生产 Gate① 不因一源限流整跑失败。默认 False（严格，测试用）。
        self._resilient = resilient
        # ── 认证接缝（`GATE1-DEDUP` / owner 2026-08-11：**本版不配 token**）──
        #
        # 今天注进来的是**空**：所有请求都走免登录路。
        # 实测（`DEC-057` 那一跑的真响应头）：GitHub 免登录搜索
        # `x-ratelimit-limit: 10`（每分钟），那一跑用掉 4。
        #
        # **配 token 时从这里进**，NEVER 在本文件里读 env：
        # 模块层读环境变量的话，「这次跑带没带凭据」就不是调用方能决定的事，
        # 而 CI 与本机会因为一个忘了清的变量跑出两种行为
        # （`DEC-052` / `DEC-057` 反复钉的同一条：授权 NEVER 从环境变量来）。
        #
        # **什么时候回来找 owner**（重启条件，owner 逐字）：
        #   · 出现第二个并发用户；**或**
        #   · 一次分析的 github 请求数达到两位数。
        # 到那时回来要凭据裁决，**NEVER 自行开通**——token 免费但它是凭据，
        # 存放/轮换/泄漏面都要新建。
        self._auth_headers: Mapping[str, str] = auth_headers or {}

    def _github(self, text: str) -> list[Doc]:
        resp = self._client.get(
            github_search_url(text, self._n),
            headers={"Accept": "application/vnd.github+json",
                     **self._auth_headers})
        if resp.status_code == 429:
            raise RateLimitedError("github", 429, resp.text)
        if resp.status_code != 200:
            raise SourceFetchError("github", resp.status_code, resp.text)
        try:
            items = json.loads(resp.text)["items"]
        except (json.JSONDecodeError, KeyError, TypeError) as err:
            raise ParseDrift("github", f"search schema mismatch: {err}") from err
        docs: list[Doc] = []
        for it in items[: self._n]:
            docs.append(Doc(
                doc_id=doc_id_for(str(it["html_url"])), source_id="github", kind="repo",
                title=str(it["full_name"]), url=str(it["html_url"]),
                published_at=_parse_date(str(it.get("pushed_at") or "")),
                meta=base_meta(self._now), origin="retrieved", access="public"))
        return docs

    def _arxiv(self, text: str) -> list[Doc]:
        resp = self._client.get(arxiv_search_url(text, self._n))
        if resp.status_code == 429:
            raise RateLimitedError("arxiv", 429, resp.text)
        if resp.status_code != 200:
            raise SourceFetchError("arxiv", resp.status_code, resp.text)
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as err:
            raise ParseDrift("arxiv", f"invalid Atom XML: {err}") from err
        docs: list[Doc] = []
        for entry in root.findall(f"{_ATOM_NS}entry")[: self._n]:
            title_node = entry.find(f"{_ATOM_NS}title")
            id_node = entry.find(f"{_ATOM_NS}id")
            pub_node = entry.find(f"{_ATOM_NS}published")
            if title_node is None or id_node is None or not title_node.text or not id_node.text:
                raise ParseDrift("arxiv", "entry without title or id")
            docs.append(Doc(
                doc_id=doc_id_for(id_node.text.strip()), source_id="arxiv", kind="paper",
                title=" ".join(title_node.text.split()), url=id_node.text.strip(),
                published_at=None if pub_node is None or not pub_node.text
                else _parse_date(pub_node.text),
                meta=base_meta(self._now), origin="retrieved", access="public"))
        return docs

    def _try(self, fn: Any, text: str) -> list[Doc]:
        if not self._resilient:
            return cast("list[Doc]", fn(text))
        try:
            return cast("list[Doc]", fn(text))
        except SourceFetchError:
            return []                       # 单源限流/失败 → 跳过该源（M1-015 降级）

    def __call__(self, query: Query) -> list[Doc]:
        # 按 query.source_kinds 分派——只搜对口源（github=repo/product，arxiv=paper）：
        # 更贴 intent，且省调用守住公网 API 限流（门 2=R1）。
        docs: list[Doc] = []
        kinds = set(query.source_kinds)
        if kinds & {"repo", "product"}:
            docs += self._try(self._github, query.text)
        if "paper" in kinds:
            docs += self._try(self._arxiv, query.text)
        return docs
