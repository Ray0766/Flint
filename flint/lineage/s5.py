"""血缘⑤ 新簇建档 + LLM 命名（M1-027，PDD v0.2 §3.2；结构化输出走 E5/D9）。

- 命名经 LLMProvider.generate_structured(prompt, NAMING_SCHEMA, max_retries=2)；
  返回值本方再校验（name 非空、category_id 在 12 类目录内）——schema 校验双保险。
- 任何失败（provider 抛错 / 校验不过）→ 降级：canonical_name = top 关键词、
  category = fallback，**不阻塞建档**（章节类降级语义，非 verdict 类，S2-3 例外面）。
- cluster_id 由血缘决策（M1-025）预分配，本模块只建档不发号。
"""
from __future__ import annotations

from datetime import date
from typing import Final

from flint.domain.models import JSON, Cluster
from flint.domain.protocols import LLMProvider
from flint.lineage.s23 import LineageDecision
from flint.obs import get_logger

NAMING_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1, "maxLength": 40},
        "category_id": {"type": "string", "minLength": 1},
    },
    "required": ["name", "category_id"],
    "additionalProperties": False,
}

_PROMPT_TEMPLATE = (
    "以下关键词构成一个新的热点簇，请给出简洁的簇名（<=20 字）并从候选大类中"
    "选择唯一 category_id。\n关键词：{keywords}\n候选大类：{categories}\n"
    "只输出符合 schema 的 JSON。"
)


def register_new_cluster(
    decision: LineageDecision,
    keyword_canonicals: list[str],
    allowed_category_ids: list[str],
    provider: LLMProvider,
    day: date,
    fallback_category_id: str,
) -> tuple[Cluster, bool]:
    """Returns (cluster, degraded). Never raises on naming failure."""
    if not keyword_canonicals:
        raise ValueError("a new cluster needs at least one keyword canonical")
    name: str | None = None
    category_id: str | None = None
    degraded = False
    prompt = _PROMPT_TEMPLATE.format(
        keywords=", ".join(keyword_canonicals),
        categories=", ".join(allowed_category_ids),
    )
    try:
        payload = provider.generate_structured(prompt, NAMING_SCHEMA, max_retries=2)
        raw_name = payload.get("name")
        raw_category = payload.get("category_id")
        if (
            isinstance(raw_name, str)
            and raw_name.strip()
            and isinstance(raw_category, str)
            and raw_category in allowed_category_ids
        ):
            name = raw_name.strip()
            category_id = raw_category
    except Exception as err:  # noqa: BLE001 — degradation path must not block
        get_logger("flint.lineage.s5").warning(
            "cluster_naming_failed",
            cluster_id=decision.new_cluster_id,
            error=str(err),
        )
    if name is None or category_id is None:
        degraded = True
        name = keyword_canonicals[0]
        category_id = fallback_category_id

    cluster = Cluster(
        cluster_id=decision.new_cluster_id,
        canonical_name=name,
        category_id=category_id,
        centroid=list(decision.centroid),
        status="active",
        first_seen=day,
        last_active=day,
        parent_cluster_ids=list(decision.parent_cluster_ids),
        merged_into=None,
        aliases=list(keyword_canonicals),
    )
    return cluster, degraded
