"""TS-004：Topic 生成器（LLMProvider 注入、embedding、GenerationRecord、接地）。

合成 ScriptedProvider + DeterministicHashBackend，CI 离线（真机 qwen3.6 NEVER 触）。
覆盖：全字段生成 + embedding 1024 确定性 + GenerationRecord（prompt_version/model/
字段映射）+ 接地丢弃集合外 citation + evidences 空→speculative + keyword_mapping 保真
+ prompt 装载 seed。
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.domain.models import JSON, GenerationRecord, Topic, TopicSeed
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.llm.structured import validate_schema
from flint.topic.generate import (
    TOPIC_PROMPT_NAME,
    TOPIC_SCHEMA,
    generate_topic,
)

pytestmark = pytest.mark.compose

TS = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
ALLOWED = {"cit-1", "cit-2"}

SEED = TopicSeed(
    seed_id="ts-s1", origin_id="ts-o1",
    keywords=["扩散模型", "药物发现"], hypothesis="跨热点联想一句话",
    context_text="关联假设：跨热点联想一句话",
)

FULL: JSON = {
    "one_liner": "用扩散模型加速药物发现的工作台",
    "target_user_tag": "药物研发团队",
    "form_factor_tag": "SaaS",
    "why_now": {
        "claim": "扩散模型刚在结构预测取得突破",
        "evidences": [
            {"event": "结构预测突破", "event_date": "2026-07-01", "citation_id": "cit-1"},
            {"event": "编造事件", "event_date": "2026-07-02", "citation_id": "cit-FAKE"},
        ],
    },
    "keyword_mapping": {"扩散模型": ["diffusion", "生成式"]},
}


class ScriptedProvider:
    def __init__(self, payload: JSON) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.prompts.append(prompt)
        return self.payload


def _embed() -> EmbeddingService:
    return EmbeddingService(DeterministicHashBackend(dim=1024))


def test_schema_valid_for_full_payload() -> None:
    assert validate_schema(TOPIC_SCHEMA, FULL) == []
    assert TOPIC_PROMPT_NAME == "topic_gen@1"


def test_generate_full_topic_and_record() -> None:
    provider = ScriptedProvider(FULL)
    topic, record = generate_topic(
        provider, SEED, topic_id="ts-t1", job_id="job-1", model="qwen3.6",
        record_id="gr-1", ts=TS, embed_service=_embed(),
        allowed_citation_ids=ALLOWED)
    assert isinstance(topic, Topic) and isinstance(record, GenerationRecord)
    assert topic.topic_id == "ts-t1" and topic.seed_id == "ts-s1"
    assert topic.one_liner == "用扩散模型加速药物发现的工作台"
    assert topic.target_user_tag == "药物研发团队" and topic.form_factor_tag == "SaaS"
    assert topic.keyword_mapping == {"扩散模型": ["diffusion", "生成式"]}
    assert len(topic.embedding) == 1024
    # GenerationRecord 溯源（owner #4 + 字段映射）
    assert record.prompt_version.startswith("topic_gen@1#")
    assert record.model == "qwen3.6"
    assert record.deliverable_id == "ts-t1"          # 映射：产物即 topic
    assert record.retrieval_snapshot_id == "ts-s1"   # 映射：种子快照
    assert record.job_id == "job-1" and record.ts == TS
    assert record.params["seed_id"] == "ts-s1"
    assert record.user_evidence_verdict_optin is False
    # prompt 装载 seed
    assert "跨热点联想一句话" in provider.prompts[0]
    assert "药物发现" in provider.prompts[0]


def test_grounding_drops_out_of_ledger_citation() -> None:
    provider = ScriptedProvider(FULL)
    topic, _ = generate_topic(
        provider, SEED, topic_id="ts-t2", job_id="j", model="m",
        record_id="gr-2", ts=TS, embed_service=_embed(),
        allowed_citation_ids=ALLOWED)
    cids = [e.citation_id for e in topic.why_now.evidences]
    assert cids == ["cit-1"]                 # cit-FAKE 丢弃（集合外）
    assert topic.why_now.speculative is False  # 仍有 1 条接地证据


def test_empty_evidences_marks_speculative() -> None:
    payload = {**FULL, "why_now": {"claim": "尚无硬证据", "evidences": []}}
    provider = ScriptedProvider(payload)
    topic, _ = generate_topic(
        provider, SEED, topic_id="ts-t3", job_id="j", model="m",
        record_id="gr-3", ts=TS, embed_service=_embed(),
        allowed_citation_ids=ALLOWED)
    assert topic.why_now.evidences == []
    assert topic.why_now.speculative is True   # [C2]


def test_all_citations_out_of_ledger_becomes_speculative() -> None:
    payload = {**FULL, "why_now": {"claim": "全是编造", "evidences": [
        {"event": "e", "event_date": "2026-07-01", "citation_id": "cit-NOPE"}]}}
    provider = ScriptedProvider(payload)
    topic, _ = generate_topic(
        provider, SEED, topic_id="ts-t4", job_id="j", model="m",
        record_id="gr-4", ts=TS, embed_service=_embed(),
        allowed_citation_ids=ALLOWED)
    assert topic.why_now.evidences == []       # 全丢弃
    assert topic.why_now.speculative is True


def test_bad_date_evidence_dropped() -> None:
    payload = {**FULL, "why_now": {"claim": "日期坏", "evidences": [
        {"event": "e", "event_date": "not-a-date", "citation_id": "cit-1"}]}}
    provider = ScriptedProvider(payload)
    topic, _ = generate_topic(
        provider, SEED, topic_id="ts-t5", job_id="j", model="m",
        record_id="gr-5", ts=TS, embed_service=_embed(),
        allowed_citation_ids=ALLOWED)
    assert topic.why_now.evidences == []       # 不可解析日期丢弃
    assert topic.why_now.speculative is True


def test_prompt_v2_fills_cards_block_and_records_version() -> None:
    # Phase 0.5：topic_gen@2 强接地模板——注入被引卡内容+日期到 {cards} 占位。
    provider = ScriptedProvider(FULL)
    cards_ctx = 'cit-1 = "钙钛矿组件"（日期 2026-06-29）'
    _topic, record = generate_topic(
        provider, SEED, topic_id="ts-v2", job_id="j", model="m",
        record_id="gr-v2", ts=TS, embed_service=_embed(),
        allowed_citation_ids=ALLOWED,
        prompt_name="topic_gen@2", cards_context=cards_ctx)
    assert record.prompt_version.startswith("topic_gen@2#")
    assert cards_ctx in provider.prompts[0]           # 卡内容+日期已注入
    assert "{cards}" not in provider.prompts[0]        # 占位已填


def test_default_prompt_stays_v1_unchanged() -> None:
    # 默认路径仍 @1、无 {cards} 占位——冻结既有行为（4 家 API 资产口径不动）。
    provider = ScriptedProvider(FULL)
    _t, record = generate_topic(
        provider, SEED, topic_id="ts-v1", job_id="j", model="m",
        record_id="gr-v1", ts=TS, embed_service=_embed(),
        allowed_citation_ids=ALLOWED)
    assert record.prompt_version.startswith("topic_gen@1#")
    assert "{cards}" not in provider.prompts[0]


def test_embedding_deterministic_for_same_one_liner() -> None:
    svc = _embed()
    provider = ScriptedProvider(FULL)
    t1, _ = generate_topic(provider, SEED, topic_id="ts-ta", job_id="j", model="m",
                           record_id="gr-a", ts=TS, embed_service=svc,
                           allowed_citation_ids=ALLOWED)
    provider2 = ScriptedProvider(FULL)
    t2, _ = generate_topic(provider2, SEED, topic_id="ts-tb", job_id="j", model="m",
                           record_id="gr-b", ts=TS, embed_service=svc,
                           allowed_citation_ids=ALLOWED)
    assert t1.embedding == t2.embedding        # 同 one_liner → 同 embedding
