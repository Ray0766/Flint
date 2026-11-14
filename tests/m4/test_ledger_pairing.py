"""常驻台账成对性执法（M4-036 复审整改产物，非任务卡测试）。

Every verified/blocked/review event must have a started line somewhere in
the append-only ledger. Runs with every full pytest — the manual
checklist is retired.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eval.ledger_pairing import load_ledger, pairing_violations

pytestmark = pytest.mark.compose

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "progress.jsonl"


def test_live_ledger_fully_paired() -> None:
    violations = pairing_violations(load_ledger(LEDGER))
    assert violations == [], violations


def test_detector_catches_missing_started() -> None:
    entries = [
        {"task_id": "M9-001", "event": "started"},
        {"task_id": "M9-001", "event": "verified"},
        {"task_id": "M9-002", "event": "verified"},
        {"task_id": "M9-003", "event": "blocked"},
    ]
    violations = pairing_violations(entries)
    assert violations == [
        "M9-002: verified recorded but no started line in ledger",
        "M9-003: blocked recorded but no started line in ledger",
    ]


def test_backfill_order_tolerated() -> None:
    entries = [
        {"task_id": "M9-001", "event": "verified"},
        {"task_id": "M9-001", "event": "started"},  # BACKFILL appended later
    ]
    assert pairing_violations(entries) == [], (
        "existence not position: append-only BACKFILL precedent honored"
    )


def test_lifecycle_records_exempt_but_cards_not() -> None:
    entries = [
        {"task_id": "M9-expand", "event": "verified"},
        {"task_id": "M3-CLOSE", "event": "verified"},
        {"task_id": "M9-001", "event": "verified"},
    ]
    violations = pairing_violations(entries)
    assert violations == [
        "M9-001: verified recorded but no started line in ledger"
    ], "single-event lifecycle records exempt; real cards never"


def test_legacy_list_is_closed_pre_convention_only() -> None:
    from eval.ledger_pairing import PRE_CONVENTION_LEGACY

    assert all(t.startswith(("M1-", "M2-")) for t in PRE_CONVENTION_LEGACY), (
        "M3+ can never enter the legacy exemption"
    )
    assert len(PRE_CONVENTION_LEGACY) == 35


def test_live_ledger_ts_monotone_after_epoch() -> None:
    from eval.ledger_pairing import ts_monotonicity_violations

    violations = ts_monotonicity_violations(load_ledger(LEDGER))
    assert violations == [], violations


def test_ts_rules_scoped_to_epoch() -> None:
    from eval.ledger_pairing import ts_monotonicity_violations

    entries: list[dict[str, object]] = [
        # 锚前混乱：不回溯（既成事实已披露）
        {"task_id": "M9-001", "event": "verified", "ts": "2026-07-31T00:00:00Z"},
        {"task_id": "M9-002", "event": "verified", "ts": "2026-07-28T00:00:00Z"},
        {"task_id": "LEDGER-TS-NOTE", "event": "verified",
         "ts": "2026-07-28T16:32:00Z", "note": "epoch"},
        {"task_id": "M9-003", "event": "verified",
         "ts": "2026-07-28T16:40:00Z", "note": "x"},
        # BACKFILL 豁免（1-5 收紧后）：标记 + 机器钟补录时点双要件
        {"task_id": "M9-004", "event": "started",
         "ts": "2026-07-28T10:00:00Z", "note": "BACKFILL: window",
         "recorded_ts": "2026-07-28T16:42:00Z"},
        {"task_id": "M9-005", "event": "verified",
         "ts": "2026-07-28T16:50:00Z", "note": "y"},
    ]
    assert ts_monotonicity_violations(entries) == []

    # 锚后无标记回跳 → 违规指认
    bad = [*entries, {"task_id": "M9-006", "event": "verified",
                      "ts": "2026-07-28T16:45:00Z", "note": "z"}]
    violations = ts_monotonicity_violations(bad)
    assert len(violations) == 1 and "backjump" in violations[0]

    # 锚后非机器钟形态 → 违规指认
    malformed = [*entries, {"task_id": "M9-007", "event": "verified",
                            "ts": "07-28 17:00", "note": "w"}]
    violations = ts_monotonicity_violations(malformed)
    assert len(violations) == 1 and "UTC form" in violations[0]

    # 无锚台账：整体不适用（历史仓形态）
    assert ts_monotonicity_violations(entries[:2]) == []


def test_forward_estimate_anomaly_list_is_closed() -> None:
    """The one disclosed forward-estimated line is skipped whole (never
    poisons the chain); the list is a frozen single-entry closed set —
    new estimation misconduct must go red, never get enrolled."""
    from eval.ledger_pairing import FORWARD_ESTIMATE_ANOMALIES

    assert FORWARD_ESTIMATE_ANOMALIES == frozenset(
        {("2026-07-28T18:35:00Z", "M4-040")}
    )


def test_ts_hardening_five_injections() -> None:
    """Ruling 1-5: adversarial injections the first assertion missed."""
    from datetime import UTC, datetime

    from eval.ledger_pairing import ts_monotonicity_violations

    now = datetime(2026, 7, 28, 18, 0, 0, tzinfo=UTC)
    base: list[dict[str, object]] = [
        {"task_id": "LEDGER-TS-NOTE", "event": "verified",
         "ts": "2026-07-28T16:32:00Z", "note": "epoch"},
        {"task_id": "M9-101", "event": "verified",
         "ts": "2026-07-28T16:40:00Z", "note": "x"},
    ]

    # ① 回跳（既有覆盖，保持红线）
    backjump = [*base, {"task_id": "M9-102", "event": "verified",
                        "ts": "2026-07-28T16:35:00Z", "note": "y"}]
    assert any("backjump" in v
               for v in ts_monotonicity_violations(backjump, now=now))

    # ② 格式错（既有覆盖）
    malformed = [*base, {"task_id": "M9-103", "event": "verified",
                         "ts": "07-28 17:00", "note": "y"}]
    assert any("UTC form" in v
               for v in ts_monotonicity_violations(malformed, now=now))

    # ③ 向前伪造：2027 年 ts（原病灶本体）MUST 被上界断言抓获
    forged = [*base, {"task_id": "M9-104", "event": "verified",
                      "ts": "2027-01-01T00:00:00Z", "note": "y"}]
    violations = ts_monotonicity_violations(forged, now=now)
    assert any("future" in v for v in violations), violations

    # ④ 伪 BACKFILL 子串：无补录时点字段 → 不豁免（按普通行断言）
    fake = [*base, {"task_id": "M9-105", "event": "verified",
                    "ts": "2026-07-28T16:35:00Z",
                    "note": "not a BACKFILL really"}]
    violations = ts_monotonicity_violations(fake, now=now)
    assert any("backjump" in v for v in violations), (
        "marker without recorded_ts never exempts"
    )

    # ④b 真 BACKFILL 携机器钟补录时点且对锚非递减 → 仅豁免非递减检查
    real_backfill = [*base, {
        "task_id": "M9-106", "event": "started",
        "ts": "2026-07-28T10:00:00Z",
        "note": "BACKFILL: actual window",
        "recorded_ts": "2026-07-28T16:45:00Z",
    }]
    assert ts_monotonicity_violations(real_backfill, now=now) == []

    # ④c BACKFILL 的格式检查不豁免：ts 畸形照抓
    bad_backfill = [*base, {
        "task_id": "M9-107", "event": "started",
        "ts": "yesterday", "note": "BACKFILL: w",
        "recorded_ts": "2026-07-28T16:45:00Z",
    }]
    assert any("UTC form" in v
               for v in ts_monotonicity_violations(bad_backfill, now=now))

    # ⑤ BACKFILL 补录时点自身回跳（早于纪元锚）→ 违规
    stale_backfill = [*base, {
        "task_id": "M9-108", "event": "started",
        "ts": "2026-07-28T10:00:00Z", "note": "BACKFILL: w",
        "recorded_ts": "2026-07-28T16:00:00Z",
    }]
    violations = ts_monotonicity_violations(stale_backfill, now=now)
    assert any("recorded_ts" in v for v in violations), violations
