"""M2-008 fixture 生成器：证据六源首批样本（确定性，可复现——铁律 3）。

布局：fixtures/evidence6/{source}/{query-slug}.json + ratelimit.json + failure.json。
载荷保持各源原生形态（Crossref works / 专利检索 / 新闻 API / 产品目录 /
融资库 / 供应商 pricing HTML——含 contact-us 低置信形态，B5 语料）。
在线实录不可控（与 _generate_4src 同理），按真实响应形态确定性构造；
重录真实数据保持文件布局即可。运行：python -m fixtures._generate_evidence6。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flint.testing.replay import RecordedExchange, save_fixture

ROOT = Path(__file__).resolve().parent / "evidence6"
QUERIES = {
    "solid-state-battery": "solid state battery",
    "agent-memory": "agent memory",
    "low-altitude-economy": "low altitude economy",
}

URLS = {
    "paper": "https://api.crossref.org/works?query={q}&rows=10",
    "patent": "https://api.patents.example/v1/search?q={q}&rows=10",
    "news": "https://api.news.example/v2/everything?q={q}&pageSize=10",
    "competitor": "https://api.products.example/search?q={q}&limit=10",
    "funding": "https://api.funding.example/orgs?q={q}",
    "pricing": "https://www.vendor-{slug}.example/pricing",
}
CTYPES = {
    "paper": "application/json",
    "patent": "application/json",
    "news": "application/json",
    "competitor": "application/json",
    "funding": "application/json",
    "pricing": "text/html; charset=utf-8",
}


def paper_body(slug: str, q: str) -> str:
    idx = sum(ord(c) for c in slug)
    items = [
        {
            "DOI": f"10.5555/{slug}.{i}",
            "title": [f"{q} study {i}"],
            "container-title": ["Journal of Applied Energy" if i % 2 else "NeurIPS"],
            "is-referenced-by-count": (idx * 7 + i * 31) % 400,
            "published": {"date-parts": [[2026, (i % 12) + 1, 10]]},
            "URL": f"https://doi.org/10.5555/{slug}.{i}",
            "type": "journal-article",
        }
        for i in range(6)
    ]
    return json.dumps({"message": {"total-results": 6, "items": items}})


def patent_body(slug: str, q: str) -> str:
    idx = sum(ord(c) for c in slug)
    patents = [
        {
            "patent_id": f"US{11000000 + idx + i}",
            "title": f"{q} apparatus {i}",
            "family_size": 1 + (idx + i) % 8,
            "legal_status": "active" if i % 3 else "pending",
            "date": f"2026-0{(i % 6) + 1}-15",
            "url": f"https://patents.example/US{11000000 + idx + i}",
        }
        for i in range(5)
    ]
    return json.dumps({"patents": patents, "count": len(patents)})


def news_body(slug: str, q: str) -> str:
    idx = sum(ord(c) for c in slug)
    articles = [
        {
            "title": f"{q} market update {i}",
            "url": f"https://news.example/{slug}/{i}",
            "source": {"name": "Reuters" if i % 2 else "TechBlog Weekly"},
            "media_tier": 1 if i % 2 else 3,
            "independent_sources": 1 + (idx + i) % 4,
            "publishedAt": f"2026-07-{10 + i:02d}T08:00:00Z",
        }
        for i in range(5)
    ]
    return json.dumps({"status": "ok", "articles": articles})


def competitor_body(slug: str, q: str) -> str:
    results = [
        {
            "name": f"{q.title()} Vendor {i}",
            "url": f"https://vendor{i}-{slug}.example",
            "description": f"Commercial platform for {q}",
            "last_activity": f"2026-0{(i % 6) + 1}-01",
        }
        for i in range(4)
    ]
    return json.dumps({"results": results, "total": len(results)})


def funding_body(slug: str, q: str) -> str:
    orgs = [
        {
            "name": f"{q.title()} Labs {i}",
            "last_round": "Series B" if i % 2 else "Seed",
            "raised_usd": 5_000_000 * (i + 1),
            "url": f"https://funding.example/{slug}/{i}",
        }
        for i in range(3)
    ]
    return json.dumps({"organizations": orgs})


def pricing_body(slug: str, q: str) -> str:
    if slug == "agent-memory":  # contact-us 低置信形态（B5 常态语料）
        return (
            "<html><body><h1>Pricing</h1>"
            "<div class='plan'><h2>Enterprise plan</h2>"
            "<p>Contact us for a quote tailored to your team.</p>"
            "<a href='/sales'>Contact sales</a></div>"
            f"<!-- {q} --></body></html>"
        )
    return (
        "<html><body><h1>Pricing</h1>"
        "<div class='plan'><h2>Starter plan</h2><p>$29 per month</p></div>"
        "<div class='plan'><h2>Pro plan</h2><p>$99 per month</p></div>"
        "<div class='plan'><h2>Enterprise plan</h2><p>Contact us</p></div>"
        f"<!-- {q} --></body></html>"
    )


BODIES = {
    "paper": paper_body,
    "patent": patent_body,
    "news": news_body,
    "competitor": competitor_body,
    "funding": funding_body,
    "pricing": pricing_body,
}


def negative_bodies(slug: str, q: str) -> dict[tuple[str, str], tuple[str, str, str]]:
    """证伪素材（M2-016）：撤稿 / archived / 关停三类，各挂原生形态。"""
    retraction = json.dumps({
        "retractions": [
            {
                "title": f"RETRACTED: {q} breakthrough claims",
                "original_doi": f"10.5555/{slug}.retracted.1",
                "url": f"https://retractions.example/{slug}/1",
                "date": "2026-05-20",
                "reason": "data fabrication",
            }
        ]
    })
    archived = json.dumps({
        "results": [
            {
                "name": f"{q.title()} OpenProject",
                "url": f"https://github.com/legacy/{slug}",
                "archived": True,
                "last_activity": "2023-11-02",
                "description": f"Abandoned open implementation of {q}",
            }
        ]
    })
    shutdown = json.dumps({
        "status": "ok",
        "articles": [
            {
                "title": f"{q.title()} startup shuts down after funding dries up",
                "url": f"https://news.example/{slug}/shutdown",
                "source": {"name": "Reuters"},
                "media_tier": 1,
                "independent_sources": 3,
                "publishedAt": "2026-06-30T08:00:00Z",
            }
        ]
    })
    qp = q.replace(" ", "+")
    return {
        ("paper", f"retraction-{slug}"): (
            f"https://api.retractions.example/search?q={qp}", "application/json", retraction),
        ("competitor", f"archived-{slug}"): (
            f"https://api.products.example/search?q={qp}&status=archived",
            "application/json", archived),
        ("news", f"shutdown-{slug}"): (
            f"https://api.news.example/v2/everything?q={qp}+shutdown&pageSize=5",
            "application/json", shutdown),
    }


def main() -> None:
    for slug, q in QUERIES.items():
        for (source, name), (url, ctype, body) in negative_bodies(slug, q).items():
            save_fixture(
                ROOT / source / f"{name}.json",
                [RecordedExchange("GET", url, 200, ctype, body)],
            )
    for source, url_tpl in URLS.items():
        for slug, q in QUERIES.items():
            url = url_tpl.format(q=q.replace(" ", "+"), slug=slug)
            save_fixture(
                ROOT / source / f"{slug}.json",
                [RecordedExchange("GET", url, 200, CTYPES[source], BODIES[source](slug, q))],
            )
        probe = url_tpl.format(q="probe", slug="probe")
        save_fixture(
            ROOT / source / "ratelimit.json",
            [RecordedExchange("GET", probe, 429, "text/plain", "rate limited: retry later")],
        )
        save_fixture(
            ROOT / source / "failure.json",
            [RecordedExchange("GET", probe, 503, "text/plain", "upstream unavailable")],
        )
    print("evidence6 fixtures written:", ", ".join(URLS))


if __name__ == "__main__":
    main()
