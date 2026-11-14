"""台账写守卫（收回"全绿"欠账 @2026-07-31）：只写合法单行 JSON。

累犯根因：手搓 bash JSON 漏闭合 `}` / note 裸换行未转义 → `docs/progress.jsonl` 破坏
"一行一个 JSON"、pairing 红。守卫：**一切追加走 `append_entry`（json.dumps）**，NEVER 手拼
——json.dumps 必产合法单行（裸换行/反斜杠/引号全转义、括号必闭）。`malformed_lines` 是 lint
（pairing 测跑，破坏即精确红）。
"""
from __future__ import annotations

import json
from pathlib import Path


def append_entry(path: str | Path, entry: dict[str, object]) -> str:
    """把一条台账追加为合法单行 JSON（json.dumps 保证转义+闭合）。返回写入的行。

    追加用 'a'/utf-8（不新增 BOM；文件首行 BOM 保留）。断言序列化无裸换行（json.dumps
    本就不产，双保险）。
    """
    line = json.dumps(entry, ensure_ascii=False)
    if "\n" in line or "\r" in line:                     # json.dumps 不会到这，双保险
        raise ValueError("serialized ledger line contains a raw newline")
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def malformed_lines(path: str | Path) -> list[str]:
    """lint：返回不是合法单行 JSON 的行（行号 + 前 60 字）；空 = 全合法。"""
    text = Path(path).read_text(encoding="utf-8-sig")
    bad: list[str] = []
    for i, ln in enumerate(text.splitlines(), 1):
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError as err:
            bad.append(f"line {i}: not single-line JSON ({err}) :: {ln[:60]}")
            continue
        if not isinstance(obj, dict):
            bad.append(f"line {i}: top-level not an object :: {ln[:60]}")
    return bad
