"""Feature B payoff：总开关铁证（离线回放，S2-7 零联网）。

demo combo 两卡指向真实 github/arxiv；qwen3.6:35b-a3b @3 前后跑（thin vs rich）录制回放。
断言：① 前后均 dirty=0（enrichment 不引入编造）；② 富化后主题**引真源身份**（arxiv 卡命名真论文
"Attention Is All You Need"，thin 不命名）——卡变厚→主题引真证据的铁证。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flint.grounding import grade_asset
from harness.featb_payoff import (
    _enriched,
    _replay,
    _thin_context,
    _thin_corpus,
)

pytestmark = pytest.mark.compose

ASSET = Path(__file__).resolve().parents[2] / "assets" / "featb_payoff"


def _asset(tag: str) -> dict:
    return json.loads((ASSET / f"{tag}.json").read_text("utf-8"))


def _names_real_paper(ev: dict) -> bool:
    e = ev["event"]
    return "Attention Is All You Need" in e or "序列转导" in e or "编码器-解码器" in e


def test_thin_and_rich_both_dirty_zero() -> None:
    thin = grade_asset(_asset("thin"), _thin_corpus())
    _, rich_corpus = _enriched()
    rich = grade_asset(_asset("rich"), rich_corpus)
    assert thin["dirty"] == 0 and rich["dirty"] == 0     # enrichment 不引入编造


def test_enrichment_makes_topics_cite_real_source() -> None:
    # 铁证（arxiv 卡，无 few-shot 污染）：thin 从不命名真论文 → rich 每条都命名 + 引真论点
    thin = _asset("thin")
    rich = _asset("rich")
    thin_ax = [e for t in thin["topics"] for e in t["why_now_evidences"]
               if "arxiv" in e["citation_id"]]
    rich_ax = [e for t in rich["topics"] for e in t["why_now_evidences"]
               if "arxiv" in e["citation_id"]]
    assert thin_ax and rich_ax
    assert sum(_names_real_paper(e) for e in thin_ax) == 0        # thin：泛写、不引真源
    assert all(_names_real_paper(e) for e in rich_ax)             # rich：全引真论文


def test_rich_replay_reproduces_offline() -> None:
    rich_ctx, _ = _enriched()
    replayed = _replay("rich", rich_ctx)
    asset = _asset("rich")
    assert [t["one_liner"] for t in replayed["topics"]] == \
        [t["one_liner"] for t in asset["topics"]]


def test_thin_replay_reproduces_offline() -> None:
    replayed = _replay("thin", _thin_context())
    asset = _asset("thin")
    assert [t["one_liner"] for t in replayed["topics"]] == \
        [t["one_liner"] for t in asset["topics"]]
