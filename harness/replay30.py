"""30 天离线回放 harness（M1-037，技术方案 E12：make dev-replay DAYS=30）。

- 逐日调用 daily_ingest 全链（采集→聚类→热度→卡片），全程 fixtures 回放
  零联网（S2-7）；job_id = replay-{day}，断点续跑语义与生产一致。
- 每日产出 trace（docs/trace/replay30/{day}.md）：inputs 来源清单（fixture
  文件 + 交换数）+ 断点日志（步骤清单 + 末位 checkpoint 内容）+ 降级备注
  + 产出计数 + 终态。
- 出口：全部 job done = all_green；任一非 done → 进程退出码 1。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import asyncpg

from flint.jobs.ingest import IngestReport, build_replay_deps, run_daily_ingest


@dataclass
class DaySummary:
    day: date
    job_state: str
    steps_run: list[str]
    notes: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ReplaySummary:
    days: list[DaySummary] = field(default_factory=list)

    @property
    def all_green(self) -> bool:
        return bool(self.days) and all(d.job_state == "done" for d in self.days)


async def _day_facts(dsn: str, day: date, job_id: str) -> dict[str, object]:
    conn = await asyncpg.connect(dsn)
    try:
        state: str = await conn.fetchval(
            "SELECT state FROM jobs WHERE job_id = $1", job_id
        )
        steps = await conn.fetch(
            "SELECT name, state, snapshot_ref FROM job_steps WHERE job_id = $1 "
            "ORDER BY step_index",
            job_id,
        )
        counts = {
            "raw_items": await conn.fetchval(
                "SELECT count(*) FROM trend_items_raw WHERE day = $1", day
            ),
            "keywords_total": await conn.fetchval("SELECT count(*) FROM keywords"),
            "clusters_total": await conn.fetchval("SELECT count(*) FROM clusters"),
            "heat_points_day": await conn.fetchval(
                "SELECT count(*) FROM heat_points WHERE day = $1", day
            ),
            "cards_total": await conn.fetchval("SELECT count(*) FROM evidence_cards"),
        }
        return {"state": state, "steps": [dict(s) for s in steps], "counts": counts}
    finally:
        await conn.close()


def _inputs_manifest(fixtures_root: Path, day: date) -> list[str]:
    lines: list[str] = []
    for source_id in ("arxiv", "ghtrend", "gtrends", "weibo"):
        path = fixtures_root / source_id / f"{day.isoformat()}.json"
        if path.exists():
            exchanges = json.loads(path.read_text(encoding="utf-8"))
            rel = path.relative_to(fixtures_root.parent).as_posix()
            lines.append(f"- {rel}（{len(exchanges)} exchange, status {exchanges[0]['status_code']}）")
        else:
            lines.append(f"- fixtures/{source_id}/{day.isoformat()}.json（缺失）")
    return lines


def _write_trace(
    trace_dir: Path,
    fixtures_root: Path,
    day: date,
    report: IngestReport,
    facts: dict[str, object],
) -> None:
    steps = facts["steps"]
    counts = facts["counts"]
    assert isinstance(steps, list) and isinstance(counts, dict)
    last_checkpoint = steps[-1]["snapshot_ref"] if steps else "(no steps)"
    lines = [
        f"# replay trace {day.isoformat()}",
        "",
        "## inputs 来源清单",
        *_inputs_manifest(fixtures_root, day),
        "",
        "## 步骤与断点日志",
        f"- 本次执行步骤：{report.steps_run or '（无：job 已完成，跳过）'}",
        "- job_steps 全量：",
        *[f"  - {s['name']}: {s['state']}" for s in steps],
        f"- 末位 checkpoint：{last_checkpoint}",
        "",
        "## 降级备注",
        *(
            [f"- {n.source_id}: {n.reason}（{n.detail[:80]}）" for n in report.degradation_notes]
            or ["- 无"]
        ),
        "",
        "## 产出计数",
        *[f"- {k}: {v}" for k, v in counts.items()],
        "",
        f"## 终态：job replay-{day.isoformat()} state={facts['state']}",
        "",
    ]
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / f"{day.isoformat()}.md").write_text(
        "\n".join(lines), encoding="utf-8", newline="\n")


def run_replay(
    days: int,
    end: date,
    dsn: str,
    fixtures_root: Path,
    trace_dir: Path,
) -> ReplaySummary:
    summary = ReplaySummary()
    shared_embedder = None
    for offset in range(days - 1, -1, -1):
        day = end - timedelta(days=offset)
        deps = build_replay_deps(dsn=dsn, fixtures_root=fixtures_root, day=day)
        if shared_embedder is None:
            shared_embedder = deps.embedder  # 跨日共享内容 hash 缓存
        else:
            deps.embedder = shared_embedder
        job_id = f"replay-{day.isoformat()}"
        report = asyncio.run(run_daily_ingest(job_id=job_id, day=day, deps=deps))
        facts = asyncio.run(_day_facts(dsn, day, job_id))
        _write_trace(trace_dir, fixtures_root, day, report, facts)
        summary.days.append(
            DaySummary(
                day=day,
                job_state=str(facts["state"]),
                steps_run=report.steps_run,
                notes=[(n.source_id, n.reason) for n in report.degradation_notes],
            )
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="flint 30-day offline replay")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--end", default="2026-07-23")
    # 同 drill7：CLI 默认 demo 库、env 优先；测试走 run_replay(dsn=...) 必填参数。
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint"),
    )
    parser.add_argument("--fixtures-root", default=str(Path(__file__).resolve().parents[1] / "fixtures"))
    parser.add_argument(
        "--trace-dir",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "trace" / "replay30"),
    )
    args = parser.parse_args(argv)
    summary = run_replay(
        days=args.days,
        end=date.fromisoformat(args.end),
        dsn=args.dsn,
        fixtures_root=Path(args.fixtures_root),
        trace_dir=Path(args.trace_dir),
    )
    green = sum(1 for d in summary.days if d.job_state == "done")
    print(f"replay30: {green}/{len(summary.days)} days green; all_green={summary.all_green}")
    return 0 if summary.all_green else 1


if __name__ == "__main__":
    sys.exit(main())
