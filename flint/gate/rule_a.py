"""A 档规则（M2-034，证伪硬门槛；VerdictResult docstring / PDD v0.3.1 §2.2）。

- >=1 条 stage="verdict" 对齐通过的证伪证据才判 A；
- 默认须 origin="retrieved"；user_provided 单独支撑判 A 需显式 optin，
  未确认的用户证据 NEVER 进入引用（blocked_pending_optin 供 UI 引导），
  确认后 MUST 经 backfill_optin 回填 GenerationRecord.user_evidence_verdict_optin；
- 任一关键证据对齐未过 → demote_to_d（stage1 语义直传：绝不带病判定）。
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from flint.align.stage1 import DEFAULT_K_CAP, LLMCitationAligner, align_key_evidence
from flint.domain.models import Doc, GenerationRecord


@dataclass
class RuleAResult:
    satisfied: bool
    demote_to_d: bool = False
    refute_doc_ids: list[str] = field(default_factory=list)
    used_user_evidence_only: bool = False
    blocked_pending_optin: bool = False


def evaluate_rule_a(
    aligner: LLMCitationAligner,
    refute_pairs: list[tuple[str, Doc]],
    user_evidence_optin: bool,
    k_cap: int = DEFAULT_K_CAP,
) -> RuleAResult:
    if not refute_pairs:
        return RuleAResult(satisfied=False)
    alignment = align_key_evidence(aligner, refute_pairs, k_cap)
    if alignment.demote_to_d:
        return RuleAResult(satisfied=False, demote_to_d=True)
    origin_by_id = {doc.doc_id: doc.origin for _claim, doc in refute_pairs}
    passed_ids = [
        doc_id for _claim, doc_id, verdict in alignment.checked if verdict == "supports"
    ]
    retrieved = [i for i in passed_ids if origin_by_id[i] == "retrieved"]
    user_provided = [i for i in passed_ids if origin_by_id[i] == "user_provided"]
    if retrieved:
        cited = retrieved + (user_provided if user_evidence_optin else [])
        return RuleAResult(satisfied=True, refute_doc_ids=cited)
    if user_provided and user_evidence_optin:
        return RuleAResult(
            satisfied=True, refute_doc_ids=user_provided, used_user_evidence_only=True
        )
    if user_provided:
        return RuleAResult(satisfied=False, blocked_pending_optin=True)
    return RuleAResult(satisfied=False)


def backfill_optin(record: GenerationRecord) -> GenerationRecord:
    """user_provided 单独支撑判 A 的显式确认位回填（验收硬条款）；
    返回副本，原记录留档不动。"""
    return replace(record, user_evidence_verdict_optin=True)
