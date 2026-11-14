"""CN-05：ghtrend / arxiv 的真实契约验证。

## 「没验证过」与「验证过没问题」在盘上长得一样

四个适配器全部按合成夹具建（`_generate_4src.py` 自述无法在线录制）。
`CN-04` 修的是**已知坏**的两源；这两源**没被证明是好的**——本卡把这两件事分开。

## 结论（`DEC-052` 窗口内探测，ghtrend 2/10 · arxiv 5/10，全部留痕）

| 源 | 端点 | 实测 |
|---|---|---|
| ghtrend | `api.github.com/search/repositories?q=created:>…` | **200 · 15 repos**，解析出 136 条 |
| arxiv | `export.arxiv.org/api/query?search_query=cat:cs.AI+AND+submittedDate:[…]` | **200**，契约成立 |

**两源契约都没漂**。而 arxiv 那一发逼出了一件真事，见下。

## arxiv：「那天没有」与「查询坏了」此前分不开

查昨天（2026-08-09，**周日**）回 `totalResults: 0`、一条 entry 都没有，
而适配器**安安静静地回 `[]`**。当时唯一能分辨的办法是人工再打两发：

- 不带日期过滤 → `totalResults: 193472`（端点活着）；
- 查一周前那一天 → `totalResults: 120`（**日期范围写法是对的**）。

也就是说：**是 arXiv 周末不发布**，不是我们写坏了。
但盘上那一刻的两种情形长得一模一样——本卡把 `opensearch:totalResults`
接进解析：它在且为 0 = 查过了、那天确实没有；**它整个不在 = 上游换了结构**。

判据全部离线回放**真响应**（`fixtures/_probe/{source}/*.body`）；
`ParseDrift` 的阴性对照拿真响应改坏一处构造，NEVER 手编一个想象中的坏响应。
"""
from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from flint.sources.arxiv import ArxivSource, parse_atom
from flint.sources.errors import ParseDrift
from flint.sources.ghtrend import GitHubTrendingSource

REPO = Path(__file__).resolve().parents[2]
PROBE = REPO / "fixtures" / "_probe"
ROBOTS = REPO / "fixtures" / "robots"
NOW = datetime(2026, 8, 10, tzinfo=UTC)
DAY = date(2026, 8, 2)


