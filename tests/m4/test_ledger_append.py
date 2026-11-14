"""台账写守卫 + lint（收回"全绿"欠账 @2026-07-31）：只写合法单行 JSON，防再犯。"""
from __future__ import annotations

import json
from pathlib import Path

from eval.ledger_append import append_entry, malformed_lines

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "progress.jsonl"


def test_live_ledger_all_lines_legal_single_json() -> None:
    # lint 守卫：常驻台账每行都是合法单行 JSON 对象（破坏即精确红，不再等 pairing 级联报错）
    assert malformed_lines(LEDGER) == []


def test_append_entry_escapes_newlines_and_quotes(tmp_path: Path) -> None:
    f = tmp_path / "led.jsonl"
    entry = {"task_id": "T", "event": "verified",
             "note": 'has\nnewline and "quote" and \\backslash'}
    line = append_entry(f, entry)
    assert "\n" not in line and "\r" not in line       # 单行、无裸换行
    # 落盘一物理行、可 round-trip、内容保真（换行转义为 \n）
    physical = f.read_text(encoding="utf-8").splitlines()
    assert len(physical) == 1
    assert json.loads(physical[0]) == entry


def test_malformed_lines_catches_missing_brace(tmp_path: Path) -> None:
    f = tmp_path / "bad.jsonl"
    # 复现本次病灶：漏闭合 } 的手拼行
    f.write_text('{"task_id":"T","event":"verified","note":"x"\n', encoding="utf-8")
    bad = malformed_lines(f)
    assert len(bad) == 1 and "line 1" in bad[0]


def test_append_entry_then_lint_clean(tmp_path: Path) -> None:
    f = tmp_path / "ok.jsonl"
    append_entry(f, {"task_id": "A", "event": "started", "note": "多行\n与反斜杠\\"})
    append_entry(f, {"task_id": "A", "event": "verified", "note": "汉字 note"})
    assert malformed_lines(f) == []
