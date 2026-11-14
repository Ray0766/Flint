"""M2-030 acceptance tests: competitor record extraction.

Acceptance (tasks.json M2-030):
  - Doc -> Competitor entity structured extraction (schema validated)
  - every competitor asserts >=1 reachable source
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from flint.competitor.extract import (
    COMPETITOR_SCHEMA,
    CompetitorRecord,
    ExtractionError,
    extract_competitors,
)
from flint.domain.models import JSON, Doc
from flint.llm.structured import StructuredOutputExhausted, validate_schema

FETCHED = datetime(2026, 7, 28, 12, 0, 0, tzinfo=UTC).isoformat()


def make_doc(i: int, name: str) -> Doc:
    return Doc(
        doc_id=f"doc-comp-{i}", source_id="products", kind="product",
        title=name, url=f"https://vendor{i}.example",
        published_at=None,
        meta={"fetched_at": FETCHED, "last_activity": "2026-06-01", "description": "x"},
        origin="retrieved", access="public",
    )


class ScriptedProvider:
    def __init__(self, payload: JSON | None = None, exhaust: bool = False) -> None:
        self.payload = payload
        self.exhaust = exhaust
        self.prompts: list[str] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> object:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.prompts.append(prompt)
        if self.exhaust:
            raise StructuredOutputExhausted(1 + max_retries, ["$.competitors[0].url: required"])
        assert self.payload is not None
        return self.payload


GOOD: JSON = {
    "competitors": [
        {"name": "Solid Vendor A", "url": "https://vendor0.example",
         "source_doc_ids": ["doc-comp-0"]},
        {"name": "Solid Vendor B", "url": "https://vendor1.example",
         "source_doc_ids": ["doc-comp-1"]},
    ]
}


def test_structured_extraction_with_schema() -> None:
    docs = [make_doc(0, "Solid Vendor A"), make_doc(1, "Solid Vendor B")]
    provider = ScriptedProvider(payload=GOOD)
    records = extract_competitors(provider, docs)
    assert [r.name for r in records] == ["Solid Vendor A", "Solid Vendor B"]
    assert all(isinstance(r, CompetitorRecord) for r in records)
    assert "Solid Vendor A" in provider.prompts[0], "docs feed the prompt"
    assert validate_schema(COMPETITOR_SCHEMA, GOOD) == []


def test_schema_requires_url() -> None:
    missing_url: JSON = {"competitors": [{"name": "X", "source_doc_ids": []}]}
    errors = validate_schema(COMPETITOR_SCHEMA, missing_url)
    assert errors and "required" in " ".join(errors)


def test_every_competitor_needs_reachable_source() -> None:
    bad: JSON = {
        "competitors": [
            {"name": "Ghost Vendor", "url": "ftp://not-web", "source_doc_ids": []}
        ]
    }
    with pytest.raises(ExtractionError, match="reachable"):
        extract_competitors(ScriptedProvider(payload=bad), [make_doc(0, "G")])


def test_source_doc_ids_must_exist_in_input() -> None:
    phantom: JSON = {
        "competitors": [
            {"name": "V", "url": "https://v.example", "source_doc_ids": ["doc-ghost"]}
        ]
    }
    with pytest.raises(ExtractionError, match="doc-ghost"):
        extract_competitors(ScriptedProvider(payload=phantom), [make_doc(0, "V")])


def test_exhaustion_propagates() -> None:
    with pytest.raises(StructuredOutputExhausted):
        extract_competitors(ScriptedProvider(exhaust=True), [make_doc(0, "V")])


def test_normalized_name_dedupe() -> None:
    doubled: JSON = {
        "competitors": [
            {"name": "Solid  Vendor A", "url": "https://vendor0.example",
             "source_doc_ids": ["doc-comp-0"]},
            {"name": "solid vendor a", "url": "https://mirror.example",
             "source_doc_ids": ["doc-comp-0"]},
        ]
    }
    records = extract_competitors(ScriptedProvider(payload=doubled), [make_doc(0, "A")])
    assert len(records) == 1, "normalized duplicate names collapse (first wins)"
