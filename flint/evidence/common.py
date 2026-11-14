"""证据适配器共用件（M2-009~013）：统一溯源三字段的实现基座。

冻结协议头部约定六类数据源统一溯源 source_id / url / fetched_at；
Doc 冻结模型无 fetched_at 字段 → 归 meta["fetched_at"]（ISO 字符串），
合规抽查（M2-015）按此口径。doc_id 为 url 的内容寻址（确定性）。
"""
from __future__ import annotations

import hashlib
from datetime import datetime

from flint.domain.models import JSON


def doc_id_for(url: str) -> str:
    return "doc-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def base_meta(now: datetime, **extra: object) -> JSON:
    meta: JSON = {"fetched_at": now.isoformat()}
    meta.update(extra)
    return meta


def plus_query(text: str) -> str:
    return text.replace(" ", "+")
