"""本地天花板实测（Phase 1）的离线回放 + 头号指标（dirty 率）断言。

owner @2026-07-31 授权免费本地跑：五家统一 @2 强接地 + Phase 0 校验器。本测试离线回放
录制资产（零联网），并断言核心结论：**免费本地在 @2+校验器下 dirty=0**；A/B（qwen3.6:27b
同 batch、只差 prompt）证明 @2 把「全留白」翻成「干净接地」。Scout/120b 录制后自动纳入。
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from flint.grounding import grade_asset, load_card_corpus
from flint.testing.replay import ReplayMiss, load_fixture
from harness.topic_caliber import (
    ASSET_ROOT,
    _OrderedReplayTransport,
    fixture_file,
    replay_run,
)

pytestmark = pytest.mark.compose

CORPUS = ASSET_ROOT / "card_corpus.json"
# 已录本地 @2 资产（label = {model}#v2）——Scout/120b 录后加进来即纳入断言。
LOCAL_V2 = ["gpt-oss:20b#v2", "deepseek-r1:32b#v2", "qwen3.6:35b-a3b#v2",
            "llama4:scout#v2", "gpt-oss:120b#v2"]


def _asset(label: str) -> dict[str, Any]:
    return json.loads((ASSET_ROOT / f"{label.replace(':', '_')}.json").read_text("utf-8"))


def _exists(label: str) -> bool:
    return (ASSET_ROOT / f"{label.replace(':', '_')}.json").exists()


@pytest.mark.parametrize("label", LOCAL_V2)
def test_local_asset_valid_and_v2(label: str) -> None:
    if not _exists(label):
        pytest.skip(f"{label} 未录制")
    a = _asset(label)
    assert a["pipeline"] == "batch"
    assert a["prompt_name"] == "topic_gen@2"
    assert float(a["cost_usd"]) == 0.0            # 本地免费档：实值 0
    for t in a["topics"]:
        assert (t["why_now_evidences"] == []) == bool(t["speculative"])


@pytest.mark.parametrize("label", LOCAL_V2)
def test_local_ordered_replay_reproduces_offline(label: str) -> None:
    if not _exists(label):
        pytest.skip(f"{label} 未录制")
    replayed = replay_run(label)
    asset = _asset(label)
    assert [t["one_liner"] for t in replayed["topics"]] == \
        [t["one_liner"] for t in asset["topics"]]
    assert [t["speculative"] for t in replayed["topics"]] == \
        [t["speculative"] for t in asset["topics"]]


@pytest.mark.parametrize("label", LOCAL_V2)
def test_local_replay_never_hits_network(label: str) -> None:
    if not _exists(label):
        pytest.skip(f"{label} 未录制")
    exchanges = load_fixture(fixture_file(label))
    client = httpx.Client(transport=_OrderedReplayTransport(exchanges))
    for _ in range(len(exchanges)):
        client.post("http://x/v1/chat/completions", json={})
    with pytest.raises(ReplayMiss):
        client.post("http://x/v1/chat/completions", json={})


@pytest.mark.parametrize("label", LOCAL_V2)
def test_headline_free_local_stays_dirty_zero(label: str) -> None:
    # owner 头号指标：@2 下免费本地 dirty=0（诚实、不造假）。
    if not _exists(label):
        pytest.skip(f"{label} 未录制")
    cards = load_card_corpus(CORPUS)
    graded = grade_asset(_asset(label), cards)
    assert graded["dirty"] == 0, f"{label} 应 dirty=0，实得 {graded['dirty']}"


def test_ab_prompt_flips_abstention_to_clean_grounding() -> None:
    # A/B：qwen3.6:27b 同 batch、只差 prompt。@1 全留白（unverifiable）→ @2 全干净（clean, dirty=0）。
    if not (_exists("qwen3.6:27b#v1b") and _exists("qwen3.6:27b#v2")):
        pytest.skip("A/B 资产未录齐")
    cards = load_card_corpus(CORPUS)
    base = grade_asset(_asset("qwen3.6:27b#v1b"), cards)
    treat = grade_asset(_asset("qwen3.6:27b#v2"), cards)
    assert base["unverifiable_topics"] == len(base["topics"])   # @1：全留白
    assert base["clean_topics"] == 0
    assert treat["dirty"] == 0                                   # @2：零编造
    assert treat["clean_topics"] >= 1                            # @2：出现干净接地
    assert treat["clean_topics"] > base["clean_topics"]         # prompt 单独把留白翻成接地
