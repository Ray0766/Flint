"""Feature B payoff：总开关成不成的铁证（owner @2026-07-31）。

一个 demo combo 的两张卡指向**真实 github/arxiv**（R1 授权公网免费）：
- BEFORE（瘦卡）：cards_context 只有关键词+日期 → qwen3.6:35b-a3b @2 生成 → 校验器。
- 富化：抓真实源 → 抽短 quote_span → Doc+Citation（B-1~B-4）。
- AFTER（厚卡）：cards_context 带真 title+quote_span（B-5）→ 同模型同 @2 生成 → 校验器（富语料）。
报前后对比：主题从"瘦/含糊"→"实/带真 quote_span 引证"，且**仍 dirty=0**（有真证据、不造假）。

抓取走 M1-008 录制回放（fixtures/evidence/*，S2-7 CI 零联网）；qwen 跑亦录制回放。
门 1=C：只经短 quote_span，NEVER 全文。免费本地 + 免费公网 API，零花费。
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from flint.domain.models import TopicSeed
from flint.evidence.docfetch import ArxivFetcher, DocFetcherRegistry, GithubRepoFetcher
from flint.evidence.enrich import (
    card_evidence_to_enriched,
    enrich_card,
    enriched_cards_context,
    enriched_corpus,
)
from flint.grounding import CardContent, grade_asset
from flint.llm.local import LocalProvider
from flint.testing.replay import RecordedExchange, load_fixture, save_fixture
from harness.topic_caliber import (
    _OrderedReplayTransport,
    _RecordingTransport,
    _serialize,
    run_combo_batch,
)

REPO = Path(__file__).resolve().parents[1]
FX_EVID = REPO / "fixtures" / "evidence"
FX_PAYOFF = REPO / "fixtures" / "featb_payoff"
ASSET = REPO / "assets" / "featb_payoff"
NOW = datetime(2026, 7, 31, tzinfo=UTC)
CARD_DAY = date(2026, 6, 29)
MODEL = "qwen3.6:35b-a3b"
PROMPT = "topic_gen@3"  # 证据感知强接地：有证据段则 why_now.event 引其要点

# demo combo：两卡指向真实 github/arxiv（keyword 为该源的中文主题标签）
DEMO = [
    ("card-featb-flask", "Web 应用框架", "https://github.com/pallets/flask",
     "github_pallets_flask"),
    ("card-featb-arxiv", "Transformer 注意力机制", "https://arxiv.org/abs/1706.03762",
     "arxiv_1706.03762"),
]
CARD_IDS = [c[0] for c in DEMO]
HYPOTHESIS = "把 web 框架的工程易用性与注意力机制的建模能力迁移到同一可复用工作台"


def _seed() -> TopicSeed:
    return TopicSeed(
        seed_id="seed-featb", origin_id="origin-featb",
        keywords=[c[1] for c in DEMO], hypothesis=HYPOTHESIS,
        context_text=f"关联假设：{HYPOTHESIS}")


def _thin_context() -> str:
    return "\n".join(f'{cid} = 「{kw}」（日期 {CARD_DAY.isoformat()}）' for cid, kw, _, _ in DEMO)


def _thin_corpus() -> dict[str, CardContent]:
    return {cid: CardContent(card_id=cid, day=CARD_DAY, corpus=kw) for cid, kw, _, _ in DEMO}


def _evidence_client() -> httpx.Client:
    by_url: dict[str, RecordedExchange] = {}
    for _, _, _, key in DEMO:
        for ex in load_fixture(FX_EVID / key / "fetch.json"):
            by_url[ex.url] = ex

    def handler(request: httpx.Request) -> httpx.Response:
        ex = by_url[str(request.url)]
        return httpx.Response(ex.status_code, content=ex.body_text.encode("utf-8"),
                              headers={"content-type": ex.content_type})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _enriched() -> tuple[str, dict[str, CardContent]]:
    """抓真实源（回放录制）→ 富化卡 → (rich cards_context, rich corpus)。"""
    reg = DocFetcherRegistry()
    client = _evidence_client()
    reg.register(GithubRepoFetcher(client))
    reg.register(ArxivFetcher(client))
    enriched = []
    for cid, kw, url, _ in DEMO:
        ev = enrich_card(cid, [url], reg, NOW)
        enriched.append(card_evidence_to_enriched(cid, kw, CARD_DAY, ev.docs, ev.citations))
    return enriched_cards_context(enriched), enriched_corpus(enriched)


def _provider(client: httpx.Client) -> LocalProvider:
    return LocalProvider(base_url="http://localhost:11434/v1", model=MODEL,
                         http_client=client, disable_reasoning=True, max_tokens=4096)


def _run_and_record(tag: str, cards_context: str) -> dict[str, Any]:
    sink: list[RecordedExchange] = []
    client = httpx.Client(transport=_RecordingTransport(httpx.HTTPTransport(), sink),
                          timeout=600.0)
    result, misses = run_combo_batch(
        _provider(client), _seed(), CARD_IDS, MODEL,
        prompt_name=PROMPT, cards_context=cards_context)
    save_fixture(FX_PAYOFF / tag / "combo.json", sink)
    rec = _serialize(result, CARD_IDS, MODEL)
    rec["prompt_name"] = PROMPT
    rec["schema_misses"] = misses
    rec["variant"] = tag
    ASSET.mkdir(parents=True, exist_ok=True)
    (ASSET / f"{tag}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    return rec


def _replay(tag: str, cards_context: str) -> dict[str, Any]:
    exchanges = load_fixture(FX_PAYOFF / tag / "combo.json")
    client = httpx.Client(transport=_OrderedReplayTransport(exchanges))
    result, _misses = run_combo_batch(
        _provider(client), _seed(), CARD_IDS, MODEL,
        prompt_name=PROMPT, cards_context=cards_context)
    return _serialize(result, CARD_IDS, MODEL)


def _grade(rec: dict[str, Any], corpus: dict[str, CardContent]) -> dict[str, Any]:
    return grade_asset(rec, corpus)


def record() -> None:
    rich_ctx, rich_corpus = _enriched()
    thin = _run_and_record("thin", _thin_context())
    rich = _run_and_record("rich", rich_ctx)
    gt = _grade(thin, _thin_corpus())
    gr = _grade(rich, rich_corpus)
    print(f"BEFORE(thin): dirty={gt['dirty']} clean={gt['clean']} unv={gt['unverifiable']} "
          f"topics clean/dirty/unv={gt['clean_topics']}/{gt['dirty_topics']}/{gt['unverifiable_topics']}")
    print(f"AFTER(rich):  dirty={gr['dirty']} clean={gr['clean']} unv={gr['unverifiable']} "
          f"topics clean/dirty/unv={gr['clean_topics']}/{gr['dirty_topics']}/{gr['unverifiable_topics']}")


if __name__ == "__main__":
    record()
