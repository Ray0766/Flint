"""统一判官横比（owner 任务）：固定 claude-sonnet-5 判官重判三家已存产出，
得可比作答率。只重判、不重写组稿。CI 零外部（本测只覆盖装载器 + 判官构造，
真实判分走运行环境）。
"""
from __future__ import annotations

import json
from pathlib import Path

from flint.llm.production import AnthropicTier, PaidTierProvider
from harness.rejudge import (
    SOURCE_TRAILS,
    build_judge,
    load_compositions_from_trail,
)

_TIER = AnthropicTier(
    api_key="sk-test", model="claude-sonnet-5",
    usd_per_mtok_input=2.0, usd_per_mtok_output=10.0,
)


def test_load_compositions_from_trail(tmp_path: Path) -> None:
    trail = {"compositions": {
        "golddoc-generic-plain": {
            "template_id": "generic",
            "sections": {"summary": "文本A", "market": "文本B"},
        },
        "golddoc-thesis-plain": {
            "template_id": "thesis", "sections": {"summary": "文本C"},
        },
    }}
    p = tmp_path / "t.json"
    p.write_text(json.dumps(trail, ensure_ascii=False), encoding="utf-8")
    comps = load_compositions_from_trail(p)
    assert len(comps) == 2
    by = {c.composition_id: c for c in comps}
    assert by["golddoc-generic-plain"].template_id == "generic"
    assert by["golddoc-generic-plain"].sections["summary"] == "文本A"
    assert by["golddoc-generic-plain"].sections["market"] == "文本B"
    assert by["golddoc-thesis-plain"].sections["summary"] == "文本C"


def test_build_judge_is_claude_thinking_off() -> None:
    # 判官恒定 claude-sonnet-5；判分走 output_config.format、thinking 关
    # （结构化 JSON 干净、无思考成本）。
    judge = build_judge(_TIER)
    assert isinstance(judge, PaidTierProvider)
    assert judge.model == "claude-sonnet-5"
    assert judge._disable_thinking is True


def test_source_trails_are_the_three_families() -> None:
    # 被判三家：gemma4:31b / qwen3.6:27b / claude-sonnet-5（repair-on 那版）
    assert set(SOURCE_TRAILS) == {"gemma4:31b", "qwen3.6:27b", "claude-sonnet-5"}
    for tf in SOURCE_TRAILS.values():
        assert tf.endswith(".json")
