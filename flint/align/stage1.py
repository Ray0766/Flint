"""引用对齐 · 第一段（verdict 前，M2-028；PDD v0.3.1 §2.1 / D1-c）。

- 只校验 verdict 直接依赖的关键证据（判 A 证伪 / 判 C 支持 / 判 B top 竞品），
  上限 K=8 配置化（S4 Open Question 初值，成本实测后调参）。
- 任一关键证据未过（partial / unsupported）→ demote_to_d：**绝不带病判定**，
  规则引擎（M2-034/036）据此降 D。
- 判定为幂等判别类：经 LLMJudgmentCache 缓存（同 (claim, doc, stage) 命中零调用）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal, cast

from flint.domain.models import JSON, Alignment, Doc
from flint.domain.protocols import LLMProvider
from flint.llm.cache import LLMJudgmentCache

DEFAULT_K_CAP: Final[int] = 8

ALIGN_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "alignment": {
            "type": "string",
            "enum": ["supports", "partial", "unsupported"],
        }
    },
    "required": ["alignment"],
    "additionalProperties": False,
}

_PROMPT = (
    "判定引用对齐：给定断言与证据摘要，判定证据对断言是 supports / partial / "
    "unsupported。只输出符合 schema 的 JSON。\n"
    "断言：{claim}\n"
    "证据（doc_id={doc_id}）：{title}\nURL：{url}"
)


class LLMCitationAligner:
    """冻结协议 CitationAligner 实现（judgment 类调用，小模型档位）。"""

    def __init__(
        self,
        provider: LLMProvider,
        cache: LLMJudgmentCache | None = None,
        max_retries: int = 2,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._max_retries = max_retries

    def align(
        self, claim: str, evidence: Doc, stage: Literal["verdict", "draft"]
    ) -> Alignment:
        prompt = _PROMPT.format(
            claim=claim, doc_id=evidence.doc_id, title=evidence.title, url=evidence.url
        )

        def compute() -> JSON:
            return self._provider.generate_structured(
                prompt, ALIGN_SCHEMA, self._max_retries
            )

        if self._cache is not None:
            payload = self._cache.cached(
                "judgment", f"align|{stage}|{claim}|{evidence.doc_id}", compute
            )
        else:
            payload = compute()
        return cast(Alignment, payload["alignment"])


@dataclass
class VerdictAlignmentResult:
    checked: list[tuple[str, str, Alignment]] = field(default_factory=list)
    passed: bool = True
    demote_to_d: bool = False
    skipped_beyond_cap: int = 0


def align_key_evidence(
    aligner: LLMCitationAligner,
    pairs: list[tuple[str, Doc]],
    k_cap: int = DEFAULT_K_CAP,
) -> VerdictAlignmentResult:
    result = VerdictAlignmentResult()
    result.skipped_beyond_cap = max(0, len(pairs) - k_cap)
    for claim, doc in pairs[:k_cap]:
        alignment = aligner.align(claim, doc, stage="verdict")
        result.checked.append((claim, doc.doc_id, alignment))
        if alignment != "supports":
            result.passed = False
            result.demote_to_d = True
    return result
