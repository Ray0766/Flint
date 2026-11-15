"""NARROW-05 · the ledger turns red when a frozen item gets a card after `DEC-066`.

`CLAUDE.md` S1: "NEVER 为冻结项开新卡或续做旧卡". `DEC-067` kept batch runs going,
and the only thing keeping them off frozen items was that one sentence: no check
went red if a worker started a card on one. This one does.

## What counts

Any `started` event in `docs/progress-v041.jsonl` after the freeze took effect, for a
card that belongs to a frozen item. "After" is measured from the ledger itself: the
`started` event of `NARROW-01`, the card that landed `DEC-066`. The `REDESIGN-05`
contrast sweep that morning was still allowed.

A card belongs to a frozen item when either

1. its id carries a prefix the ledger has used for that item (the table below, read
   off the existing ledger by me; it is my reading, not an owner ruling), or
2. its `started` note names the item outright (a new prefix for an old item).

`EXEMPT` lists cards that name a frozen item in their note because they work *on* the
freeze (closing entries, cleaning text), each with its reason. Adding a card there is a
visible act in a diff, which is the point.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "docs" / "progress-v041.jsonl"
FREEZE_CARD = "NARROW-01"

#: freeze item (as `CLAUDE.md` S1 words it) -> card prefixes the ledger used for it
PREFIXES: dict[str, tuple[str, ...]] = {
    "九个地区与英文界面": ("REGION", "REGION-CN", "LOC", "LOCALE", "I18N"),
    "支付与计费": ("PAY", "BILLING"),
    "分享": ("SHARE",),
    "收藏": ("FAV", "FAV-CARD"),
    "图谱工作台": ("GRAPH", "EDGES"),
    "设计工作台": ("DESIGN",),
    "五套人类模板": ("WB", "TPL"),
    "UI 细化": ("UI", "UIR", "UIX", "REDESIGN", "DARK", "PAL", "NAV", "NAV-ANIME",
                "SHELL", "WIDTH", "TITLE", "DS"),
    "微博与 Google 趋势两个源": ("WEIBO", "GTRENDS"),
}

#: words that name a frozen item in a `started` note
NAMES: dict[str, tuple[str, ...]] = {
    "九个地区与英文界面": ("九个地区", "英文界面"),
    "支付与计费": ("支付", "计费"),
    "分享": ("分享",),
    "收藏": ("收藏",),
    "图谱工作台": ("图谱工作台",),
    "设计工作台": ("设计工作台", "模板工具"),
    "五套人类模板": ("人类模板",),
    "UI 细化": ("UI 细化",),
    "微博与 Google 趋势两个源": ("微博", "Google 趋势", "weibo", "gtrends"),
}

#: cards that name a frozen item because they work on the freeze itself
EXEMPT: dict[str, str] = {
    "NARROW-05": "closes the frozen items' entry points (DEC-066 asked for it)",
}


def _rows(lines: Iterable[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in lines if line.strip()]


def _ledger() -> list[dict[str, Any]]:
    return _rows(LEDGER.read_text(encoding="utf-8-sig").splitlines())


def _item_of(row: dict[str, Any]) -> str | None:
    card = str(row["task_id"])
    for item, prefixes in PREFIXES.items():
        if any(card == p or card.startswith(p + "-") for p in prefixes):
            return item
    if card in EXEMPT:
        return None
    note = str(row.get("note", ""))
    for item, words in NAMES.items():
        if any(w in note for w in words):
            return item
    return None


def frozen_starts(rows: list[dict[str, Any]]) -> list[str]:
    """`card (item) @ ts` for every frozen-item start after the freeze card started."""
    cutoff = next(r["ts"] for r in rows
                  if r["task_id"] == FREEZE_CARD and r["event"] == "started")
    hits = []
    for row in rows:
        if row["event"] != "started" or row["ts"] <= cutoff:
            continue
        item = _item_of(row)
        if item is not None:
            hits.append(f"{row['task_id']} ({item}) @ {row['ts']}")
    return hits


def test_no_frozen_item_has_been_started_since_the_freeze() -> None:
    hits = frozen_starts(_ledger())
    assert hits == [], (
        f"a frozen item got a card after DEC-066: {hits}. "
        "Unfreezing takes a new owner ruling (CLAUDE.md S1); see the DEC-067 tripwire "
        "in docs/trace/NARROW-01.md section 6 for how to stop batch runs."
    )


def test_the_check_catches_a_frozen_card_by_prefix_and_by_name() -> None:
    """Control: feed it the real ledger plus three made-up starts, it names two."""
    rows = _ledger()
    after = "2099-01-01T00:00:00+00:00"
    rows += [
        {"ts": after, "task_id": "FAV-CARD-09", "event": "started", "note": "x"},
        {"ts": after, "task_id": "SHIP-99", "event": "started",
         "note": "接上 Google 趋势港区那一源"},
        {"ts": after, "task_id": "CHAIN-99", "event": "started", "note": "热点到判定"},
    ]
    hits = frozen_starts(rows)
    assert [h.split(" ")[0] for h in hits] == ["FAV-CARD-09", "SHIP-99"], hits


def test_a_frozen_card_started_before_the_freeze_is_not_counted() -> None:
    """REDESIGN-05 (UI 细化) started the morning DEC-066 landed, before it."""
    rows = _ledger()
    assert any(r["task_id"] == "REDESIGN-05" and r["event"] == "started" for r in rows)
    assert not [h for h in frozen_starts(rows) if h.startswith("REDESIGN")]


def test_every_freeze_item_in_the_charter_has_a_row_here() -> None:
    charter = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    block = charter.split("**冻结清单**", 1)[1].split("**本包自身范围**", 1)[0]
    items = [line[2:].split("（", 1)[0].strip()
             for line in block.splitlines() if line.startswith("- ")]
    assert items == list(PREFIXES), items
    assert list(NAMES) == list(PREFIXES)
