"""TS-009：combo 生成编排器——串 TS-004 生成 + TS-005 差异约束 + TS-006 建 Project。

- Origin→TopicSeed 后，循环 generate_topic 生成目标数主题（每主题走 GenerationRecord，
  #4），经 differentiate（[C1] δ 真跑、定点重生成 ≤3、诚实降级 #7）筛差异化主题，
  越下界 backfill 续生成、越上界截断（#2 5~8），再 build_project 装容器。
- provider 注入（模型无关）；接地铁律照 generate_topic（集合外 citation 丢弃、
  evidences 空→speculative）。CI 离线：真机 qwen3.6 = 资源触点，NEVER 在此触。
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from flint.domain.models import GenerationRecord, Principal, Project, Topic, TopicSeed
from flint.domain.protocols import LLMProvider
from flint.embed import EmbeddingService
from flint.topic.differentiate import (
    MAX_TOPICS,
    MIN_TOPICS,
    DifferentiationOutcome,
    backfill_shortfall,
    differentiate,
)
from flint.topic.generate import TOPIC_PROMPT_NAME, generate_topic
from flint.topic.project import build_project

# (topic_id, record_id) 工厂——调用方注入，保证 id 唯一且可复现（无隐藏 uuid）。
IdFactory = Callable[[], tuple[str, str]]


@dataclass
class ComboResult:
    topics: list[Topic]
    records: list[GenerationRecord]
    outcome: DifferentiationOutcome
    project: Project


def orchestrate_combo(
    provider: LLMProvider,
    seed: TopicSeed,
    embed_service: EmbeddingService,
    *,
    id_factory: IdFactory,
    allowed_citation_ids: Iterable[str],
    model: str,
    job_id: str,
    ts: datetime,
    project_id: str,
    owner: Principal,
    target: int = 6,
    delta: float | None = None,
    max_backfill_rounds: int = 2,
    max_retries: int = 2,
    cards_context: str = "",
    prompt_name: str = TOPIC_PROMPT_NAME,
) -> ComboResult:
    """BL-02：`cards_context` 与 `prompt_name` 两个旋钮都露出来。

    此前编排器一路走 `generate_topic` 的默认值（空串 + @1），于是**生产路径上
    `{cards}` 永远是空的**——而 harness 自己拼上下文，一直是绿的。
    两条路分叉时，绿的那条不是生产那条。
    """
    allowed = set(allowed_citation_ids)
    records: list[GenerationRecord] = []

    def gen_one() -> Topic:
        topic_id, record_id = id_factory()
        topic, record = generate_topic(
            provider, seed, topic_id=topic_id, job_id=job_id, model=model,
            record_id=record_id, ts=ts, embed_service=embed_service,
            allowed_citation_ids=allowed, max_retries=max_retries,
            cards_context=cards_context, prompt_name=prompt_name,
        )
        records.append(record)
        return topic

    # 初批：目标数钳制到 [MIN, MAX]
    initial = min(max(target, MIN_TOPICS), MAX_TOPICS)
    topics = [gen_one() for _ in range(initial)]
    outcome = differentiate(topics, regenerate=lambda _t: gen_one(), delta=delta)
    kept = outcome.topics

    # 越下界 backfill 续生成（诚实降级仍可能少出，#7）
    rounds = 0
    while len(kept) < MIN_TOPICS and rounds < max_backfill_rounds:
        for _ in range(backfill_shortfall(len(kept))):
            kept.append(gen_one())
        outcome = differentiate(kept, regenerate=lambda _t: gen_one(),
                                delta=outcome.delta)
        kept = outcome.topics
        rounds += 1

    project = build_project(
        project_id=project_id, owner=owner, origin_id=seed.origin_id,
        topic_ids=[t.topic_id for t in kept], created_at=ts,
    )
    return ComboResult(topics=kept, records=records, outcome=outcome, project=project)


# 越上界硬截断已在 differentiate 内（topics[:MAX_TOPICS]）；此处再声明常量出处
__all__ = ["MAX_TOPICS", "MIN_TOPICS", "ComboResult", "orchestrate_combo"]
