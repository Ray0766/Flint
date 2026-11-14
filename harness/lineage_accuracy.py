"""BL-10：血缘准确率度量器（S4 出口断言 ≥90%、50 簇的那把尺子）。**恒 report_only**。

用法：
  python harness/lineage_accuracy.py --labels assets/labels.yaml --offline
  python harness/lineage_accuracy.py --labels assets/labels.yaml --dsn postgresql://…

## 与既有 `eval/lineage.py` 的分工

那一把（M1-039）是**门**：低于 `--min` 退 1，夜间定时评测据此标红。
本模块是**尺**：只报数、**恒 report_only**，因为 S4 的出口线本身仍是未决项
（「血缘准确率线 ≥90%（50 簇）」列在 CLAUDE.md#S4 的 Open Questions 里）。

度量器一旦会判，它就变成了门；而这条线还没定，先建门等于替 owner 定了。

## 口径：什么算一次正确的血缘

- 一次「正确」= 该簇的 **(day, kind) 全序列逐项相等**（**顺序**敏感）；
- **全或无**：少一个事件、多一个事件、顺序不同，这一簇都算错。
  按事件计分会让「漏了一次 split」看起来只丢一点点——而血缘是一条时间线，
  错一处后面全错位；
- 标注里有、实际里**找不到**的簇：计入**分母**、不计分子（跳过它分母就变小，
  准确率虚高，而「压根没产出这个簇」是最严重的一种错）；
- 实际里有、标注里没有的簇：不进准确率，但**报出条数**——它可能说明标注集不全。

比较一律按字符串：`day` 用 ISO 文本、`kind` 逐字。数值化或按日期对象比较会
在时区与格式上引入第二套口径。

## 样本量：不足 50 簇不判定

S4 写的是「≥90%（**50 簇**）」。样本不足时报「样本 N 不足 50，不判定」——
但**数字照给**：不给的话人会自己去算一个，而那个算法没人看得见。

「够样本量」与「达线」是**两件事**，分开报，NEVER 混成一个「通过」。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# S4 出口断言：血缘准确率 ≥90%，50 簇。两个数都来自 CLAUDE.md#S4 的 Open Question 行。
MIN_GOLD_CLUSTERS: Final[int] = 50
EXIT_LINE: Final[float] = 0.90

Timeline = list[tuple[str, str]]


@dataclass(frozen=True)
class ClusterLabel:
    """一簇的人工标注（真值）。`expected` 是 (day, kind) 序列，顺序有意义。"""

    cluster_key: str
    expected: tuple[tuple[str, str], ...]


@dataclass
class AccuracyReport:
    total: int = 0
    matched: int = 0
    unlabelled: int = 0
    mismatches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.matched / self.total if self.total else 0.0

    @property
    def judgeable(self) -> bool:
        """样本量够不够拿这个数当出口判定。**与「达线」是两件事**。"""
        return self.total >= MIN_GOLD_CLUSTERS

    @property
    def meets_line(self) -> bool:
        """达没达到 S4 那条线。judgeable=False 时这只是个参考值。"""
        return self.accuracy >= EXIT_LINE

    @property
    def note(self) -> str:
        if not self.judgeable:
            return (
                f"样本 {self.total} 不足 {MIN_GOLD_CLUSTERS}，**不判定**"
                f"（数字照给，但 NEVER 拿它当出口判定）"
            )
        verdict = "已达线" if self.meets_line else "未达线"
        return f"样本 {self.total} 够 {MIN_GOLD_CLUSTERS}；{verdict}（参考，判定归 owner）"


def measure(
    labels: list[ClusterLabel], actual_by_key: dict[str, Timeline]
) -> AccuracyReport:
    """算准确率。口径见模块 docstring——**全或无**、顺序敏感、缺簇计入分母。"""
    report = AccuracyReport()
    labelled_keys = {label.cluster_key for label in labels}
    for label in labels:
        report.total += 1
        actual = actual_by_key.get(label.cluster_key, [])
        if [tuple(item) for item in actual] == list(label.expected):
            report.matched += 1
        else:
            report.mismatches.append({
                "cluster_key": label.cluster_key,
                "expected": [list(e) for e in label.expected],
                "actual": [list(a) for a in actual],
            })
    report.unlabelled = len([k for k in actual_by_key if k not in labelled_keys])
    return report


def render(report: AccuracyReport) -> str:
    """给人看的一屏。`report_only` 那句话**成句**写出来。"""
    headline = (
        f"血缘准确率 {report.matched}/{report.total} = {report.accuracy:.2%}"
        "   （**report_only**：本度量器 NEVER 判定，S4 的线仍是未决项）"
    )
    lines = [headline, f"  {report.note}"]
    if report.unlabelled:
        lines.append(
            f"  实际里有、标注里没有的簇：{report.unlabelled} 个"
            "（不进准确率；它可能说明标注集不全）"
        )
    for miss in report.mismatches[:5]:
        lines.append(
            f"  ✗ {miss['cluster_key']}：标注 {miss['expected']} / 实际 {miss['actual']}"
        )
    if len(report.mismatches) > 5:
        lines.append(f"  …… 另有 {len(report.mismatches) - 5} 簇失配")
    return "\n".join(lines)


def load_labels(path: Path) -> list[ClusterLabel]:
    """读 `assets/labels.yaml`（生成器直出真值，owner 指令 @2026-07-27）。"""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        ClusterLabel(
            cluster_key=str(entry["keyword_id"]),
            expected=tuple(
                (str(event["day"]), str(event["kind"])) for event in entry["expected"]
            ),
        )
        for entry in payload["clusters"]
    ]


async def actual_from_db(dsn: str, labels: list[ClusterLabel]) -> dict[str, Timeline]:
    """从 `lineage_audit` 取实际时间线（定位口径同 `eval/lineage.py`）。"""
    import asyncpg

    out: dict[str, Timeline] = {}
    conn = await asyncpg.connect(dsn)
    try:
        for label in labels:
            row = await conn.fetchrow(
                "SELECT cluster_id FROM lineage_audit WHERE role = 'subject' "
                "AND event_kind = 'new' AND event::text LIKE '%' || $1 || '%' "
                "ORDER BY day LIMIT 1",
                label.cluster_key,
            )
            if row is None:
                continue                      # 缺簇不补空行：measure 会计入分母
            rows = await conn.fetch(
                "SELECT day, event_kind, event FROM lineage_audit "
                "WHERE cluster_id = $1 AND role = 'subject' ORDER BY day, event_index",
                row["cluster_id"],
            )
            timeline: Timeline = []
            for r in rows:
                if r["event_kind"] == "new":
                    payload = json.loads(r["event"])
                    if label.cluster_key not in payload.get("keyword_ids", []):
                        continue
                timeline.append((r["day"].isoformat(), str(r["event_kind"])))
            out[label.cluster_key] = timeline
    finally:
        await conn.close()
    return out


def main(argv: list[str]) -> int:
    """**恒返回 0**——本度量器只报数。判定归 owner（S4 未决项）。"""
    parser = argparse.ArgumentParser(description="血缘准确率度量（report_only）")
    parser.add_argument("--labels", required=True)
    parser.add_argument("--dsn", default=None)
    parser.add_argument(
        "--offline", action="store_true",
        help="不连库：实际时间线视为空（用于口径自检与样本量清点）",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    labels = load_labels(Path(args.labels))
    if args.offline or not args.dsn:
        actual: dict[str, Timeline] = {}
    else:
        actual = asyncio.run(actual_from_db(args.dsn, labels))

    report = measure(labels, actual)
    if args.as_json:
        print(json.dumps({
            "schema": "lineage-accuracy/1",
            "total": report.total, "matched": report.matched,
            "accuracy": report.accuracy, "judgeable": report.judgeable,
            "meets_line": report.meets_line, "note": report.note,
            "unlabelled": report.unlabelled, "mismatches": report.mismatches,
            "report_only": True,
        }, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
