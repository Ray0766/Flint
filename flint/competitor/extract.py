"""竞品记录抽取（M2-030；Doc → 结构化竞品实体前身）。

- LLM 结构化抽取（schema：name/url 硬必填 + source_doc_ids 溯源），复用
  M2-003 重试/降级环。
- 硬校验：url 必须 http(s) 可达形态（B 档「各有可达来源」素材面）；
  source_doc_ids 必须指向输入 Doc（防幻觉溯源）；归一名去重（首见保序）。
- 强度判定归 M2-032——本层产出 CompetitorRecord 前身，不产冻结 Competitor。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from flint.domain.models import JSON, Doc
from flint.domain.protocols import LLMProvider
from flint.evidence.competitor import normalize_competitor_name

COMPETITOR_SCHEMA: Final[JSON] = {
    "type": "object",
    "properties": {
        "competitors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "url": {"type": "string", "minLength": 1},
                    "source_doc_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "url"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["competitors"],
    "additionalProperties": False,
}

_PROMPT = (
    "从以下产品/竞品文档中抽取竞品记录。每条给出 name、url（官网或产品页）、"
    "source_doc_ids（引用的输入文档 doc_id 列表）。只输出符合 schema 的 JSON。\n"
    "{docs}"
)


class ExtractionError(Exception):
    pass


@dataclass(frozen=True)
class CompetitorRecord:
    name: str
    url: str
    source_doc_ids: list[str] = field(default_factory=list)


def extract_competitors(
    provider: LLMProvider, docs: list[Doc], max_retries: int = 2
) -> list[CompetitorRecord]:
    doc_lines = "\n".join(
        f"- doc_id={d.doc_id} | {d.title} | {d.url} | {d.meta.get('description', '')}"
        for d in docs
    )
    payload = provider.generate_structured(
        _PROMPT.format(docs=doc_lines), COMPETITOR_SCHEMA, max_retries
    )
    known_ids = {d.doc_id for d in docs}
    records: list[CompetitorRecord] = []
    seen_names: set[str] = set()
    for item in payload["competitors"]:
        url = str(item["url"])
        if not url.startswith(("http://", "https://")):
            raise ExtractionError(
                f"competitor {item['name']!r} lacks a reachable web source: {url!r}"
            )
        for doc_id in item.get("source_doc_ids", []):
            if doc_id not in known_ids:
                raise ExtractionError(
                    f"competitor {item['name']!r} cites unknown doc {doc_id!r}"
                )
        normalized = normalize_competitor_name(str(item["name"]))
        if normalized in seen_names:
            continue
        seen_names.add(normalized)
        records.append(
            CompetitorRecord(
                name=str(item["name"]),
                url=url,
                source_doc_ids=list(item.get("source_doc_ids", [])),
            )
        )
    return records