def _bodies(source: str, needle: str) -> list[str]:
    out = []
    for path in sorted((PROBE / source).glob("*.body")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if needle in text:
            out.append(text)
    return out


def _receipts(source: str) -> list[dict[str, object]]:
    loaded = [json.loads(p.read_text(encoding="utf-8"))
              for p in (PROBE / source).glob("*.json")]
    return [r for r in loaded
            if isinstance(r, dict) and r.get("schema") == "probe/1"]


def _offline(body: str, ctype: str) -> httpx.Client:
    """离线客户端：**一个真实请求都不发**（`S2-7`：CI 恒不联网）。"""
    return httpx.Client(transport=httpx.MockTransport(
        lambda _req: httpx.Response(200, text=body,
                                    headers={"content-type": ctype})))


# ───────────────────────── 一、两源都真的被探过（留痕在盘上）


@pytest.mark.parametrize("source", ["ghtrend", "arxiv"])
def test_the_source_was_really_probed(source: str) -> None:
    """**「没验证过」与「验证过没问题」分开**：这一条要的是那次往返的证据。"""
    receipts = _receipts(source)
    ok = [r for r in receipts if r["status"] == 200]

    assert ok, f"{source} 没有一次成功往返的留痕"
    assert all(r["authorized_by"] == "DEC-052" for r in receipts)


@pytest.mark.parametrize("source", ["ghtrend", "arxiv"])
def test_a_robots_snapshot_was_taken(source: str) -> None:
    """`K2-01` RECORD_ONLY：照实记录、不阻断、NEVER 重判。"""
    snaps = list(ROBOTS.glob(f"{source}-*.txt"))

    assert snaps, f"{source} 没有 robots 快照"
    assert snaps[0].stat().st_size > 100


# ───────────────────────── 二、ghtrend：真响应解析得动


def test_ghtrend_parses_the_real_search_response() -> None:
    """真 JSON → 真关键词。**NEVER 只断言「没抛异常」**。

    `CN-07` 回填：这条判据此前拿到的是一份 **0 条目**的响应
    （旧窗口 `created:>今天` 结构上恒空），于是它证明的只是「解析器不崩」。
    换成窗口修好之后录的那一份——**真的有条目**，断言也才有意义。
    """
    body = (PROBE / "ghtrend" / "real-search.json").read_text(encoding="utf-8")

    items = GitHubTrendingSource(
        client=_offline(body, "application/json"), now=lambda: NOW,
    ).fetch_daily(DAY)

    assert len(items) >= 20, f"只解析出 {len(items)} 条"
    assert all(i.keyword.strip() for i in items)
    assert all(i.url.startswith("http") for i in items)


# ───────────────────────── 三、arxiv：契约成立，且两种「空」分得开


def test_arxiv_parses_a_populated_real_feed() -> None:
    """有内容那一份：entry 全部解析出来。

    `CN-07` 回填：换成窗口修好之后录的那一份（近 7 天、截到昨天）。
    """
    body = (PROBE / "arxiv" / "real-feed.xml").read_text(encoding="utf-8")

    items = parse_atom(body, categories=None, now=NOW)

    assert len(items) >= 10, f"只解析出 {len(items)} 条"
    assert all(i.keyword.strip() for i in items)


def test_an_empty_day_is_read_as_empty_not_as_drift() -> None:
    """**那天确实没有**：`totalResults: 0` → 回空列表，NEVER 抛。

    2026-08-09 是周日，arXiv 不发布。查询写法是对的
    （同一写法查一周前那天回 120 条），所以这一档必须是「查过了、是空的」。
    """
    empty = [b for b in _bodies("arxiv", "totalResults") if "<entry>" not in b]
    assert empty, "盘上没有那份空的真响应"

    assert parse_atom(empty[0], categories=None, now=NOW) == []


def test_a_feed_without_total_results_is_drift() -> None:
    """**它整个不在 = 上游换了结构**——那时回 `[]` 才是撒谎。

    这一条是本卡的产品：改前 feed 里没有 entry 时解析安静地回 `[]`，
    而「那天没有」「查询写坏了」「上游改了结构」三种情形**在盘上长得一模一样**。
    """
    body = _bodies("arxiv", "totalResults")[0]
    broken = re.sub(r"<opensearch:totalResults[^<]*</opensearch:totalResults>",
                    "", body)
    assert broken != body, "这条对照的前提没了"

    with pytest.raises(ParseDrift, match="totalResults"):
        parse_atom(broken, categories=None, now=NOW)


@pytest.mark.parametrize("label,break_it", [
    ("根元素不是 feed", lambda b: b.replace("<feed", "<notafeed", 1)
                                  .replace("</feed>", "</notafeed>")),
    ("整个不是 XML", lambda b: "<!doctype html><title>502</title>"),
])
def test_a_real_feed_broken_in_one_place_raises_drift(
    label: str, break_it: object,
) -> None:
    """阴性对照**拿真响应改坏一处**构造。

    手编一个想象中的坏响应，只证明「解析器认得我编的东西」；
    改坏真响应证明的是「上游真变了的时候它会喊」。
    """
    body = _bodies("arxiv", "totalResults")[0]

    with pytest.raises(ParseDrift):
        parse_atom(break_it(body), categories=None, now=NOW)  # type: ignore[operator]


def test_the_module_records_why_total_results_is_read() -> None:
    """理由写在源码里——不写的话，下一个人会把这条判断当成多余的。"""
    text = (REPO / "flint" / "sources" / "arxiv.py").read_text(encoding="utf-8")

    assert "totalResults" in text
    assert "周末不发布" in text or "周日" in text
    assert "CN-05" in text


def test_the_adapter_still_asks_the_endpoint_that_answered() -> None:
    """取数路仍是那条被验过的端点，**NEVER 顺手换一条没验过的**。"""
    url = ArxivSource(client=_offline("<feed/>", "application/atom+xml"))._url(DAY)

    assert url.startswith("https://export.arxiv.org/api/query?")
    assert "submittedDate:" in url
