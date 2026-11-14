"""迁移 0028：把既有 gtrends 行的 region 从 CN 回填成 HK（REGION-CN-HK / DEC-056）。

## 回填是把标签改回与出处一致，不是改写事实

库里既有的 gtrends 行今天标着 `region='CN'`，而**它们的 provenance manifest
记的是真实的 `geo=HK` URL**——数据从来就是港区的，标签是 `DEC-054` 那条
「华语圈代理」口径贴上去的。`DEC-056` 撤销了那条口径，
所以这一步**改的是标签，不是事实**：出处链一个字都没动。

（这句话是 `DEC-056` 逐字要求写进迁移注释的。）

## 只按 source_id 定位，NEVER 按词面猜

`WHERE source_id = 'gtrends'`。**NEVER 去猜「哪几条看起来像港区的」**——
词面猜法在「馬國明」这种两地都可能上榜的条目上必然错，
而错了之后没有任何东西会报红。

## 簇那一层：只动**无歧义**的那些

`clusters.region` 由成员推出（`flint/region/backfill.py#region_of_members`）。
实测（demo 库）：

| 簇 | 数量 | 这一步怎么处置 |
|---|---|---|
| 只有 gtrends | 35 | → `HK` |
| 混源（含 gtrends 与别的源） | 1 | **不动**，见下 |
| 不含 gtrends | 233 | 不动 |

混源那一簇今天成员真的跨区了。既有口径写死在 `region_of_members` 里：
跨区**抛错并点名**，「MUST 停下上报，NEVER 取众数——
取众数只会把这个信号抹平，并留下一个哪个区都不存在的假热点」。

所以这一步**不给它挑一个区**，留给人看
（单据 `docs/blocked/REGION-CN-HK-ONE-CLUSTER-SPANS-BOTH.md`）。

## downgrade 回得去

反向把同一批改回 `CN`。**定位方式一模一样**（按 `source_id` 与
「只有 gtrends 的簇」），所以来回一次不会多动也不会少动一行。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

#: 只有这一个源在这一步里换区。写成常量是为了 upgrade 与 downgrade **共用同一个定位**。
_SOURCE = "gtrends"

#: 「只有这一个源」的簇。`heat_points` 是簇与源的连接处。
_SOLE_SOURCE_CLUSTERS = sa.text("""
    SELECT cluster_id FROM heat_points
    GROUP BY cluster_id
    HAVING array_agg(DISTINCT source_id) = ARRAY[:source]::text[]
""")


def _move(from_region: str, to_region: str) -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE trend_items_raw SET region = :to "
            "WHERE source_id = :source AND region = :from_"
        ),
        {"to": to_region, "source": _SOURCE, "from_": from_region},
    )
    conn.execute(
        sa.text(
            "UPDATE clusters SET region = :to "
            "WHERE region = :from_ AND cluster_id IN ("
            "  SELECT cluster_id FROM heat_points"
            "  GROUP BY cluster_id"
            "  HAVING array_agg(DISTINCT source_id) = ARRAY[:source]::text[]"
            ")"
        ),
        {"to": to_region, "source": _SOURCE, "from_": from_region},
    )


def upgrade() -> None:
    _move("CN", "HK")


def downgrade() -> None:
    _move("HK", "CN")
