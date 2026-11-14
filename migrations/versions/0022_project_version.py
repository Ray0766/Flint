"""迁移 0022：`projects` 加 `version` 列（LOCK-01，乐观锁）。

## 为什么现在建

`ENTRY-02`（v0.4.1 第 6 批）把 `PgProjectStore.save` 从纯 `INSERT` 改成全行 upsert。
**那个改动是对的**——`save` 只能建不能更是真缺陷。

**但 `projects` 九列里没有版本列，而 `change_log` 在被覆盖的列里**：

```
project_id · owner · origin_id · topic_ids · chosen_topic_id
· deliverable_ids · change_log · status · created_at
```

并发下：A 读（`change_log=[e1]`）→ B 读 → A 写 `[e1,e2]` → B 写 `[e1,e3]`，
**`e2` 无声消失**。

改前是「第二次写大声失败（500）」，改后是「并发下静默丢失」——
**它把一个响亮的错换成了一个安静的错**。今天只有一条写路径，
风险是**潜伏**的，而「潜伏」正是 `ENTRY-02` 形容原缺陷时用的词。

## 这一列为什么**非空且有默认值**

与 0021 的 `region` 刻意相反。

`region` 可空，因为「还不知道这个簇属于哪个区」是一种**真实状态**。
版本不是这样：**一行记录永远有一个版本**，`NULL` 在这里没有任何含义——
它只会让 `WHERE version = $n` 静静地匹配不到任何行，
而那个症状读起来是「冲突」，真相是「这一行从来没有版本」。

`server_default="1"` 是必需的：库里已经有 project 行
（demo 库两条、测试库若干），不给起点的话迁移会在既有行上当场违约。
默认值只在**建行**时生效，之后由 `PgProjectStore` 的条件更新推进——
**NEVER 让数据库自己去加**（触发器之类）：那样版本会在没人预期的时候前进，
而调用方拿着刚读到的版本去写就会莫名冲突。

## 口径与账本那一套同源

`facts_ledgers` 的乐观锁靠 `(project_id, version)` 唯一索引 + 先读后比
（`flint/ledger/store.py`）。**这里不需要唯一索引**：版本是同一行上的一列，
条件更新（`WHERE version = $n`）由行锁保证互斥，
而账本那边每个版本是**一行新记录**，才需要唯一索引来兜住竞态。

两处的**语义**一致（版本不符 → 抛携带当前状态的冲突），
落地手段按各自的数据形状选——那不是两套锁。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 非空 + 默认 1：既有行从 1 起，之后由条件更新推进（见模块 docstring）。
    op.add_column(
        "projects",
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("projects", "version")
