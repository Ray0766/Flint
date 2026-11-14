"""迁移 0021：`clusters` 加 `region` 列（REGION-08）。

## 为什么现在建

规格 `docs/前端功能说明-v2.md#2.14` 写着 `GET /plaza/hot?region=`【已建，增 query】，
而端点签名只有 `day`——FastAPI 对未声明的 query **静默忽略**，
带 `region=CN` 回的是全量 154 条。`DEC-035`（owner 2026-08-08）的原话：
**一个静静地什么都不筛的筛选器比没有筛选器更坏**——用户会把「全国的热点」
读成「这个区的热点」，并据此做判断。

要真筛就得有列。开工前实查过：`clusters` 十列没有 region，`heat_points` 也没有；
region 今天只活在 `trend_items_raw`（0004 建的）与
`flint/region/bucketing.py` 的 `RegionCluster`——后者是模块内 dataclass，
**从没落过库**。

## 这一列为什么可空

回填是一次**可能停下**的操作：成员跨区的簇 MUST 上报而不是取众数
（`PRINCIPLES#B5`），成员里根本没有 region 的簇则是「还不知道」。

写成非空，回填就必须给每一条都填一个值，于是必然逼出一个默认值——
而默认值就是**给每个簇猜一个区**。`NULL` 说的是实话：这一条还没判出来。

## 为什么带索引

广场那条 query 的形状恒是 `WHERE region = $1`（外加 day 的连接）。
193 条时全表扫也无所谓，但这张表是**日更累积**的——
索引现在建最便宜，等到它慢下来时再加，那是一次生产库变更（S2-10 要人工确认）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 可空且**无默认值**：回填判不出来的簇留 NULL，NEVER 猜一个区。
    op.add_column("clusters", sa.Column("region", sa.Text, nullable=True))
    op.create_index("ix_clusters_region", "clusters", ["region"])


def downgrade() -> None:
    op.drop_index("ix_clusters_region", table_name="clusters")
    op.drop_column("clusters", "region")
