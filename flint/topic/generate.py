"""TS-004：Topic 生成器（LLMProvider 注入、prompt 版本化、GenerationRecord 溯源）。

- 按 seed（keywords + hypothesis + context）经注入 LLMProvider 生成 one_liner /
  target_user_tag / form_factor_tag / why_now / keyword_mapping；embedding 由
  flint/embed.py 对 one_liner 编码（确定性、非 LLM）。
- 接地铁律（S2-2）：why_now.evidences 的 citation_id 只认「可引用集合」，集合外/
  日期不可解析的证据一律丢弃（LLM NEVER 编造出处）；evidences 空 → speculative=True
  （[C2]）。
- 可复现（S2-2 第三铁律）：每次生成产出 GenerationRecord 记 prompt_version + model
  （字段映射见 docs/v0.4-问题单.md「Topic 生成经 GenerationRecord 的字段映射」——
  deliverable_id:=topic_id / retrieval_snapshot_id:=seed_id，generation_records 无 FK）。
- 差异约束 [C1] / 5~8 计数 / 诚实降级归 TS-005；本卡产**单个**接地 Topic + 记录。
- CI 离线：真机 qwen3.6 = 资源触点（NEVER 在此触发），测试全用合成 provider +
  DeterministicHashBackend。
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Final

from flint.domain.models import (
    JSON,
    GenerationRecord,
    Topic,
    TopicSeed,
    WhyNow,
    WhyNowEvidence,
)
from flint.domain.protocols import LLMProvider
from flint.embed import EmbeddingService
from flint.llm.prompts import load_prompt

PROMPTS_DIR: Final[Path] = Path(__file__).resolve().parents[2] / "prompts"
TOPIC_PROMPT_NAME: Final[str] = "topic_gen@1"

_EVIDENCE_ITEM: Final[JSON] = {
    "type": "object",
    "properties": {
        "event": {"type": "string", "minLength": 1},
        "event_date": {"type": "string", "minLength": 1},
        "citation_id": {"type": "string", "minLength": 1},
    },
    "required": ["event", "event_date", "citation_id"],
    "additionalProperties": False,
}

TOPIC_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "one_liner": {"type": "string", "minLength": 1},
        "target_user_tag": {"type": "string", "minLength": 1},
        "form_factor_tag": {"type": "string", "minLength": 1},
        "why_now": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "minLength": 1},
                "evidences": {"type": "array", "items": _EVIDENCE_ITEM},
            },
            "required": ["claim", "evidences"],
            "additionalProperties": False,
        },
        "keyword_mapping": {"type": "object"},
    },
    "required": [
        "one_liner", "target_user_tag", "form_factor_tag",
        "why_now", "keyword_mapping",
    ],
    "additionalProperties": False,
}


def _ground_evidences(
    raw: list[JSON], allowed: set[str]
) -> list[WhyNowEvidence]:
    """只保留 citation_id ∈ 白名单 且 日期可解析 的证据；其余丢弃（NEVER 编造）。"""
    kept: list[WhyNowEvidence] = []
    for item in raw:
        cid = str(item["citation_id"])
        if cid not in allowed:
            continue
        try:
            parsed = date.fromisoformat(str(item["event_date"]))
        except ValueError:
            continue
        kept.append(
            WhyNowEvidence(event=str(item["event"]), event_date=parsed, citation_id=cid)
        )
    return kept


def _fill_prompt(
    text: str, seed: TopicSeed, allowed: set[str], cards_context: str
) -> str:
    return (
        text.replace("{allowed_citations}", "\n".join(sorted(allowed)))
        .replace("{cards}", cards_context)  # @2 强接地：被引卡内容+日期；@1 无此占位=空操作
        .replace("{keywords}", ", ".join(seed.keywords))
        .replace("{hypothesis}", seed.hypothesis or "")
        .replace("{context}", seed.context_text)
    )


def generate_topic(
    provider: LLMProvider,
    seed: TopicSeed,
    *,
    topic_id: str,
    job_id: str,
    model: str,
    record_id: str,
    ts: datetime,
    embed_service: EmbeddingService,
    allowed_citation_ids: Iterable[str],
    cost: float = 0.0,
    max_retries: int = 2,
    prompts_dir: Path | None = None,
    prompt_name: str = TOPIC_PROMPT_NAME,
    cards_context: str = "",
) -> tuple[Topic, GenerationRecord]:
    directory = prompts_dir or PROMPTS_DIR
    prompt = load_prompt(directory, prompt_name, enforce_lock=True)
    allowed = set(allowed_citation_ids)
    payload = provider.generate_structured(
        _fill_prompt(prompt.text, seed, allowed, cards_context),
        TOPIC_SCHEMA, max_retries,
    )
    why_now_raw = payload["why_now"]
    evidences = _ground_evidences(list(why_now_raw["evidences"]), allowed)
    why_now = WhyNow(
        claim=str(why_now_raw["claim"]),
        evidences=evidences,
        speculative=len(evidences) == 0,  # [C2] evidences 空 → True
    )
    one_liner = str(payload["one_liner"])
    embedding = embed_service.embed([one_liner])[0]  # 确定性、非 LLM
    topic = Topic(
        topic_id=topic_id,
        seed_id=seed.seed_id,
        one_liner=one_liner,
        target_user_tag=str(payload["target_user_tag"]),
        form_factor_tag=str(payload["form_factor_tag"]),
        why_now=why_now,
        keyword_mapping=dict(payload["keyword_mapping"]),
        embedding=embedding,
    )
    record = GenerationRecord(
        record_id=record_id,
        deliverable_id=topic_id,          # 语义借用：本记录生成的产物即该 Topic（无 FK）
        job_id=job_id,
        prompt_version=prompt.version,    # "topic_gen@1#<hash>"
        model=model,
        params={"seed_id": seed.seed_id, "max_retries": max_retries},
        retrieval_snapshot_id=seed.seed_id,
        ledger_version=None,
        pricebook_version=None,
        user_evidence_verdict_optin=False,
        ts=ts,
        cost=cost,
        alignment_rate=None,
        structured_output_failures=0,
    )
    return topic, record
