"""FE-CORE-003：生产 LLM 章节 BlockGenerator（qwen3.6/LocalProvider，替换桩）。

- generator 按 section_draft prompt + SectionSpec + usable_facts 调 LLM → 结构化输出
  → list[Block]，经 generator_factory 注入；产出过 draft_section_with_channels 门。
- 离线 fixture：LocalProvider 走 httpx.MockTransport（M1-008 机理），**块内容取自 M4 已
  录制的真实 qwen3.6 产出**（assets/prod_caliber/qwen3.6_27b.json）以贴合真实模型行为。
  CI 零联网零付费（S2-7）。
- _default_generator 桩保留（离线确定性测试用，NEVER 删）——本测断言其仍在。
- 账本外事实 → DraftViolation 拒稿（铁律护栏，FE-CORE-006 深化）。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from flint.compose.draft import DraftViolation
from flint.compose.draft_channels import draft_section_with_channels
from flint.compose.llm_generator import BLOCK_SCHEMA, llm_generator_factory
from flint.domain.models import (
    Fact,
    FactsLedger,
    Principal,
    SectionSpec,
    UserProfile,
)
from flint.llm.local import LocalProvider

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)


def _real_qwen_prose() -> str:
    """取一段 M4 已录制的真实 qwen3.6 摘要正文（贴合真实模型行为）。"""
    data = json.loads(
        (REPO / "assets" / "prod_caliber" / "qwen3.6_27b.json").read_text(encoding="utf-8")
    )
    comp = next(iter(data["compositions"].values()))
    return str(comp["sections"]["summary"])[:100]


def _profile() -> UserProfile:
    return UserProfile(
        profile_id="p-1", owner=Principal(kind="user", id="u-1"),
        identity={}, research={}, team=[], assets={}, constraints={},
        track_record=[], locale="zh-CN", sensitivity_overrides={}, updated_at=NOW,
    )


def _ledger(fact_ids: list[str]) -> FactsLedger:
    facts = [
        Fact(fact_id=fid, statement=f"陈述-{fid}", value=None, unit=None,
             citation_ids=[], status="frozen", origin="injected",
             created_in_version=1)
        for fid in fact_ids
    ]
    return FactsLedger(
        ledger_id="led-1", project_id="proj-1", version=1, parent_version=None,
        derivation_reason="freeze", facts=facts, created_from=[], created_at=NOW,
        actor="u-1",
    )


def _mock_provider(block_json: dict) -> LocalProvider:
    def respond(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(block_json, ensure_ascii=False),
                                     "tool_calls": []}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        })
    return LocalProvider(
        base_url="http://local/v1", model="qwen3.6:27b",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )


SPEC = SectionSpec(section_id="summary", inputs=[],
                   check_questions=["项目一句话是什么？"], charts=[])


def test_generator_produces_gate_passing_blocks_from_real_qwen_prose() -> None:
    prose = _real_qwen_prose()
    provider = _mock_provider({"blocks": [
        {"type": "heading", "level": 2, "text": "项目摘要"},
        {"type": "paragraph", "text": prose, "fact_ids": ["fact-1"]},
    ]})
    factory = llm_generator_factory(provider, "PROMPT")
    generator = factory(SPEC, "del-1")
    blocks = draft_section_with_channels(
        SPEC, _ledger(["fact-1"]), generator, entries_by_id={}, profile=_profile(),
    )
    assert [b.type for b in blocks] == ["heading", "paragraph"]
    assert blocks[0].content.kind == "heading"
    assert blocks[1].content.kind == "paragraph"
    assert blocks[1].content.spans[0].text == prose
    assert blocks[1].fact_ids == ["fact-1"]
    assert blocks[0].author == "system" and blocks[0].locked is False
    assert [b.order for b in blocks] == [0, 1]


def test_out_of_ledger_fact_is_rejected_by_channel_gate() -> None:
    """铁律护栏：生成器产出引用账本外 fact → DraftViolation 拒稿（不出厂）。"""
    provider = _mock_provider({"blocks": [
        {"type": "paragraph", "text": "宣称一个没有支撑的数字", "fact_ids": ["fact-99"]},
    ]})
    generator = llm_generator_factory(provider, "PROMPT")(SPEC, "del-1")
    with pytest.raises(DraftViolation):
        draft_section_with_channels(
            SPEC, _ledger(["fact-1"]), generator, entries_by_id={}, profile=_profile(),
        )


def test_gap_notice_when_no_supporting_fact() -> None:
    """指令/内容要证据外事实时，正路是 gap_notice 留白（不断言、不编造）。"""
    provider = _mock_provider({"blocks": [
        {"type": "gap_notice", "hints_ref": "缺市场规模权威来源"},
    ]})
    generator = llm_generator_factory(provider, "PROMPT")(SPEC, "del-1")
    blocks = draft_section_with_channels(
        SPEC, _ledger([]), generator, entries_by_id={}, profile=_profile(),
    )
    assert blocks[0].content.kind == "gap_notice"


def test_default_generator_stub_kept() -> None:
    """桩保留（离线确定性测试用，NEVER 删）。"""
    from flint.jobs.compose import _default_generator
    assert callable(_default_generator)


def test_block_schema_shape() -> None:
    assert BLOCK_SCHEMA["type"] == "object"
    assert "blocks" in BLOCK_SCHEMA["properties"]
