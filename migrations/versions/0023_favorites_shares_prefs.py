"""迁移 0023：`favorites` · `share_links` · `prefs` 三张表（PERSIST-01 / DEC-048）。

## 为什么现在建

`DEC-048` 记的实况：这三张表**从来没有建过**。于是

- `flint/api/app.py` 给 favorites 注 `store=None` → `GET /favorites` 回 `not_provided`；
- share 与 prefs 注的是**内存件** → 进程一重启，链接与偏好一起没了。

`flint/fav/store.py:35` 与 `flint/profile/prefs.py:39` 两处自述里写的
「SQL 实现随表接入」，接的就是这三张。

## 归属列为什么拆成两列而不是一个 jsonb

`Principal` 是 `(kind, id)` 两个字段。`profiles` 表把它存成 `owner jsonb`
（`flint/profile/store.py:63`），那张表按 `profile_id` 取，归属只是随行数据。

这三张不一样：**它们全都要按归属过滤**（我的收藏 / 我的链接 / 我的偏好），
而按 jsonb 过滤要么走 `owner->>'id'` 表达式索引、要么全表扫。
拆成两列之后 `(owner_kind, owner_id)` 是一个普通复合索引——
**索引形状跟着查询形状走**，这是唯一的理由。

## `favorites.snapshot_stale` 为什么非空且默认 false

冻结件原话：「新收藏还没被算过，故 `snapshot_stale` 默认 False」。
`NULL` 在这里会多出第三种含义（「没算过」），而**「没算过」已经由 `False` 表示了**——
两个东西表示同一件事的时候，读它的人必须知道是谁写的才知道该信哪个。
`stale` 判定只能由 Revalidator 置（§6-H1），存储层照原样存。

## `share_links.expires_at` 为什么可空，`revoked` 为什么不可空

冻结件把这两件事**刻意分开**：「过期可续期，撤销不可逆」。

- `expires_at = NULL` 是一种**真实状态**：不过期。
- `revoked` 没有第三态：一条链接要么撤了要么没撤。`NULL` 只会让
  `WHERE NOT revoked` 静静地漏掉那些行，而漏掉的正是**没被撤销的可用链接**。

## `prefs` 为什么不并进 `profiles`

`profiles` 是 `UserProfile`（M3-014，敏感度过滤、owner_only 路径那一套）。
语言与地区是**每个用户都有**的两轴，与「有没有填过创业档案」无关。
并进去的话，一个没建过 profile 的人切语言会先被迫建一个空 profile——
而 `get_prefs` 的既有口径是「未设置 → 声明过的默认值」，不是「先去建一行」。

`user_id` 直接做主键：一个用户一行，`PRINCIPLES#A3` 的两轴各占一列。
**NEVER 合成 `zh-CN` 一列**——合成串把两轴绑死，切地区必然连语言一起切。

## 主题那一列不在这张迁移里

`DEC-047` 的白天/夜间三态也存在 `prefs` 里，但 `Prefs` 今天只有 `lang` / `region`
两个字段。现在加一个没有任何代码读写的列，等于把一个猜测写进 schema——
列建在 `SHELL-02` 那张卡里（迁移 0027），与它一起加进 `Prefs`。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("favorite_id", sa.Text, primary_key=True),
        # 归属拆两列：这张表恒按归属过滤（见模块 docstring）。
        sa.Column("owner_kind", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Text, nullable=False),
        sa.Column("target_kind", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text, nullable=False),
        # 内嵌快照是本体（冻结件 I9 基线），NEVER 换成对 snapshots 的引用。
        sa.Column("evidence_snapshot", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "snapshot_stale", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_favorites_owner", "favorites", ["owner_kind", "owner_id"])

    op.create_table(
        "share_links",
        sa.Column("token", sa.Text, primary_key=True),
        sa.Column("target_kind", sa.Text, nullable=False),
        sa.Column("target_id", sa.Text, nullable=False),
        sa.Column("created_by_kind", sa.Text, nullable=False),
        sa.Column("created_by_id", sa.Text, nullable=False),
        # 可空 = 不过期（一种真实状态）。
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        # 不可空 = 撤销没有第三态（见模块 docstring）。
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # 只存 hash。冻结件原话：连放明文的地方都不留。
        sa.Column("password_hash", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_share_links_owner", "share_links", ["created_by_kind", "created_by_id"])

    op.create_table(
        "prefs",
        sa.Column("user_id", sa.Text, primary_key=True),
        # 两轴各占一列（A3 正交），NEVER 合成一根字符串。
        sa.Column("lang", sa.Text, nullable=False),
        sa.Column("region", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    # 索引随表一起走（`drop_table` 带走它自己的索引），这里按建表的反序删。
    op.drop_table("prefs")
    op.drop_index("ix_share_links_owner", table_name="share_links")
    op.drop_table("share_links")
    op.drop_index("ix_favorites_owner", table_name="favorites")
    op.drop_table("favorites")
