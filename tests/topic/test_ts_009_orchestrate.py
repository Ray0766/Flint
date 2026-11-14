"""TS-009：combo 生成编排器（Origin→生成 N 主题→[C1] 差异约束→建 Project）。

注入 provider（模型无关），合成 fixture 全测（CI 离线，真机 qwen3.6 NEVER 在此触）。
覆盖：生成目标数、差异约束真跑、重生成解冲突、诚实降级、backfill、每主题 record、
接地照走、建 Project。
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from flint.domain.models import JSON, Principal, Project, TopicSeed
from flint.embed import DeterministicHashBackend, EmbeddingService
from flint.topic.orchestrate import ComboResult, orchestrate_combo

pytestmark = pytest.mark.compose

TS = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC)
OWNER = Principal(kind="user", id="u-1")
ALLOWED = {"cit-1"}
SEED = TopicSeed(seed_id="ts-s1", origin_id="ts-o1", keywords=["扩散模型"],
                 hypothesis="跨热点联想", context_text="关联假设：跨热点联想")


def _payload(i: int, *, tu: str, ff: str, evidences: list[JSON] | None = None) -> JSON:
    return {
        "one_liner": f"主题方向 {i}",
        "target_user_tag": tu,
        "form_factor_tag": ff,
        "why_now": {
            "claim": f"时机 {i}",
            "evidences": evidences if evidences is not None
            else [{"event": "e", "event_date": "2026-07-01", "citation_id": "cit-1"}],
        },
        "keyword_mapping": {"扩散模型": [f"kw{i}"]},
    }


class SequenceProvider:
    """按序返回不同 payload（每次生成给不同 one_liner/tag → 不同 embedding）。"""

    def __init__(self, payloads: list[JSON]) -> None:
        self._payloads = payloads
        self._i = 0
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        payload = self._payloads[min(self._i, len(self._payloads) - 1)]
        self._i += 1
        self.calls += 1
        return payload


class ConstProvider:
    """恒返同一 payload（同 one_liner/tag → 冲突，重生成不解 → 降级）。"""

    def __init__(self, payload: JSON) -> None:
        self.payload = payload
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls += 1
        return self.payload


def _embed() -> EmbeddingService:
    return EmbeddingService(DeterministicHashBackend(dim=1024))


def _ids() -> Any:
    counter = {"n": 0}

    def factory() -> tuple[str, str]:
        counter["n"] += 1
        return (f"ts-t{counter['n']}", f"ts-gr{counter['n']}")

    return factory


DISTINCT = [_payload(i, tu=f"u{i}", ff=f"f{i}") for i in range(12)]


def test_orchestrates_distinct_batch_builds_project() -> None:
    provider = SequenceProvider(DISTINCT)
    result = orchestrate_combo(
        provider, SEED, _embed(), id_factory=_ids(), allowed_citation_ids=ALLOWED,
        model="qwen3.6", job_id="job-1", ts=TS, project_id="ts-p1", owner=OWNER,
        target=6, delta=0.5)
    assert isinstance(result, ComboResult)
    assert 5 <= len(result.topics) <= 8               # combo 5~8
    assert result.outcome.degraded is False
    assert isinstance(result.project, Project)
    assert result.project.project_id == "ts-p1"
    assert result.project.origin_id == "ts-o1"
    assert result.project.topic_ids == [t.topic_id for t in result.topics]
    # 每主题一条 GenerationRecord（#4，含重生成的）
    assert len(result.records) == provider.calls
    assert all(r.prompt_version.startswith("topic_gen@1#") for r in result.records)
    assert all(len(t.embedding) == 1024 for t in result.topics)


def test_upper_bound_truncates_to_eight() -> None:
    provider = SequenceProvider(DISTINCT)
    result = orchestrate_combo(
        provider, SEED, _embed(), id_factory=_ids(), allowed_citation_ids=ALLOWED,
        model="m", job_id="j", ts=TS, project_id="ts-p2", owner=OWNER,
        target=8, delta=0.5)
    assert len(result.topics) == 8                    # 越上界截断


def test_const_provider_degrades_honestly_never_fabricate() -> None:
    provider = ConstProvider(_payload(0, tu="u", ff="f"))
    result = orchestrate_combo(
        provider, SEED, _embed(), id_factory=_ids(), allowed_citation_ids=ALLOWED,
        model="m", job_id="j", ts=TS, project_id="ts-p3", owner=OWNER,
        target=6, delta=0.5, max_backfill_rounds=1)
    # 全同 → 差异约束诚实降级：少出 + 标冲突，NEVER 硬造
    assert result.outcome.degraded is True
    assert len(result.outcome.dropped_conflicts) >= 1
    assert len(result.topics) < 5                     # 少出（诚实）
    assert result.project.topic_ids == [t.topic_id for t in result.topics]


def test_grounding_out_of_ledger_citation_dropped() -> None:
    payloads = [_payload(i, tu=f"u{i}", ff=f"f{i}", evidences=[
        {"event": "编造", "event_date": "2026-07-01", "citation_id": "cit-FAKE"}])
        for i in range(6)]
    provider = SequenceProvider(payloads)
    result = orchestrate_combo(
        provider, SEED, _embed(), id_factory=_ids(), allowed_citation_ids=ALLOWED,
        model="m", job_id="j", ts=TS, project_id="ts-p4", owner=OWNER,
        target=6, delta=0.5)
    # 集合外 citation 丢弃 → evidences 空 → speculative
    assert all(t.why_now.speculative for t in result.topics)
    assert all(t.why_now.evidences == [] for t in result.topics)


def test_delta_none_estimates_from_embedding_space() -> None:
    provider = SequenceProvider(DISTINCT)
    result = orchestrate_combo(
        provider, SEED, _embed(), id_factory=_ids(), allowed_citation_ids=ALLOWED,
        model="m", job_id="j", ts=TS, project_id="ts-p5", owner=OWNER, target=6)
    assert result.outcome.delta > 0.0                 # δ 真跑估计（非 report_only）
