"""TS-014：云端档（DeepSeek/GPT）授权跑的离线回放 + 四家并排诚实断言。

owner @2026-07-31 授权各一轮小额付费。DeepSeek 已跑；GPT 待 owner 补
FLINT_OPENAI_USD_PER_MTOK_OUTPUT（未录则 skip，NEVER 造）。四家（qwen/claude/
deepseek/gpt）并排断言诚实差距：接地取证与否、speculative 比例。
"""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from flint.testing.replay import ReplayMiss, load_fixture
from harness.topic_caliber import (
    ASSET_ROOT,
    _OrderedReplayTransport,
    fixture_file,
    replay_run,
)

pytestmark = pytest.mark.compose

CLOUD_MODELS = ["deepseek-chat", "gpt-4o-mini"]


def _asset_path(model: str) -> Any:
    return ASSET_ROOT / f"{model.replace(':', '_')}.json"


def _asset(model: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_asset_path(model).read_text(encoding="utf-8"))
    return data


def _require(model: str) -> None:
    if not _asset_path(model).exists():
        pytest.skip(f"{model} 未录制（env 待 owner 补齐；NEVER 造）")


@pytest.mark.parametrize("model", CLOUD_MODELS)
def test_cloud_asset_valid_and_honest(model: str) -> None:
    _require(model)
    a = _asset(model)
    assert a["model"] == model
    assert a["pipeline"] == "batch"
    assert 1 <= len(a["topics"]) <= 8
    assert float(a["delta"]) > 0.0
    assert float(a["cost_usd"]) >= 0.0                 # 实录付费成本
    for t in a["topics"]:
        assert t["one_liner"] and t["keyword_mapping"]
        assert (t["why_now_evidences"] == []) == bool(t["speculative"])


@pytest.mark.parametrize("model", CLOUD_MODELS)
def test_cloud_fixture_offline_source(model: str) -> None:
    _require(model)
    exchanges = load_fixture(fixture_file(model))
    assert len(exchanges) >= 5
    for ex in exchanges:
        assert ex.method == "POST" and ex.status_code == 200
        json.loads(ex.body_text)


@pytest.mark.parametrize("model", CLOUD_MODELS)
def test_cloud_ordered_replay_reproduces_offline(model: str) -> None:
    _require(model)
    replayed = replay_run(model)
    asset = _asset(model)
    assert [t["one_liner"] for t in replayed["topics"]] == \
        [t["one_liner"] for t in asset["topics"]]
    assert [t["speculative"] for t in replayed["topics"]] == \
        [t["speculative"] for t in asset["topics"]]


@pytest.mark.parametrize("model", CLOUD_MODELS)
def test_cloud_replay_never_hits_network(model: str) -> None:
    _require(model)
    exchanges = load_fixture(fixture_file(model))
    client = httpx.Client(transport=_OrderedReplayTransport(exchanges))
    for _ in range(len(exchanges)):
        client.post("http://x/v1/chat/completions", json={})
    with pytest.raises(ReplayMiss):
        client.post("http://x/v1/chat/completions", json={})


def test_four_way_grounding_side_by_side() -> None:
    # 并排（qwen/claude/deepseek/gpt）诚实断言：①speculative 比例 ②白名单取证
    qwen = _asset("qwen3.6:27b")
    claude = _asset("claude-sonnet-5")
    # qwen 不引白名单 → 全 speculative
    assert sum(bool(t["speculative"]) for t in qwen["topics"]) == len(qwen["topics"])
    # claude 从白名单取证 → 0 speculative
    assert sum(bool(t["speculative"]) for t in claude["topics"]) == 0
    # 云端各家（已录的）：接地取证则 citation_id ∈ card_ids（非 speculative 主题）
    for model in CLOUD_MODELS:
        if not _asset_path(model).exists():
            continue
        a = _asset(model)
        allowed = set(a["card_ids"])
        for t in a["topics"]:
            if not t["speculative"]:
                assert t["why_now_evidences"]
                for e in t["why_now_evidences"]:
                    assert e["citation_id"] in allowed   # 真从白名单取 citation
