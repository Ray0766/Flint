"""BL-05：热点参数 A/B 跑批器（**恒 report_only**）。

用法：
  python harness/tune_hotness.py --gold <gold.jsonl> --today 2026-07-20 \
      --left <a.json> --right <b.json>

## 它做什么、不做什么

**做**：同一批数据、两组参数各排一次序，把「谁动了、动到哪」摆出来。
**不做**：写回任何默认值、写任何配置文件、改任何环境变量。

调参是 owner 决策（S4 未决项：θ_rel / δ / G / α β γ ν …）。
一个能顺手写回的跑批器，迟早会有人「跑完顺便存一下」——**那一刻未决项就被
执行侧定了**，而 owner 连看都没看过对照表。所以这里连写文件的能力都不给。

## 未标定要一路带到报告上

`TuningProfile` 自带来源标注，本模块把它原样抄进 `note`。
两组里只要有一组未标定，整张对照表就是 report_only ——
半标定的对照表比没有更危险：它看起来像结论。

## 吃不下的金标条目**报出来**

`series_from_gold` 遇到没有热度序列的条目直接抛并点名 `entry_id`。
悄悄跳过的话，「拿 50 条金标跑的」可能实际只跑了 3 条，而对照表上看不出来。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flint.config import TuningProfile, load_tuning, tuning_note
from flint.hotness import ClusterSeries, compute_hotness, rank_hotness


def series_from_gold(path: Path) -> list[ClusterSeries]:
    """读 `harness/gold_collect.py` 导出的 jsonl，取出带热度序列的条目。

    吃不下的**抛并点名**：悄悄跳过会让「拿 N 条金标跑的」变成一句假话。
    """
    out: list[ClusterSeries] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry: dict[str, Any] = json.loads(line)
        payload = entry.get("payload") or {}
        missing = [
            k for k in ("cluster_id", "first_seen", "agg_by_day", "by_source_today")
            if k not in payload
        ]
        if missing:
            raise ValueError(
                f"金标条目 {entry.get('entry_id')!r} 缺 {missing}，喂不进热度算式。"
                "NEVER 悄悄跳过——跳过之后对照表上看不出少跑了多少条。"
            )
        out.append(
            ClusterSeries(
                cluster_id=str(payload["cluster_id"]),
                first_seen=date.fromisoformat(str(payload["first_seen"])),
                agg_by_day={
                    date.fromisoformat(d): float(v)
                    for d, v in dict(payload["agg_by_day"]).items()
                },
                by_source_today={
                    str(s): float(v) for s, v in dict(payload["by_source_today"]).items()
                },
            )
        )
    return out


def _side(series: list[ClusterSeries], today: date, profile: TuningProfile) -> dict[str, Any]:
    ranked = rank_hotness(series, today, profile.hotness)
    return {
        "ranking": [s.cluster_id for s in ranked],
        "scores": {
            s.cluster_id: round(compute_hotness(s, today, profile.hotness).total, 6)
            for s in series
        },
        "note": tuning_note(profile),
        "calibrated": profile.calibrated,
    }


def ab_compare(
    series: list[ClusterSeries],
    today: date,
    *,
    left: TuningProfile,
    right: TuningProfile,
) -> dict[str, Any]:
    """同一批数据两组参数各排一次序。`moved` = 名次变了的簇。

    `moved` 为空是**有信息的**：它说明这两组参数在这批数据上分不出差别，
    而那本身就是一条结论（别在这个旋钮上继续花时间）。
    """
    left_side, right_side = _side(series, today, left), _side(series, today, right)
    left_rank = {cid: i for i, cid in enumerate(left_side["ranking"])}
    right_rank = {cid: i for i, cid in enumerate(right_side["ranking"])}
    moved = sorted(cid for cid in left_rank if left_rank[cid] != right_rank[cid])
    return {
        "schema": "tune-hotness/1",
        "clusters": len(series),
        "today": today.isoformat(),
        "left": left_side,
        "right": right_side,
        "moved": moved,
        # 恒 True：本跑批器 NEVER 写回任何默认值（S4 未决项属 owner）
        "report_only": True,
    }


def format_table(report: dict[str, Any]) -> str:
    """给人看的一屏。两侧的来源标注**都**印出来，包括「未标定」那句。"""
    lines = [
        f"A/B 对照（{report['clusters']} 簇，today={report['today']}）  report_only",
        f"  左：{report['left']['note']}",
        f"  右：{report['right']['note']}",
        "",
        f"  {'cluster_id':<24}{'左名次':>8}{'右名次':>8}{'左分':>12}{'右分':>12}",
    ]
    left_rank = {cid: i + 1 for i, cid in enumerate(report["left"]["ranking"])}
    right_rank = {cid: i + 1 for i, cid in enumerate(report["right"]["ranking"])}
    for cid in report["left"]["ranking"]:
        lines.append(
            f"  {cid:<24}{left_rank[cid]:>8}{right_rank[cid]:>8}"
            f"{report['left']['scores'][cid]:>12.4f}{report['right']['scores'][cid]:>12.4f}"
        )
    lines.append("")
    lines.append(
        f"  名次有变化的：{report['moved'] or '（无——这两组参数在这批数据上分不出差别）'}"
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="热点参数 A/B 跑批（report_only）")
    parser.add_argument("--gold", required=True, help="gold_collect 导出的 jsonl")
    parser.add_argument("--today", required=True, help="YYYY-MM-DD")
    parser.add_argument("--left", default=None, help="左侧参数 json（省略=初值/未标定）")
    parser.add_argument("--right", default=None, help="右侧参数 json（省略=初值/未标定）")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    series = series_from_gold(Path(args.gold))
    report = ab_compare(
        series,
        date.fromisoformat(args.today),
        left=load_tuning(Path(args.left) if args.left else None),
        right=load_tuning(Path(args.right) if args.right else None),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.as_json
          else format_table(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
