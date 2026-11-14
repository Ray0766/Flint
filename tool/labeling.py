"""血缘标注工具：抽 50 簇导出 yaml（M1-038，PDD v0.3.1 §7）。

- 数据源：30 天回放库（lineage_audit 逐簇时间线，M1-029 审计视图口径）。
- 标注格式：label_classes 含 延续(continued)/分裂(split)/合并(merged)/新生(new)
  四类（验收硬条款）+ revived/dormant 全生命周期；每事件带空 label 槽。
- 抽样：种子化确定性抽样；工程化构造的复活簇强制入样（人审必看场景）。
- 用法：python -m tool.labeling --out docs/labeling/lineage-50.yaml
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

import asyncpg
import yaml

LABEL_CLASSES = ["continued", "split", "merged", "new", "revived", "dormant"]

REVIVAL_MARKER = "复活测试词"


async def export_labeling_sheet(
    dsn: str, out: Path, sample_size: int = 50, seed: int = 42
) -> int:
    conn = await asyncpg.connect(dsn)
    try:
        cluster_rows = await conn.fetch(
            "SELECT DISTINCT cluster_id FROM lineage_audit WHERE role = 'subject' "
            "ORDER BY cluster_id"
        )
        all_ids = [r["cluster_id"] for r in cluster_rows]
        kw_rows = await conn.fetch("SELECT keyword_id, canonical FROM keywords")
        canonical_by_id = {r["keyword_id"]: r["canonical"] for r in kw_rows}

        forced: list[str] = []
        marker_row = await conn.fetchrow(
            "SELECT cluster_id FROM lineage_audit WHERE role = 'subject' "
            "AND event_kind = 'revived' AND event::text LIKE '%' || $1 || '%' "
            "ORDER BY day LIMIT 1",
            _marker_keyword_id(),
        )
        if marker_row is not None:
            forced.append(marker_row["cluster_id"])

        rng = random.Random(seed)
        pool = [cid for cid in all_ids if cid not in forced]
        sampled = forced + rng.sample(pool, k=max(0, sample_size - len(forced)))
        sampled = sorted(sampled[:sample_size])

        clusters: list[dict[str, Any]] = []
        for cid in sampled:
            rows = await conn.fetch(
                "SELECT day, event_kind, event FROM lineage_audit "
                "WHERE cluster_id = $1 AND role = 'subject' ORDER BY day, event_index",
                cid,
            )
            keyword_ids: set[str] = set()
            timeline = []
            for r in rows:
                payload = json.loads(r["event"])
                keyword_ids.update(payload.get("keyword_ids", []))
                timeline.append(
                    {
                        "day": r["day"].isoformat(),
                        "system_kind": r["event_kind"],
                        "label": None,
                    }
                )
            clusters.append(
                {
                    "cluster_id": cid,
                    "keywords": sorted(
                        canonical_by_id.get(k, k) for k in keyword_ids
                    ),
                    "timeline": timeline,
                }
            )
    finally:
        await conn.close()

    sheet = {
        "version": 0,
        "purpose": "血缘人工标注（M1-038）；对照口径见 assets/labels.yaml（生成器直出真值）",
        "label_classes": LABEL_CLASSES,
        "clusters": clusters,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(sheet, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return len(clusters)


def _marker_keyword_id() -> str:
    from flint.jobs.ingest import keyword_id_for

    return keyword_id_for(REVIVAL_MARKER, "zh")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="flint lineage labeling exporter")
    parser.add_argument("--out", default="docs/labeling/lineage-50.yaml")
    parser.add_argument("--sample", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    # 同 eval/lineage.py：CLI 默认 demo 库、env 优先。
    # 测试从不吃这个 default：tests/m1/test_m1_038.py 直接传 DSN 给 export_labeling_sheet。
    parser.add_argument(
        "--dsn", default=os.environ.get(
            "FLINT_DEMO_DSN", "postgresql://flint:flint@localhost:55432/flint")
    )
    args = parser.parse_args(argv)
    count = asyncio.run(
        export_labeling_sheet(args.dsn, Path(args.out), args.sample, args.seed)
    )
    print(f"labeling sheet written: {args.out} ({count} clusters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
