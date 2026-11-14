"""金标集采集脚手架（GOLD-01）：为 θ_rel / δ / hotness 标定备料。

## 只采集，不调参

θ_rel（初值 0.6）、δ（0.965）、hotness 权重都是 `CLAUDE.md#S4` 的 Open Question——
调参是 owner 决策，NEVER 由采集脚本代劳。所以本模块**不含任何阈值常量、不做任何判定**：
它把一次真跑的证据/判定原样摊成可人工标注的条目，标注结果留空槽等人填。

一旦这里内置了阈值，标注出来的金标就带着当前阈值的偏见——用它去调那个阈值，等于拿
答案去验算答案。

## 可复现

同一输入两次导出**逐字节一致**：条目 id 由内容哈希定；时间戳取**数据自身的** UTC
（快照落库时刻），NEVER 取导出时的 `now()`；序列化固定 `sort_keys=True` +
`ensure_ascii=False` + `\n` 行尾。

## 采什么

一次 Gate① 真跑在库里留三份快照（`flint/jobs/gate1.py`）：

| 快照 id | 内容 | 采成什么条目 |
|---|---|---|
| `snap-{job}-docs` | 检索到的 Doc 元信息 | `evidence` 条（待标：这篇证据与主题相关吗） |
| `snap-{job}-judge` | 判官产出的 support_claims | `claim` 条（待标：这条断言被证据支持吗） |
| `snap-{job}-verdict` | 四分类判定 | `verdict` 条（待标：这个判定对吗） |

标注槽 `label` 恒为 `None`、`note` 恒为空串——**留白由人填**，脚本不预填任何猜测。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import asyncpg

SNAPSHOT_KINDS: tuple[tuple[str, str], ...] = (
    ("docs", "evidence"),
    ("judge", "claim"),
    ("verdict", "verdict"),
)


@dataclass(frozen=True)
class GoldEntry:
    """一条待人工标注的金标条目。`label`/`note` 是留白，采集侧 NEVER 预填。"""

    entry_id: str
    job_id: str
    kind: str
    source_snapshot_id: str
    source_ts: str          # 数据自身的 UTC 落库时刻，NEVER 导出时的 now()
    payload: Any
    label: None
    note: str


def _canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _entry_id(job_id: str, kind: str, index: int, payload: Any) -> str:
    digest = hashlib.sha256(
        f"{job_id}|{kind}|{index}|{_canonical(payload)}".encode()
    ).hexdigest()
    return f"gold-{digest[:16]}"


def _utc_text(moment: Any) -> str:
    """落库时刻 → `YYYY-MM-DDTHH:MM:SSZ`（与台账同形）。"""
    from datetime import UTC, datetime

    stamp: datetime = moment
    return stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _split_payload(kind: str, payload: Any) -> list[Any]:
    """把一份快照摊成逐条可标注的单元。摊不开的（判定本身）就是一条。"""
    if kind == "evidence" and isinstance(payload, dict):
        docs = payload.get("docs")
        if isinstance(docs, list):
            return docs
    if kind == "claim" and isinstance(payload, dict):
        claims = payload.get("support_claims")
        if isinstance(claims, list):
            return claims
    return [payload]


async def collect_gold_entries(dsn: str, job_id: str) -> list[GoldEntry]:
    """把一次真跑的证据/判定采成金标条目。缺快照的种类跳过（那一步没跑到）。"""
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT snapshot_id, payload, created_at FROM snapshots "
            "WHERE snapshot_id = ANY($1::text[]) ORDER BY snapshot_id",
            [f"snap-{job_id}-{suffix}" for suffix, _kind in SNAPSHOT_KINDS],
        )
    finally:
        await conn.close()
    by_id = {r["snapshot_id"]: r for r in rows}

    entries: list[GoldEntry] = []
    for suffix, kind in SNAPSHOT_KINDS:            # 固定序：可复现的前提
        snapshot_id = f"snap-{job_id}-{suffix}"
        row = by_id.get(snapshot_id)
        if row is None:
            continue
        payload = json.loads(bytes(row["payload"]).decode("utf-8"))
        source_ts = _utc_text(row["created_at"])
        for index, unit in enumerate(_split_payload(kind, payload)):
            entries.append(GoldEntry(
                entry_id=_entry_id(job_id, kind, index, unit),
                job_id=job_id, kind=kind, source_snapshot_id=snapshot_id,
                source_ts=source_ts, payload=unit, label=None, note="",
            ))
    return entries


def to_jsonl(entries: list[GoldEntry]) -> str:
    """确定性序列化：固定键序、固定编码、固定行尾。两次导出逐字节一致。"""
    return "".join(
        json.dumps(asdict(e), ensure_ascii=False, sort_keys=True) + "\n"
        for e in entries
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="flint 金标集采集（只采不判）")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    entries = asyncio.run(collect_gold_entries(args.dsn, args.job_id))
    Path(args.out).write_text(to_jsonl(entries), encoding="utf-8")


if __name__ == "__main__":
    main()
