"""M2-028 acceptance tests: citation alignment stage 1 (pre-verdict).

Acceptance (tasks.json M2-028):
  - only key evidence checked, cap K=8 configurable (S4 Open Question on file)
  - failure demotes to D (never judge while sick) case
"""
from __future__ import annotations

from datetime import UTC, date, datetime

from flint.align.stage1 import (
    DEFAULT_K_CAP,
    LLMCitationAligner,
    align_key_evidence,
)
from flint.domain.models import JSON, Doc
from flint.llm.cache import LLMJudgmentCache

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(i: int) -> Doc:
    return Doc(
        doc_id=f"doc-{i}", source_id="crossref", kind="paper",
        title=f"evidence {i}", url=f"https://example.com/{i}",
        published_at=date(2026, 1, 1), meta={"fetched_at": FETCHED},
        origin="retrieved", access="public",
    )


class ScriptedProvider:
    """按 doc_id 出对齐判定；记录调用序。"""

    def __init__(self, verdicts: dict[str, str], default: str = "supports") -> None:
        self.verdicts = verdicts
        self.default = default
        self.calls: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls.append(prompt)
        for doc_id, verdict in self.verdicts.items():
            if doc_id in prompt:
                return {"alignment": verdict}
        return {"alignment": self.default}


def make_aligner(
    provider: ScriptedProvider, cache: LLMJudgmentCache | None = None
) -> LLMCitationAligner:
    return LLMCitationAligner(provider=provider, cache=cache)


def test_protocol_signature_returns_alignment_literal() -> None:
    aligner = make_aligner(ScriptedProvider({}))
    result = aligner.align("固态电池 2027 年量产", make_doc(1), stage="verdict")
    assert result == "supports"


def test_cap_defaults_to_k8_and_is_configurable() -> None:
    assert DEFAULT_K_CAP == 8
    provider = ScriptedProvider({})
    aligner = make_aligner(provider)
    pairs = [(f"claim-{i}", make_doc(i)) for i in range(10)]

    result = align_key_evidence(aligner, pairs)
    assert len(result.checked) == 8, "only key evidence within the cap is checked"
    assert result.skipped_beyond_cap == 2
    assert len(provider.calls) == 8

    tight = align_key_evidence(make_aligner(ScriptedProvider({})), pairs, k_cap=3)
    assert len(tight.checked) == 3 and tight.skipped_beyond_cap == 7


def test_all_supports_passes_without_demotion() -> None:
    result = align_key_evidence(
        make_aligner(ScriptedProvider({})), [("c", make_doc(1)), ("c2", make_doc(2))]
    )
    assert result.passed is True
    assert result.demote_to_d is False


def test_any_failure_demotes_to_d() -> None:
    """绝不带病判定：关键证据一条未过 → 降 D。"""
    provider = ScriptedProvider({"doc-2": "partial"})
    result = align_key_evidence(
        make_aligner(provider),
        [("c1", make_doc(1)), ("c2", make_doc(2)), ("c3", make_doc(3))],
    )
    assert result.passed is False
    assert result.demote_to_d is True
    kinds = {doc_id: alignment for _, doc_id, alignment in result.checked}
    assert kinds["doc-2"] == "partial"


def test_unsupported_also_demotes() -> None:
    provider = ScriptedProvider({"doc-1": "unsupported"})
    result = align_key_evidence(make_aligner(provider), [("c1", make_doc(1))])
    assert result.demote_to_d is True


def test_judgment_cache_hits_skip_calls() -> None:
    provider = ScriptedProvider({})
    cache = LLMJudgmentCache()
    aligner = make_aligner(provider, cache=cache)
    doc = make_doc(1)
    aligner.align("同一断言", doc, stage="verdict")
    aligner.align("同一断言", doc, stage="verdict")
    assert len(provider.calls) == 1, "identical (claim, doc, stage) hits the cache"
    assert cache.hits == 1
