"""迁移 0026：`prefs` 加 `theme` 列（SHELL-02 / DEC-050 / DEC-047）。

## 为什么它是**第三根轴**，而不是第三张表

`PRINCIPLES#A3` 说的是语言与地区正交；主题是第三件同类的东西——
**一个用户的一项显示偏好**。与 `lang` / `region` 并排一列，
读写走同一套口径（`get_prefs` / `set_prefs` / `GET|PUT /settings/locale`）。

另开一张表的话，「一个用户的偏好」就有了两个落点，
而下一个加第四项偏好的人不知道该往哪边放。

## 为什么不按设备存（`DEC-050` 逐字）

`DEC-047` 与 `SHELL-01` 的判据都写死「服务端为真相」。而「夜里用手机、
白天用台式机想要的不一样」这个真实需求，**三态里的「跟随系统」已经覆盖了**——
选「跟随系统」的人，每台设备各跟各的系统走；显式选了亮或暗的人，
是在说「我到哪都要这个」。所以主题**不单开一套按设备的存法**。

## 非空 + 默认 `system`

与 `lang` / `region` 同款：一行记录**永远有一个主题**，
`NULL` 在这里没有含义——它只会让读的人分不出「没选过」与「选了跟随系统」，
而这两件事在本卡里恰恰是**同一件**（默认就是跟随系统），
所以更没有理由留一个第三态出来。

`server_default` 是必需的：库里已经有 `prefs` 行（`SHELL-01` 写过），
不给起点的话迁移会在既有行上当场违约。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prefs",
        sa.Column("theme", sa.Text, nullable=False, server_default="system"),
    )


def downgrade() -> None:
    op.drop_column("prefs", "theme")
