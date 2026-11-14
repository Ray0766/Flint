"""LEDGER-01：台账配对守门扩到新台账——旧守门只守 `progress.jsonl`。

## 旧守门为什么盖不住新台账

`eval/ledger_pairing.py:pairing_violations` 用 `_CARD_ID = re.compile(r"M\\d-\\d{3}\\Z")`
过滤：只有 `M1-033` / `M4-039` 这种卡号才进检查，其余一律 `continue`（那是给里程碑
生命周期记录留的口子）。而 v0.4 的卡号是 `SCHEMA-09` / `GRAPH-16`、v0.4.1 是 `ASM-01`
——**一张都匹配不上**，于是 `docs/progress-v04.jsonl` 与 `docs/progress-v041.jsonl`
整本被跳过，一条都没被守过。

## 本卡只新增覆盖面

`eval/ledger_pairing.py` 与 `tests/m4/test_ledger_pairing.py` 一字不动（工单 §3）。
规则本身**照旧复用**（`PAIRED_EVENTS`、`load_ledger`、「存在性而非位置序」），本文件
只是把同一条规则应用到卡号形态不同的两本新台账上，并为 v0.4 的历史缺行列一份显式白名单。

## 白名单是逐条对（task_id, event），不是通配

按 `(task_id, event)` 对豁免，而不是按 task_id 豁免：后者会让同一张卡将来新增的未配对
事件也跟着蒙混过关。规则本身 NEVER 放宽——只有这 67 条已发生的历史事实被点名豁免。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from eval.ledger_pairing import PAIRED_EVENTS, load_ledger, pairing_violations

REPO = Path(__file__).resolve().parents[2]
V04_LEDGER = REPO / "docs" / "progress-v04.jsonl"
V041_LEDGER = REPO / "docs" / "progress-v041.jsonl"

# v0.4 历史未配对事件（首次机械审计 @2026-08-03 采集，冻结闭集）。
# 采集命令见 docs/trace/LEDGER-01.md。NEVER 增补新条目——新的漏拍应当被抓红而非入册。
V04_LEGACY_UNPAIRED: frozenset[tuple[str, str]] = frozenset({
    ("CONCURRENCY-NOTE", "verified"),
    ("DEC-003-REMAP", "verified"),
    ("DEC-007-WEBREMAP", "verified"),
    ("DESIGN-30", "verified"),
    ("FAV-01", "verified"),
    ("FAV-03", "verified"),
    ("FAV-04", "verified"),
    ("FAV-05", "verified"),
    ("FAV-06", "verified"),
    ("GRAPH-01", "verified"),
    ("GRAPH-02", "verified"),
    ("GRAPH-03", "verified"),
    ("GRAPH-04", "verified"),
    ("GRAPH-14", "verified"),
    ("HOTSPOT-01", "verified"),
    ("HOTSPOT-02", "verified"),
    ("HOTSPOT-08", "verified"),
    ("I18N-01", "blocked"),
    ("I18N-01", "verified"),
    ("I18N-02", "blocked"),
    ("I18N-02", "verified"),
    ("I18N-03", "verified"),
    ("I18N-04", "blocked"),
    ("I18N-04", "verified"),
    ("I18N-04-a", "verified"),
    ("I18N-04-b", "verified"),
    ("I18N-05", "blocked"),
    ("I18N-05", "verified"),
    ("I18N-06", "blocked"),
    ("I18N-06", "verified"),
    ("I18N-06-a", "verified"),
    ("I18N-06-b", "verified"),
    ("I18N-07", "blocked"),
    ("I18N-07", "verified"),
    ("I18N-08", "blocked"),
    ("I18N-08", "verified"),
    ("MIGRATE-06", "verified"),
    ("MIGRATE-07", "verified"),
    ("OWNER-RULING-20260803", "verified"),
    ("REGION-01", "verified"),
    ("REGION-05", "verified"),
    ("REGION-06", "verified"),
    ("REGION-07", "verified"),
    ("REGION-08", "verified"),
    ("SCHEMA-02", "verified"),
    ("SCHEMA-03", "verified"),
    ("SCHEMA-04", "verified"),
    ("SCHEMA-05", "verified"),
    ("SCHEMA-06", "verified"),
    ("SCHEMA-07", "verified"),
    ("SCHEMA-08", "verified"),
    ("SCHEMA-09", "verified"),
    ("SCHEMA-10", "verified"),
    ("SCHEMA-11", "verified"),
    ("SCHEMA-12", "verified"),
    ("SCHEMA-13", "verified"),
    ("SCHEMA-14", "verified"),
    ("SELFCHECK-V0", "blocked"),
    ("SELFCHECK-V0", "verified"),
    ("SELFCHECK-V1", "verified"),
    ("SELFCHECK-V2", "verified"),
    ("SELFCHECK-V3", "verified"),
    ("SELFCHECK-V4", "verified"),
    ("SELFCHECK-V5", "verified"),
    ("UNBLOCK-NOTE", "verified"),
    ("V04-DONE", "verified"),
    ("V04-SEAL", "verified"),
})


def unpaired_events(
    entries: list[dict[str, object]],
) -> list[tuple[str, str]]:
    """同 `eval.ledger_pairing.pairing_violations` 的规则，但不按 `M\\d-\\d{3}` 过滤。

    复用既有 `PAIRED_EVENTS` 与「存在性而非位置序」判据（append-only 台账允许
    started 后置补录）。返回 (task_id, event) 对，稳定排序。
    """
    started = {
        str(e["task_id"]) for e in entries if e.get("event") == "started"
    }
    found: set[tuple[str, str]] = set()
    for entry in entries:
        event = str(entry.get("event"))
        task_id = str(entry.get("task_id"))
        if event in PAIRED_EVENTS and task_id not in started:
            found.add((task_id, event))
    return sorted(found)


# ── acceptance ①：新台账每个配对事件必有前置 started ────────────────────

def test_v041_ledger_has_no_unpaired_event() -> None:
    if not V041_LEDGER.exists():
        pytest.fail(f"新台账不存在：{V041_LEDGER}")
    violations = unpaired_events(load_ledger(V041_LEDGER))
    assert violations == [], (
        f"docs/progress-v041.jsonl 里有未配对事件：{violations}"
    )


def test_v041_ledger_is_well_formed_json_lines() -> None:
    from eval.ledger_append import malformed_lines

    assert malformed_lines(V041_LEDGER) == []


def test_the_v041_check_would_catch_a_fresh_gap() -> None:
    """反例：往新台账形态的数据里塞一条没有 started 的 verified —— 必须红。"""
    entries: list[dict[str, object]] = [
        {"ts": "2026-08-03T09:00:00Z", "task_id": "ASM-99", "event": "verified"},
    ]
    assert unpaired_events(entries) == [("ASM-99", "verified")]


# ── acceptance ②：v0.4 历史缺行以显式白名单豁免，规则本身不放宽 ──────────

def test_v04_legacy_gaps_match_the_frozen_whitelist_exactly() -> None:
    found = set(unpaired_events(load_ledger(V04_LEDGER)))
    unexpected = sorted(found - V04_LEGACY_UNPAIRED)
    stale = sorted(V04_LEGACY_UNPAIRED - found)
    assert unexpected == [], (
        f"v0.4 台账出现白名单之外的未配对事件（新漏拍，NEVER 增补进白名单）：{unexpected}"
    )
    assert stale == [], (
        f"白名单里有台账中已不存在的条目（清单该收紧）：{stale}"
    )


def test_the_whitelist_is_listed_in_full_not_summarised() -> None:
    """清单必须逐条列全——数量对上采集时的实测值。"""
    assert len(V04_LEGACY_UNPAIRED) == 67
    assert all(
        isinstance(t, str) and e in PAIRED_EVENTS
        for t, e in V04_LEGACY_UNPAIRED
    )


# ── acceptance ③：白名单不是通配 ───────────────────────────────────────

def test_a_new_gap_on_an_already_whitelisted_card_is_still_red() -> None:
    """同一张已在白名单里的卡，新增一个**别的**未配对事件仍然红。

    这就是按 (task_id, event) 对豁免、而不是按 task_id 豁免的理由。
    """
    entries = load_ledger(V04_LEDGER)
    entries.append({
        "ts": "2026-08-03T09:00:00Z", "task_id": "SCHEMA-09",
        "event": "review_failed", "cycles_used": 0, "note": "构造用例",
    })
    found = set(unpaired_events(entries))
    assert ("SCHEMA-09", "review_failed") in found - V04_LEGACY_UNPAIRED, (
        "白名单把同卡的新事件也放过了——那就是通配，不是白名单"
    )


def test_a_brand_new_card_gap_is_still_red() -> None:
    entries = load_ledger(V04_LEDGER)
    entries.append({
        "ts": "2026-08-03T09:00:00Z", "task_id": "BRAND-NEW-01",
        "event": "verified", "cycles_used": 0, "note": "构造用例",
    })
    found = set(unpaired_events(entries))
    assert ("BRAND-NEW-01", "verified") in found - V04_LEGACY_UNPAIRED


# ── acceptance ④：既有守门的语义一字未改，本卡只加覆盖面 ────────────────

def test_the_existing_gate_keeps_its_card_id_filter() -> None:
    """旧守门仍然只认 `M?-NNN` 卡号——本卡 NEVER 改它的语义。"""
    from eval import ledger_pairing

    assert ledger_pairing._CARD_ID.pattern == r"M\d-\d{3}\Z"
    assert PAIRED_EVENTS == frozenset(
        {"verified", "blocked", "review_passed", "review_failed"}
    )
    assert len(ledger_pairing.PRE_CONVENTION_LEGACY) == 35


def test_the_existing_gate_still_skips_new_style_card_ids() -> None:
    """证明「旧守门盖不住新台账」不是猜的：喂它一条 ASM-01 的孤儿 verified，它返回空。"""
    orphan: list[dict[str, object]] = [
        {"ts": "2026-08-03T09:00:00Z", "task_id": "ASM-01", "event": "verified"},
    ]
    assert pairing_violations(orphan) == []
    assert unpaired_events(orphan) == [("ASM-01", "verified")]


def test_the_existing_gate_still_catches_old_style_gaps() -> None:
    """反例的反例：同一条孤儿换成 M?-NNN 卡号，旧守门照旧抓得住（它没被弄坏）。"""
    orphan: list[dict[str, object]] = [
        {"ts": "2026-08-03T09:00:00Z", "task_id": "M9-001", "event": "verified"},
    ]
    assert pairing_violations(orphan) == [
        "M9-001: verified recorded but no started line in ledger"
    ]


def test_this_card_did_not_touch_the_frozen_gate_files() -> None:
    """本卡只新增覆盖面：既有守门与它的测试里都不该出现 v0.4.1 的台账路径。"""
    gate = (REPO / "eval" / "ledger_pairing.py").read_text(encoding="utf-8")
    gate_test = (
        REPO / "tests" / "m4" / "test_ledger_pairing.py"
    ).read_text(encoding="utf-8")
    for text, name in ((gate, "eval/ledger_pairing.py"),
                       (gate_test, "tests/m4/test_ledger_pairing.py")):
        assert "progress-v041" not in text, f"{name} 被改动了（出现 v0.4.1 台账路径）"
        assert not re.search(r"V04_LEGACY_UNPAIRED", text), f"{name} 被改动了"
