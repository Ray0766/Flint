"""TS-003：非 combo 入口关键词抽取器（LLMProvider 注入、合成 fixture、CI 离线）。

真机 qwen3.6 = 资源触点，NEVER 在此触发；全部用 ScriptedProvider 合成 payload。
覆盖：抽取+去重+strip、prompt 版本化装载、空词拒（NEVER 猜）、结构化输出耗尽传播
（第三铁律 job failed 绝不猜）、非 combo seed 回填 keywords。
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from flint.domain.models import JSON, Origin, Principal, TopicSeed
from flint.llm.structured import StructuredOutputExhausted, validate_schema
from flint.topic.create import create_origin, origin_to_seed
from flint.topic.extract import (
    KEYWORD_PROMPT_NAME,
    KEYWORD_SCHEMA,
    KeywordExtractionError,
    extract_keywords,
    seed_with_keywords,
)

pytestmark = pytest.mark.compose

NOW = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
OWNER = Principal(kind="user", id="u-1")


class ScriptedProvider:
    def __init__(self, payload: JSON | None = None, exhaust: bool = False) -> None:
        self.payload = payload
        self.exhaust = exhaust
        self.prompts: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.prompts.append(prompt)
        if self.exhaust:
            raise StructuredOutputExhausted(1 + max_retries, ["$.keywords: required"])
        assert self.payload is not None
        return self.payload


def test_schema_is_valid_and_good_payload_passes() -> None:
    good: JSON = {"keywords": ["扩散模型", "药物发现", "湿实验"]}
    assert validate_schema(KEYWORD_SCHEMA, good) == []


def test_extract_dedupes_strips_and_feeds_context() -> None:
    provider = ScriptedProvider(payload={
        "keywords": ["扩散模型", " 扩散模型 ", "药物发现", "  ", "湿实验"]})
    kws = extract_keywords(provider, "一个用扩散模型做药物发现的点子")
    assert kws == ["扩散模型", "药物发现", "湿实验"]     # strip + 去重 + 丢空
    assert "一个用扩散模型做药物发现的点子" in provider.prompts[0]  # 上下文入 prompt


def test_prompt_is_versioned() -> None:
    # 装载走版本库（keyword_extract@1），锁校验通过；prompt 名固定
    provider = ScriptedProvider(payload={"keywords": ["a", "b", "c"]})
    extract_keywords(provider, "ctx")
    assert KEYWORD_PROMPT_NAME == "keyword_extract@1"


def test_empty_keywords_rejected_never_guess() -> None:
    provider = ScriptedProvider(payload={"keywords": []})
    with pytest.raises(KeywordExtractionError):
        extract_keywords(provider, "ctx")
    provider2 = ScriptedProvider(payload={"keywords": ["  ", ""]})
    with pytest.raises(KeywordExtractionError):
        extract_keywords(provider2, "ctx")


def test_structured_exhausted_propagates_job_failed() -> None:
    # 重试 ≤2 耗尽 → 传播，NEVER 猜测兜底（第三铁律）
    provider = ScriptedProvider(exhaust=True)
    with pytest.raises(StructuredOutputExhausted):
        extract_keywords(provider, "ctx")


def test_seed_with_keywords_fills_non_combo_seed() -> None:
    # create_origin/origin_to_seed 是 async；idea 无需 catalog
    origin = asyncio.run(_mk_idea())
    seed = asyncio.run(origin_to_seed(seed_id="ts-s-idea", origin=origin))
    assert seed.keywords == []                       # TS-002 留空
    provider = ScriptedProvider(payload={"keywords": ["扩散模型", "药物发现"]})
    filled = seed_with_keywords(provider, seed)
    assert isinstance(filled, TopicSeed)
    assert filled.keywords == ["扩散模型", "药物发现"]  # 回填
    assert filled.seed_id == seed.seed_id            # 其余字段不变
    assert filled.origin_id == seed.origin_id
    assert filled.hypothesis is None
    assert filled.context_text == seed.context_text


async def _mk_idea() -> Origin:
    return await create_origin(
        origin_id="ts-o-idea", kind="idea", owner=OWNER,
        payload={"text": "一个用扩散模型做药物发现的点子"}, created_at=NOW)
