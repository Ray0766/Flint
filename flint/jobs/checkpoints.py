"""JobCheckpoint 序列化（M1-004；判别联合 <-> JSON 文本，审16 不留裸 dict）。

JobStep.snapshot_ref 指向的序列化载荷即本模块产物；断点续跑（M1-035）
经 deserialize_checkpoint 恢复到精确类型。date 字段以 ISO 字符串落盘。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from typing import Final

from flint.domain.models import (
    AnalysisCheckpoint,
    DraftCheckpoint,
    IngestCheckpoint,
    JobCheckpoint,
    PricebookScanCheckpoint,
    RevalidationCheckpoint,
    SpecExportCheckpoint,
)

_CHECKPOINT_TYPES: Final[dict[str, type]] = {
    "gate1_analysis": AnalysisCheckpoint,
    "draft": DraftCheckpoint,
    "daily_ingest": IngestCheckpoint,
    "revalidation": RevalidationCheckpoint,
    "pricebook_scan": PricebookScanCheckpoint,
    "spec_export": SpecExportCheckpoint,
}


def serialize_checkpoint(checkpoint: JobCheckpoint) -> str:
    payload = asdict(checkpoint)
    for key, value in payload.items():
        if isinstance(value, date):
            payload[key] = {"__date__": value.isoformat()}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def deserialize_checkpoint(blob: str) -> JobCheckpoint:
    payload = json.loads(blob)
    kind = payload.get("kind")
    cls = _CHECKPOINT_TYPES.get(kind)
    if cls is None:
        raise ValueError(f"unknown checkpoint kind: {kind!r}")
    for key, value in payload.items():
        if isinstance(value, dict) and set(value) == {"__date__"}:
            payload[key] = date.fromisoformat(value["__date__"])
    result: JobCheckpoint = cls(**payload)
    return result
