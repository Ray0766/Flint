"""每日簇质心快照 repo（H-4，迁移 0018）——弱信号轨的质心历史存储。

内部派生存储（NEVER 冻结件，S2-1）：日更管线把当日热点簇质心从 `clusters.centroid` 直拷进
`cluster_centroid_daily`（`INSERT...SELECT`，无向量文本往返、事务内）；弱信号轨（plaza）读窗口
质心序算 bge-m3 漂移。质心历史是弱信号"语义稳定=真成形"判定的唯一来源。
"""
from __future__ import annotations

from datetime import date

import asyncpg


class PgCentroidDailyStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def snapshot_from_clusters_on(
        self, conn: asyncpg.Connection, day: date, cluster_ids: list[str]
    ) -> None:
        """把当日 cluster_ids 的当前质心从 clusters 直拷进快照表（事务内，幂 upsert）。"""
        if not cluster_ids:
            return
        await conn.execute(
            "INSERT INTO cluster_centroid_daily (day, cluster_id, centroid) "
            "SELECT $1, cluster_id, centroid FROM clusters "
            "WHERE cluster_id = ANY($2::text[]) "
            "ON CONFLICT (day, cluster_id) DO UPDATE SET centroid = EXCLUDED.centroid",
            day, sorted(set(cluster_ids)),
        )
