"""TS-011：授权模型跑的离线回放（CI 零联网，录制 fixture 是运行出处）。

两次授权跑（owner @2026-07-31）：qwen3.6:27b（免费本地）+ claude-sonnet-5（付费一轮）。
HTTP 交换录 fixture + 产出录 asset。本测按录制顺序回放 → 忠实复现，NEVER 联网。
并排断言两侧诚实差距（qwen 全 speculative vs claude 接地取证）。
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

MODELS = ["qwen3.6:27b", "claude-sonnet-5"]


def _asset(model: str) -> dict[str, Any]:
    path = ASSET_ROOT / f"{model.replace(':', '_')}.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("model", MODELS)
def test_recorded_asset_is_valid_and_honest(model: str) -> None:
    a = _asset(model)
    assert a["model"] == model
    topics = a["topics"]
    assert isinstance(topics, list)
    assert 1 <= len(topics) <= 8                       # combo ≤8（诚实降级可 <5）
    assert int(a["generations"]) >= 1
    assert float(a["delta"]) > 0.0                     # δ 真跑估计（非 report_only）
    assert isinstance(a["degraded"], bool)
    for t in topics:
        assert t["one_liner"] and t["target_user_tag"] and t["form_factor_tag"]
        assert isinstance(t["keyword_mapping"], dict) and t["keyword_mapping"]
        # 接地铁律：evidences 空 ⇔ speculative（系统据实判、非 LLM 自报）
        assert (t["why_now_evidences"] == []) == bool(t["speculative"])


@pytest.mark.parametrize("model", MODELS)
def test_http_fixture_recorded_offline_source(model: str) -> None:
    fixture = fixture_file(model)
    assert fixture.exists(), f"{model} 录制 fixture 缺失——需先跑 harness record"
    exchanges = load_fixture(fixture)
    assert len(exchanges) >= 5
    for ex in exchanges:
        assert ex.method == "POST"
        assert ex.status_code == 200
        json.loads(ex.body_text)                        # 响应体是合法 JSON


@pytest.mark.parametrize("model", MODELS)
def test_ordered_replay_reproduces_run_offline(model: str) -> None:
    replayed = replay_run(model)
    asset = _asset(model)
    assert [t["one_liner"] for t in replayed["topics"]] == \
        [t["one_liner"] for t in asset["topics"]]
    assert replayed["degraded"] == asset["degraded"]
    assert [t["speculative"] for t in replayed["topics"]] == \
        [t["speculative"] for t in asset["topics"]]


@pytest.mark.parametrize("model", MODELS)
def test_replay_never_hits_network(model: str) -> None:
    exchanges = load_fixture(fixture_file(model))
    client = httpx.Client(transport=_OrderedReplayTransport(exchanges))
    for _ in range(len(exchanges)):
        client.post("http://x/v1/messages", json={})
    with pytest.raises(ReplayMiss):                     # 耗尽 → ReplayMiss，非真网络
        client.post("http://x/v1/messages", json={})


def test_grounding_gap_qwen_vs_claude() -> None:
    # owner 问 ①②：并排 speculative 比例 + 是否从白名单取证（诚实差距，非粉饰）
    qwen = _asset("qwen3.6:27b")
    claude = _asset("claude-sonnet-5")
    qwen_spec = sum(bool(t["speculative"]) for t in qwen["topics"])
    claude_spec = sum(bool(t["speculative"]) for t in claude["topics"])
    # qwen 未从白名单取证 → 全 speculative
    assert qwen_spec == len(qwen["topics"])
    # claude 从白名单取证（evidences 非空、citation_id ∈ card_ids）→ 非 speculative
    assert claude_spec == 0
    allowed = set(claude["card_ids"])
    for t in claude["topics"]:
        assert t["why_now_evidences"]
        for e in t["why_now_evidences"]:
            assert e["citation_id"] in allowed          # 真从白名单取证
