"""迁移 0024：`templates` 表（PERSIST-03 / DEC-048）。

## 号为什么是 0024（**先写成 0025 是错的，改回来了**）

`0024` 本来是 `PERSIST-02` 的号，那张卡被阻在
`docs/blocked/PERSIST-02-TWO-DIFFERENT-THINGS-ARE-BOTH-CALLED-WORKBENCH.md`，
所以第一版把本卡编成 `0025` **给它留号**。

那是错的：本批 rules 写死「**NEVER 跳号也 NEVER 撞号**」，
而留号留出来的正是一个跳号。仓里有三把尺子当场判红
（`test_persist_fav_share_prefs` / `test_project_optimistic_lock` / `test_cluster_region`
各自的号段判据）——**它们是对的**。

「四张迁移卡各是哪一号」是 trace 上的记账方便，
「号段不许有洞」是写死的不变量，两者冲突时后者赢。
`PERSIST-02` 解阻之后接盘上当时最高的那一号即可。

## 表名以 `DEC-048` 为准

`flint/design/templates/registry.py:39` 自述「SQL 实现随 E2 的 `template_registry`
表接入」，而 `DEC-048`（owner 2026-08-09 裁的）点名的是 **`templates`**，
本批的出口判据也照那八个名字数。以裁决为准，那句注释是当时随手写下的设想。

## 主键是 `(template_id, version)`，因为注册表是 **append-only 的版本序列**

`registry.py` 文件头原话：「固化过的东西可能已经被别人拿去渲染了，
覆盖它等于让那些产物失去出处」。

所以这张表 **NEVER 有 upsert**：同内容不产出新版本（那一步由
`register_template` 在写之前判掉），内容变则**新增一行**。
把 `template_id` 单独做主键会逼出一个 `ON CONFLICT DO UPDATE`——
而那正是「旧版本被覆盖」的入口。

## `slots` 用 `text[]` 而不是 jsonb

冻结件那一行写着「用元组是因为插槽集合固化后不该被就地追加——
那会绕过 checksum 绑定」。`text[]` 读回来是一个 list，构造 `TemplateRecord`
时转成 tuple；jsonb 也能存，但它允许存进一个对象或者一个嵌套数组，
而那两种都不是「一串插槽名」。**列类型是最后一道形状约束**。

## `checksum` 不做唯一索引

去重的作用域是**一个 owner**（`register_template` 只在 `mine` 里比）：
两个人各自固化出内容相同的模板是正常的，它们是两份各自可用的东西。
建全表唯一索引会让第二个人的固化在库层面失败，而错误文本会说「重复」——
他并不知道自己和谁重复了，也没有任何办法解决。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("template_id", sa.Text, primary_key=True),
        # 版本进主键：append-only 版本序列（见模块 docstring）。
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("owner_kind", sa.Text, nullable=False),
        sa.Column("owner_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slots", sa.ARRAY(sa.Text), nullable=False),
        sa.Column("source_deliverable_id", sa.Text, nullable=True),
        sa.Column("html", sa.Text, nullable=False),
        sa.Column("checksum", sa.Text, nullable=False),
        sa.Column("solidified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    # 列表与去重都按 owner 走，索引形状跟着查询形状。
    op.create_index("ix_templates_owner", "templates", ["owner_kind", "owner_id"])


def downgrade() -> None:
    op.drop_index("ix_templates_owner", table_name="templates")
    op.drop_table("templates")
