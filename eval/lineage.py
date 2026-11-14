"""血缘准确率评测（M1-039，PDD v0.3.1 §7：M1 出口断言 >=90%）。

- 对照 assets/labels.yaml（生成器直出真值，owner 指令）与 30 天回放库的
  lineage_audit 实际时间线：按 keyword_id 定位簇（new 事件成员），逐簇
  比对 (day, kind) 全序列，簇级全对才计 matched。
- 输出准确率报告（总体 + 分 kind 事件计数 + 失配样本）；低于 --min 退出码 1
  ——夜间定时评测（E9）以退出码标红。
用法：python -m eval.lineage --labels assets/labels.yaml --min 0.90
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import asyncpg
import yaml


@dataclass
class EvalReport:
    total: int = 0
    matched: int = 0
    kind_counts: Counter[str] = field(default_factory=Counter)
    mismatches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.matched / self.total if self.total else 0.0

    def render(self) -> str:
        lines = [
            f"lineage accuracy: {self.matched}/{self.total} = {self.accuracy:.2%}",
            "expected events by kind: "
            + ", ".join(f"{k}={v}" for k, v in sorted(self.kind_counts.items())),
        ]
        for miss in self.mismatches[:5]:
            lines.append(
                f"MISMATCH {miss['canonical']}: expected {miss['expected']} "
                f"got {miss['actual']}"
            )
        if len(self.mismatches) > 5:
            lines.append(f"... and {len(self.mismatches) - 5} more mismatches")
        return "\n".join(lines)


async def _actual_timeline(
    conn: asyncpg.Connection, keyword_id: str
) -> list[tuple[str, str]]:
    row = await conn.fetchrow(
        "SELECT cluster_id FROM lineage_audit WHERE role = 'subject' "
        "AND event_kind = 'new' AND event::text LIKE '%' || $1 || '%' "
        "ORDER BY day LIMIT 1",
        keyword_id,
    )
    if row is None:
        return []
    rows = await conn.fetch(
        "SELECT day, event_kind, event FROM lineage_audit "
        "WHERE cluster_id = $1 AND role = 'subject' ORDER BY day, event_index",
        row["cluster_id"],
    )
    timeline: list[tuple[str, str]] = []
    for r in rows:
        if r["event_kind"] == "new":
            payload = json.loads(r["event"])
            if keyword_id not in payload.get("keyword_ids", []):
                continue
        timeline.append((r["day"].isoformat(), r["event_kind"]))
    return timeline


async def evaluate(dsn: str, labels_path: Path) -> EvalReport:
    payload = yaml.safe_load(labels_path.read_text(encoding="utf-8"))
    report = EvalReport()
    conn = await asyncpg.connect(dsn)
    try:
        for entry in payload["clusters"]:
            expected = [(e["day"], e["kind"]) for e in entry["expected"]]
            for _, kind in expected:
                report.kind_counts[kind] += 1
            actual = await _actual_timeline(conn, entry["keyword_id"])
            report.total += 1
            if actual == expected:
                report.matched += 1
            else:
                report.mismatches.append(
                    {
                        "canonical": entry["canonical"],
                        "expected": expected,
                        "actual": actual,
                    }
                )
    finally:
        await conn.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="flint lineage accuracy eval")
    parser.add_argument("--labels", required=True)
    parser.add_argument("--min", type=float, default=0.90)
    # CLI 默认打 demo 库（人手动评血缘就是冲 demo 数据去的）；env 优先。
    # 测试从不吃这个 default：tests/m1/test_m1_039.py 显式传 --dsn。
    parser.add_argument(
        "--dsn", default=os.environ.get(
            "FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")
    )
    args = parser.parse_args(argv)
    report = asyncio.run(evaluate(args.dsn, Path(args.labels)))
    print(report.render())
    if report.accuracy < args.min:
        print(f"RED: accuracy below required minimum {args.min:.2%}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
