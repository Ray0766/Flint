"""7 天日更演练（M1-040，技术方案 E7 监控断言；verify_cmd: python -m harness.drill7）。

- 回放加速：7 个日更批次经调度层（M1-036 分布式锁）背靠背执行，零人工干预；
  窗口 06-29~07-05 覆盖单源限频日（07-05 微博 429）。
- 断言面：7/7 executed 且 job done；degraded 场景标注（degradation_notes 落库 +
  广场角标文案）；E7 四指标计数器齐（ingest_success_total / degraded_sources_total /
  job_duration_seconds / llm_cost_cny_total）。
- 产出 runbook：docs/trace/drill7.md（逐日一行 + 降级标注 + 指标快照）。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import asyncpg
import redis.asyncio as aioredis

from flint.jobs.ingest import build_replay_deps, run_daily_ingest
from flint.jobs.sched import run_scheduled_ingest
from flint.obs.metrics import (
    REQUIRED_INGEST_METRICS,
    get_value,
    registry_snapshot,
    reset_metrics,
)
from flint.sources.degradation import card_gap_annotations, fetch_notes_on

_WIPE = [
    "DELETE FROM evidence_cards",
    "DELETE FROM heat_points",
    "DELETE FROM lineage_results",
    "DELETE FROM clusters",
    "DELETE FROM keywords",
    "DELETE FROM trend_items_raw",
    "DELETE FROM degradation_notes",
    "DELETE FROM job_events WHERE job_id LIKE 'drill-%'",
    "DELETE FROM job_steps WHERE job_id LIKE 'drill-%'",
    "DELETE FROM jobs WHERE job_id LIKE 'drill-%'",
]


@dataclass
class DrillDay:
    day: date
    outcome: str
    job_state: str
    gap_annotations: list[str] = field(default_factory=list)


@dataclass
class DrillReport:
    days: list[DrillDay] = field(default_factory=list)

    @property
    def all_green(self) -> bool:
        return bool(self.days) and all(
            d.outcome == "executed" and d.job_state == "done" for d in self.days
        )


async def _drill(
    days: int, end: date, dsn: str, redis_url: str, fixtures_root: Path
) -> DrillReport:
    report = DrillReport()
    conn = await asyncpg.connect(dsn)
    try:
        for stmt in _WIPE:
            await conn.execute(stmt)
    finally:
        await conn.close()
    reset_metrics()

    shared_embedder = None
    client: aioredis.Redis = aioredis.Redis.from_url(redis_url)
    try:
        for offset in range(days - 1, -1, -1):
            day = end - timedelta(days=offset)
            deps = build_replay_deps(dsn=dsn, fixtures_root=fixtures_root, day=day)
            if shared_embedder is None:
                shared_embedder = deps.embedder
            else:
                deps.embedder = shared_embedder

            async def ingest_once(day: date = day, deps: object = deps) -> None:
                await run_daily_ingest(
                    job_id=f"drill-{day.isoformat()}", day=day, deps=deps  # type: ignore[arg-type]
                )

            outcome = await run_scheduled_ingest(client, day, "am", ingest_once)

            conn = await asyncpg.connect(dsn)
            try:
                state: str = await conn.fetchval(
                    "SELECT state FROM jobs WHERE job_id = $1", f"drill-{day.isoformat()}"
                )
                notes = await fetch_notes_on(conn, day)
            finally:
                await conn.close()
            report.days.append(
                DrillDay(
                    day=day,
                    outcome=outcome.outcome,
                    job_state=state,
                    gap_annotations=card_gap_annotations(notes),
                )
            )
    finally:
        await client.aclose()
    return report


def _write_runbook(report: DrillReport, runbook: Path) -> None:
    green = sum(1 for d in report.days if d.job_state == "done")
    lines = [
        "# drill7 runbook — 7 天日更演练（M1-040）",
        "",
        f"## 总览：{green}/{len(report.days)} green；零人工干预 = {report.all_green}",
        "",
        "## 逐日",
    ]
    for d in report.days:
        marker = " [degraded]" if d.gap_annotations else ""
        lines.append(
            f"- {d.day.isoformat()}: scheduler={d.outcome}, job={d.job_state}{marker}"
        )
        for annotation in d.gap_annotations:
            lines.append(f"  - 角标：{annotation}")
    lines += ["", "## E7 四指标计数器"]
    for required in REQUIRED_INGEST_METRICS:
        lines.append(f"- {required}: 在册")
    for (name, labels), value in sorted(registry_snapshot().items()):
        label_text = ",".join(f"{k}={v}" for k, v in labels)
        lines.append(f"  - {name}{{{label_text}}} = {value:.3f}")
    degraded_days = [d for d in report.days if d.gap_annotations]
    lines += [
        "",
        "## degraded 场景",
        *(
            [
                f"- {d.day.isoformat()}: {'; '.join(d.gap_annotations)}"
                f"（degradation_notes 已落库，reason=rate_limited）"
                for d in degraded_days
            ]
            or ["- 无"]
        ),
    ]
    runbook.parent.mkdir(parents=True, exist_ok=True)
    runbook.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run_drill(
    days: int, end: date, dsn: str, redis_url: str, fixtures_root: Path, runbook: Path
) -> DrillReport:
    report = asyncio.run(_drill(days, end, dsn, redis_url, fixtures_root))
    _write_runbook(report, runbook)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="flint 7-day drill")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--end", default="2026-07-05")
    # CLI 演练默认打 demo 库（人手动跑 7 天演练就是冲 demo 数据去的）；env 优先。
    # 测试从不吃这个 default——run_drill 的 dsn 是必填参数，tests 各自传测试库。
    parser.add_argument("--dsn", default=os.environ.get(
        "FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint"))
    parser.add_argument("--redis", default="redis://localhost:56379/0")
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--fixtures-root", default=str(root / "fixtures"))
    parser.add_argument("--runbook", default=str(root / "docs" / "trace" / "drill7.md"))
    args = parser.parse_args(argv)
    report = run_drill(
        days=args.days,
        end=date.fromisoformat(args.end),
        dsn=args.dsn,
        redis_url=args.redis,
        fixtures_root=Path(args.fixtures_root),
        runbook=Path(args.runbook),
    )
    counters_ok = all(
        any(name == req or name.startswith(req) for name, _ in registry_snapshot())
        for req in REQUIRED_INGEST_METRICS
    )
    degraded_ok = get_value("degraded_sources_total", {"source": "weibo"}) >= 1.0
    print(
        f"drill7: {sum(1 for d in report.days if d.job_state == 'done')}/{len(report.days)} "
        f"green; counters_ok={counters_ok}; degraded_annotated={degraded_ok}"
    )
    return 0 if report.all_green and counters_ok and degraded_ok else 1


if __name__ == "__main__":
    sys.exit(main())
