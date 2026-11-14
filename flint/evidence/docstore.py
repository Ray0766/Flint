"""Feature B-1：DocStore——Doc(元信息) + Citation(quote_span) 落 0006 表（照冻结件）。

save→load 保真；照冻结 Doc/Citation 类型只读消费、NEVER 改契约。
doc_id 内容寻址，upsert 重复保存安全。

## DOC-02：正文进库（owner 2026-08-04 裁决方案 A 之后）

本模块原先的门 1=C 口径是「Doc 只落元信息，**无 content 字段、NEVER 全文**，
正文只进 `Citation.quote_span` 短段」。**那条口径被 owner 的裁决覆盖**——
不是我自己松的：DOC-01 已把 `content` / `content_sha256` / `content_truncated` /
`source_file_ref` 走 additive 通道加进 `contracts_v04`，本卡把它落到库里。
凡后续再有人引用「Doc 无 content」来禁止正文进库，要连带看到这一条。

**旧口径的那一半仍然有效**：`Citation.quote_span` 仍是「引用哪一段」的落点，
正文进库不代表引用可以指向整篇——引用要能定位到具体的一段。

## 两条 API 并存，各归各的

| 用哪个 | 类型 | 场景 |
|---|---|---|
| `save_doc` / `load_doc` | `flint.domain.models.Doc`（冻结件，无正文） | 既有调用点，一行不改 |
| `save_doc_with_content` / `load_doc_with_content` | `contracts_v04.models_v04.Doc` | 抓取管线写正文 |

v04 契约按仓里既有的形态**惰性 import**（同 `flint/region/registry.py`、
`flint/sources/candidates.py`）：`flint/domain/` 是冻结件的逐字副本，NEVER 改。

## 正文单独一张表（`doc_contents`）

同一篇文章被多个源抓到 = 多行 `docs`，但正文只存一份（acceptance④）。
理由与表结构见 `migrations/versions/0019_doc_content.py` 的模块 docstring。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, cast

import asyncpg

from flint.domain.models import JSON, Citation, Doc, DocKind, EvidenceAccess, EvidenceOrigin


@dataclass(frozen=True)
class PreparedContent:
    """一段正文过完「算哈希 → 截断」之后的三件套。

    三件事一次算齐、一次返回：分开算的话，调用方可能拿截断后的正文再去算哈希——
    那正是 DOC-01 的字段说明写死要避免的那件事。
    """

    content: str
    sha256: str
    truncated: bool


def prepare_content(raw: str) -> PreparedContent:
    """正文 → 三件套。**哈希算的是截断前那一份**。

    截断后再算的话，同一篇文章因两次截断位置不同会算出两个哈希，
    验证（库里这份还是不是当初那份）与去重（多源同文只存一份）同时失灵。

    截断按**字节**：上限是存储的口径，而一个汉字占三字节——
    按字符切的话，一篇汉字正文会是上限的三倍大。
    切完再按 UTF-8 边界回退，NEVER 把一个字符切成两半（那会产出坏 UTF-8）。
    """
    from contracts_v04.models_v04 import DOC_CONTENT_MAX_BYTES

    encoded = raw.encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    if len(encoded) <= DOC_CONTENT_MAX_BYTES:
        # 恰好等于上限**不算**截断：边界上多标一次，下游会以为全文缺了一块。
        return PreparedContent(content=raw, sha256=digest, truncated=False)
    cut = encoded[:DOC_CONTENT_MAX_BYTES].decode("utf-8", errors="ignore")
    return PreparedContent(content=cut, sha256=digest, truncated=True)


def build_doc_with_content(doc: Any, raw: str) -> Any:
    """把正文三件套一次填进 v04 的 `Doc`，其余字段一个不动。

    一次填齐而不是让调用方各填各的：分开填的话，总有一处会填了正文忘了标截断，
    而那一份在下游看来就是全文。
    """
    prepared = prepare_content(raw)
    return replace(
        doc,
        content=prepared.content,
        content_sha256=prepared.sha256,
        content_truncated=prepared.truncated,
    )


class PgDocStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    async def save_doc(self, doc: Doc) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO docs (doc_id, source_id, kind, title, url, "
                "published_at, meta, origin, access) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9) "
                "ON CONFLICT (doc_id) DO UPDATE SET "
                "source_id=EXCLUDED.source_id, kind=EXCLUDED.kind, "
                "title=EXCLUDED.title, url=EXCLUDED.url, "
                "published_at=EXCLUDED.published_at, meta=EXCLUDED.meta, "
                "origin=EXCLUDED.origin, access=EXCLUDED.access",
                doc.doc_id, doc.source_id, doc.kind, doc.title, doc.url,
                doc.published_at, json.dumps(doc.meta, ensure_ascii=False),
                doc.origin, doc.access)
        finally:
            await conn.close()

    async def load_doc(self, doc_id: str) -> Doc:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow("SELECT * FROM docs WHERE doc_id = $1", doc_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(doc_id)
        return self._to_doc(row)

    @staticmethod
    def _to_doc(row: asyncpg.Record) -> Doc:
        published = row["published_at"]
        return Doc(
            doc_id=str(row["doc_id"]), source_id=str(row["source_id"]),
            kind=cast("DocKind", row["kind"]), title=str(row["title"]),
            url=str(row["url"]),
            published_at=cast("date | None", published),
            meta=cast("JSON", json.loads(row["meta"])),
            origin=cast("EvidenceOrigin", row["origin"]),
            access=cast("EvidenceAccess", row["access"]))

    async def save_doc_with_content(
        self, doc: Any, *, _fail_after_metadata: bool = False,
    ) -> None:
        """元数据 + 正文**一次事务写入**（acceptance②）。

        分两次写的话，中间挂掉会留下一行「有元数据、没正文、也没标记还没提取」的 doc——
        它和「提取失败」长得一模一样，重跑时没人知道该重跑哪一条。

        正文按 `content_sha256` upsert 进 `doc_contents`：同一份内容写多少次都只有一行，
        而每个源各自的 `doc_id` / `source_id` / `url` 原样保留（acceptance④）。

        `_fail_after_metadata` 只给判据用：它在元数据已写、正文未写的**那一瞬**抛错，
        用来证明整笔会回滚。生产路径 NEVER 传它。
        """
        conn = await asyncpg.connect(self._dsn)
        try:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO docs (doc_id, source_id, kind, title, url, "
                    "published_at, meta, origin, access, "
                    "content_sha256, content_truncated, source_file_ref) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9, $10, $11, $12) "
                    "ON CONFLICT (doc_id) DO UPDATE SET "
                    "source_id=EXCLUDED.source_id, kind=EXCLUDED.kind, "
                    "title=EXCLUDED.title, url=EXCLUDED.url, "
                    "published_at=EXCLUDED.published_at, meta=EXCLUDED.meta, "
                    "origin=EXCLUDED.origin, access=EXCLUDED.access, "
                    "content_sha256=EXCLUDED.content_sha256, "
                    "content_truncated=EXCLUDED.content_truncated, "
                    "source_file_ref=EXCLUDED.source_file_ref",
                    doc.doc_id, doc.source_id, doc.kind, doc.title, doc.url,
                    doc.published_at, json.dumps(doc.meta, ensure_ascii=False),
                    doc.origin, doc.access,
                    doc.content_sha256, bool(doc.content_truncated), doc.source_file_ref)
                if _fail_after_metadata:
                    raise RuntimeError("boom: 判据在这里炸，用来证明整笔回滚")
                if doc.content is not None:
                    await conn.execute(
                        "INSERT INTO doc_contents "
                        "(content_sha256, content, content_truncated, byte_length) "
                        "VALUES ($1, $2, $3, $4) "
                        "ON CONFLICT (content_sha256) DO NOTHING",
                        doc.content_sha256, doc.content, bool(doc.content_truncated),
                        len(doc.content.encode("utf-8")))
        finally:
            await conn.close()

    async def load_doc_with_content(self, doc_id: str) -> Any:
        """读回 v04 的 `Doc`，正文从 `doc_contents` 取。

        正文行不在时 `content` 留 `None`——那就是「还没提取」，
        NEVER 用空串顶上（空串是「提取过、结果是空」，两者是两回事）。
        """
        from contracts_v04.models_v04 import Doc as DocV04

        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT d.*, c.content AS body FROM docs d "
                "LEFT JOIN doc_contents c ON c.content_sha256 = d.content_sha256 "
                "WHERE d.doc_id = $1", doc_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(doc_id)
        base = self._to_doc(row)
        return DocV04(
            doc_id=base.doc_id, source_id=base.source_id, kind=base.kind,
            title=base.title, url=base.url, published_at=base.published_at,
            meta=base.meta, origin=base.origin, access=base.access,
            region=None, source_country=None,
            content=None if row["body"] is None else str(row["body"]),
            content_sha256=(
                None if row["content_sha256"] is None else str(row["content_sha256"])),
            content_truncated=bool(row["content_truncated"]),
            source_file_ref=(
                None if row["source_file_ref"] is None else str(row["source_file_ref"])),
        )

    async def save_citation(self, citation: Citation) -> None:
        conn = await asyncpg.connect(self._dsn)
        try:
            await conn.execute(
                "INSERT INTO citations (citation_id, doc_id, locator, quote_span) "
                "VALUES ($1, $2, $3, $4) "
                "ON CONFLICT (citation_id) DO UPDATE SET "
                "doc_id=EXCLUDED.doc_id, locator=EXCLUDED.locator, "
                "quote_span=EXCLUDED.quote_span",
                citation.citation_id, citation.doc_id, citation.locator,
                citation.quote_span)
        finally:
            await conn.close()

    async def load_citation(self, citation_id: str) -> Citation:
        conn = await asyncpg.connect(self._dsn)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM citations WHERE citation_id = $1", citation_id)
        finally:
            await conn.close()
        if row is None:
            raise KeyError(citation_id)
        return self._to_citation(row)

    @staticmethod
    def _to_citation(row: asyncpg.Record) -> Citation:
        return Citation(
            citation_id=str(row["citation_id"]), doc_id=str(row["doc_id"]),
            locator=None if row["locator"] is None else str(row["locator"]),
            quote_span=None if row["quote_span"] is None else str(row["quote_span"]))

    async def citations_for_doc(self, doc_id: str) -> list[Citation]:
        conn = await asyncpg.connect(self._dsn)
        try:
            rows = await conn.fetch(
                "SELECT * FROM citations WHERE doc_id = $1 ORDER BY citation_id", doc_id)
        finally:
            await conn.close()
        return [self._to_citation(r) for r in rows]
