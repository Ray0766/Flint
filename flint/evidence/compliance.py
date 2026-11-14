"""证据溯源合规与快照接入（M2-015，统一溯源约定 + F2 可复现）。

- check_provenance：六源产出的每条 Doc 必带 source_id / url / meta.fetched_at
  （冻结协议头部约定；fetched_at 归 meta 的口径见 flint/evidence/common.py）。
- serialize/restore + snapshot_docs/load_docs_snapshot：检索结果全量入
  SnapshotStore（bytes 契约），snapshot_id 回填 GenerationRecord，
  任一 Analysis 可按快照无损回放（F2）。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from typing import Any

from flint.domain.models import Doc
from flint.store.snapshot import PgSnapshotStore


def check_provenance(docs: list[Doc]) -> list[str]:
    violations: list[str] = []
    for doc in docs:
        if not doc.source_id:
            violations.append(f"{doc.doc_id}: source_id missing")
        if not doc.url:
            violations.append(f"{doc.doc_id}: url missing")
        if not doc.meta.get("fetched_at"):
            violations.append(f"{doc.doc_id}: meta.fetched_at missing")
    return violations


def serialize_docs(docs: list[Doc]) -> bytes:
    rows = []
    for doc in docs:
        row = asdict(doc)
        published = row["published_at"]
        row["published_at"] = published.isoformat() if published is not None else None
        rows.append(row)
    return json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")


def restore_docs(payload: bytes) -> list[Doc]:
    rows: list[dict[str, Any]] = json.loads(payload.decode("utf-8"))
    docs: list[Doc] = []
    for row in rows:
        published = row.pop("published_at")
        docs.append(
            Doc(
                published_at=date.fromisoformat(published) if published else None,
                **row,
            )
        )
    return docs


async def snapshot_docs(store: PgSnapshotStore, docs: list[Doc]) -> str:
    return await store.put(serialize_docs(docs))


async def load_docs_snapshot(store: PgSnapshotStore, snapshot_id: str) -> list[Doc]:
    return restore_docs(await store.get(snapshot_id))
