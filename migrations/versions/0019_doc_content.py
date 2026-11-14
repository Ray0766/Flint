"""迁移 0019：证据正文进库（DOC-02，接 DOC-01 的契约增量）。

## 为什么正文单独一张表

`docs` 那三列（`content_sha256` / `content_truncated` / `source_file_ref`）是**这一行
doc 自己的事实**；而**正文本身**是「这篇文章」的事实，与抓到它的是哪个源无关。

同一篇文章被四个源抓到 = 四行 `docs`（各有各的 `doc_id` / `source_id` / `url`），
但正文只该存一份（DOC-02 acceptance④）。把正文留在 `docs` 一列上做不到这件事：
第二行只能填 `NULL`，而 DOC-01 把 `content IS NULL` 的语义写死成**「还没提取」**——
两件事挤进同一个值，重跑提取时就不知道该跳过谁。

所以：`doc_contents` 按 `content_sha256` 主键存正文（一份内容一行），
`docs.content_sha256` 指过去。**引用关系保留**：四行 doc 原样都在。

## 为什么不给 docs.content_sha256 加外键

抓取管线可能先落元数据、后补正文（DOC-03 的重跑路径）。加外键的话，
那一步会因为正文还没写而失败——而「先有 doc、后有正文」是正常的采集顺序。
一致性由写入路径的单事务保证（`PgDocStore.save_doc_with_content`）。

## 回滚

三列 + 一表全部清掉，`docs` 的既有行**一行不动**——回滚要能回到 0018 的世界，
而不是把证据层删了。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doc_contents",
        # 主键就是内容哈希：同一份正文写多少次都只有一行。
        sa.Column("content_sha256", sa.Text, primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        # 截断标记跟着**正文**走：同一份被截断的正文，从哪个源看都是截断的。
        sa.Column("content_truncated", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("byte_length", sa.Integer, nullable=False),
    )

    op.add_column("docs", sa.Column("content_sha256", sa.Text, nullable=True))
    # 这一列在 docs 上是**这一行的**截断态，与 doc_contents 那一列同值；
    # 冗余是有意的：读一行 doc 不必 join 就知道自己拿到的是不是全文。
    op.add_column("docs", sa.Column("content_truncated", sa.Boolean, nullable=False,
                                    server_default=sa.text("false")))
    op.add_column("docs", sa.Column("source_file_ref", sa.Text, nullable=True))
    # 去重查的就是这一列：没有索引时每存一篇要全表扫一遍。
    op.create_index("ix_docs_content_sha", "docs", ["content_sha256"])


def downgrade() -> None:
    op.drop_index("ix_docs_content_sha", table_name="docs")
    op.drop_column("docs", "source_file_ref")
    op.drop_column("docs", "content_truncated")
    op.drop_column("docs", "content_sha256")
    op.drop_table("doc_contents")
