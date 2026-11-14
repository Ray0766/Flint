"""迁移 0020：身份三张表（AUTH-01）——`users` / `orgs` / `memberships`。

## 为什么现在才建

`contracts/models.py` 里 `User` / `Org` / `Membership` 三个类型从一开始就在，
`flint/jobs/runner.py` 文件头也早写着「角色解析经注入 `RoleResolver`
（**memberships 表随身份任务落库后接 SQL 实现**）」——计划里一直有它。

顶出来的是 `WIRE-01`：四族路由（analysis / compose / interventions / combo）
十条全是写操作，挂上去就要回答「这个人对这个项目是什么角色」，
而库里没有任何事实可查。那次的选择是**拒绝挂**并开单，
owner 2026-08-06 裁决走「建表 + 真 resolver」这条路。

## 三张表的边界

- **`users`**：一个人。`email` 唯一——同一个邮箱两个账号，
  「这封邮件是谁」就有两个答案；
- **`orgs`**：一个组织。个人使用**无需先建 org**（冻结件 `Principal` 的原话），
  所以这张表可以是空的，而 `users` 不会；
- **`memberships`**：`(user_id, org_id)` **复合主键**。同一人在同一组织
  NEVER 有两条角色行——两条意味着「他是什么角色」有两个答案，
  而解析器只会取到其中一个，取到哪个取决于扫描顺序。**那是看起来正常的越权。**

## `role` 的取值域为什么是 CHECK 而不是只靠 Python

`Role = Literal["owner", "admin", "member", "viewer"]` 是 Python 侧的事实。
一条绕过应用的 `INSERT ... role='god'` 打进来时，`Literal` 不在场——
而一个库里存着的越界角色，解析出来的会是**一个谁都没定义过的权限**。

用 `CHECK` 而不是 PG 的 `ENUM` 类型：本仓既有的取值域全部是 `CHECK`
（`0006` 的 `ck_docs_kind` / `ck_docs_origin` / `ck_docs_access` 等），
换一种写法就要两套改法，而加一个角色时 `ALTER TYPE` 与改 `CHECK` 的代价并不同。

## 外键

`memberships` 两列各自指向 `users` / `orgs`，`ON DELETE CASCADE`：
人或组织没了，他在那里的角色行跟着没——**留下一条指向不存在的人的角色行，
比没有那条行更危险**。

## 回滚

三张表整体去掉，其余表一行不动。`projects.owner` 那一列（JSONB 存 `Principal`）
从 `0001` 就在，**与本迁移无关**——回滚回不到「没有归属」的世界，也不该回。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

# 取值域逐字来自冻结件 `Role`。改这里之前先改冻结件——顺序反了，
# 库会先接受一个 Python 侧还不认识的角色。
_ROLES = "('owner', 'admin', 'member', 'viewer')"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text, primary_key=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # 同一个邮箱两个账号 → 「这封邮件是谁」有两个答案。
    op.create_index("ux_users_email", "users", ["email"], unique=True)

    op.create_table(
        "orgs",
        sa.Column("org_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "memberships",
        sa.Column("user_id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text, primary_key=True),
        sa.Column("role", sa.Text, nullable=False),
        sa.CheckConstraint(f"role IN {_ROLES}", name="ck_memberships_role"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.org_id"], ondelete="CASCADE"),
    )
    # 解析器按「这个人在哪些组织里」查，索引落在 user_id 上。
    op.create_index("ix_memberships_user", "memberships", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_memberships_user", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("orgs")
    op.drop_index("ux_users_email", table_name="users")
    op.drop_table("users")
