"""FE-CORE-006：guidance 穿透 + 铁律断言（指令只引导、NEVER 变事实）。

- guidance 穿进块级生成 prompt（build_block_regenerator），**只引导方向**；
- **铁律（test-first）**：指令要证据外的数字/事实 → 走 gap / 不断言，账本外事实经通道门
  拒稿（DraftViolation），NEVER 编造出处。全离线（RecordingProvider，无网无模型）。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.compose.draft import DraftViolation
from flint.compose.llm_generator import build_block_regenerator
from flint.domain.models import (
    JSON,
    Block,
    Completion,
    Fact,
    FactsLedger,
    ParagraphContent,
    Principal,
    SectionSpec,
    TextSpan,
    UserProfile,
)
from flint.intervene.block_regen import regenerate_block

NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
SPEC = SectionSpec(section_id="s1", inputs=[], check_questions=[], charts=[])


class RecordingProvider:
    """离线 LLMProvider 桩：记录收到的 prompt，返回预设结构化 payload。"""

    def __init__(self, payload: JSON) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> Completion:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.prompts.append(prompt)
        return self.payload


def _profile() -> UserProfile:
    return UserProfile(profile_id="p", owner=Principal(kind="user", id="u"),
                       identity={}, research={}, team=[], assets={}, constraints={},
                       track_record=[], locale="zh-CN", sensitivity_overrides={},
                       updated_at=NOW)


def _ledger(fact_ids: list[str]) -> FactsLedger:
    facts = [Fact(fact_id=f, statement="s", value=None, unit=None, citation_ids=[],
                  status="frozen", origin="injected", created_in_version=1)
             for f in fact_ids]
    return FactsLedger(ledger_id="l", project_id="p", version=1, parent_version=None,
                       derivation_reason="freeze", facts=facts, created_from=[],
                       created_at=NOW, actor="u")


def _target() -> Block:
    return Block(block_id="b1", deliverable_id="d", section_id="s1", order=0,
                 type="paragraph",
                 content=ParagraphContent(kind="paragraph", spans=[TextSpan(kind="text", text="旧")]),
                 claim_ids=[], fact_ids=[], author="system", revision=1, locked=False)


def test_guidance_flows_into_prompt_as_direction_only() -> None:
    provider = RecordingProvider({"blocks": [{"type": "paragraph", "text": "新", "fact_ids": []}]})
    regen = build_block_regenerator(provider, "PROMPT", guidance="语气更学术、加一句风险")
    regen(_target(), [])
    prompt = provider.prompts[0]
    assert "语气更学术、加一句风险" in prompt          # guidance 穿进
    assert "user_guidance" in prompt and "NEVER 当事实" in prompt  # 只引导框定在场


def test_guidance_requesting_unsupported_fact_cannot_fabricate() -> None:
    """指令要证据外的数字 → 若模型硬引账本外 fact_id，通道门拒稿（NEVER 编造出处）。"""
    # 模拟：模型迎合指令、引了一个账本里没有的 fact-99
    provider = RecordingProvider({"blocks": [
        {"type": "paragraph", "text": "市场规模高达 500 亿", "fact_ids": ["fact-99"]},
    ]})
    regen = build_block_regenerator(provider, "PROMPT", guidance="加一个市场规模数字")
    section = [_target()]
    with pytest.raises(DraftViolation):
        regenerate_block(section, "b1", regen, SPEC, _ledger(["fact-1"]),
                         entries_by_id={}, profile=_profile())


def test_guidance_unsupported_gaps_instead_of_fabricating() -> None:
    """正路：模型不引账本外事实，改留白（gap_notice）——不断言、不编造，过门。"""
    provider = RecordingProvider({"blocks": [
        {"type": "gap_notice", "hints_ref": "缺市场规模权威来源"},
    ]})
    regen = build_block_regenerator(provider, "PROMPT", guidance="加一个市场规模数字")
    section = [_target()]
    out = regenerate_block(section, "b1", regen, SPEC, _ledger([]),
                           entries_by_id={}, profile=_profile())
    assert any(b.content.kind == "gap_notice" for b in out)


def test_no_guidance_prompt_has_no_user_guidance_block() -> None:
    provider = RecordingProvider({"blocks": [{"type": "paragraph", "text": "新", "fact_ids": []}]})
    build_block_regenerator(provider, "PROMPT")(_target(), [])
    assert "user_guidance" not in provider.prompts[0]
