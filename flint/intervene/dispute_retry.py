"""dispute 冲突确认重提（M3-046，审4：dispute → 提示用户确认后重新提交）。

- 与 inject 自动重放刻意相反：dispute 是用户判断行为，底层账本变了就该
  让用户看到新状态再决定——恰一次尝试，冲突以 DisputeConfirmationRequired
  上浮（携带 current_version 供确认界面展示）。
- confirm_resubmit：用户确认后以确认版本重提（仍走乐观锁——确认到提交
  之间再变仍会再次上浮）。
"""
from __future__ import annotations

from flint.domain.models import Block, Dispute, LedgerVersionConflict
from flint.intervene.dispute import DisputeOutcome, accept_dispute
from flint.ledger.store import PgLedgerStore


class DisputeConfirmationRequired(Exception):
    def __init__(self, current_version: int) -> None:
        super().__init__(
            f"ledger moved to v{current_version}: dispute needs user "
            "confirmation before resubmit"
        )
        self.current_version = current_version


async def accept_with_confirmation(
    store: PgLedgerStore,
    project_id: str,
    dispute: Dispute,
    expected_version: int,
    blocks: list[Block],
) -> DisputeOutcome:
    try:
        return await accept_dispute(
            store, project_id, dispute, expected_version, blocks
        )
    except LedgerVersionConflict as conflict:
        raise DisputeConfirmationRequired(
            getattr(conflict, "current_version", -1)
        ) from conflict


async def confirm_resubmit(
    store: PgLedgerStore,
    project_id: str,
    dispute: Dispute,
    confirmed_version: int,
    blocks: list[Block],
) -> DisputeOutcome:
    return await accept_with_confirmation(
        store, project_id, dispute, confirmed_version, blocks
    )
