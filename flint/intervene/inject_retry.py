"""inject 冲突自动重放（M3-044，审4：inject_evidence → 自动重放 ≤3）。

- 撞 LedgerVersionConflict → 以冲突携带的 current_version 为新基线重放，
  上限 3 次；第 4 次冲突不再盲试，原样上抛（S2 纪律同构）。
- 幂等面：inject 的 fact_id 由证据内容确定（M3-043），同证据重放在新版本
  上语义等效。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import LedgerVersionConflict, UserEvidence
from flint.intervene.inject import InjectionResult, inject_evidence
from flint.ledger.store import PgLedgerStore
from flint.scoring.scorer import DualScaleScorer

MAX_REPLAYS: Final[int] = 3


@dataclass
class ReplayedInjection:
    result: InjectionResult
    attempts: int


async def inject_with_replay(
    store: PgLedgerStore,
    project_id: str,
    ev: UserEvidence,
    scorer: DualScaleScorer,
    aligner: LLMCitationAligner,
    claim_text: str,
    initial_expected_version: int,
    user_evidence_optin: bool = False,
) -> ReplayedInjection:
    expected = initial_expected_version
    attempts = 0
    while True:
        attempts += 1
        try:
            result = await inject_evidence(
                store=store, project_id=project_id, ev=ev, scorer=scorer,
                aligner=aligner, claim_text=claim_text,
                expected_version=expected,
                user_evidence_optin=user_evidence_optin,
            )
        except LedgerVersionConflict as conflict:
            if attempts > MAX_REPLAYS:
                raise
            expected = getattr(conflict, "current_version", expected)
            continue
        return ReplayedInjection(result=result, attempts=attempts)
