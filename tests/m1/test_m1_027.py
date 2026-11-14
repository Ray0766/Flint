"""M1-027 acceptance tests: lineage step 5 — new-cluster registration + LLM naming.

Acceptance (tasks.json M1-027):
  - naming goes through schema validation
  - failure degrades to the top keyword without blocking
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from flint.domain.models import JSON, Cluster
from flint.lineage.s5 import NAMING_SCHEMA, register_new_cluster
from flint.lineage.s23 import LineageDecision

DAY = date(2026, 7, 23)
CATEGORIES = ["cat-ai", "cat-energy", "cat-robotics"]

DECISION = LineageDecision(
    kind="new",
    new_cluster_id="c-new-7",
    keyword_ids=["kw-1", "kw-2"],
    centroid=[1.0, 0.0, 0.0],
    parent_cluster_ids=["c-parent"],
)
KEYWORDS = ["solid-state battery", "sodium-ion battery"]


class GoodProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, JSON, int]] = []

    def generate(self, prompt: str, tools: list[JSON] | None) -> Any:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        self.calls.append((prompt, schema, max_retries))
        return {"name": "固态电池产业化", "category_id": "cat-energy"}


class WrongCategoryProvider(GoodProvider):
    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        return {"name": "某簇", "category_id": "cat-not-in-catalog"}


class EmptyNameProvider(GoodProvider):
    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        return {"name": "  ", "category_id": "cat-ai"}


class ExplodingProvider(GoodProvider):
    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        raise RuntimeError("structured output failed after retries")


def register(provider: GoodProvider) -> tuple[Cluster, bool]:
    return register_new_cluster(
        decision=DECISION,
        keyword_canonicals=KEYWORDS,
        allowed_category_ids=CATEGORIES,
        provider=provider,
        day=DAY,
        fallback_category_id="cat-ai",
    )


def test_naming_goes_through_schema_and_succeeds() -> None:
    provider = GoodProvider()
    cluster, degraded = register(provider)
    assert not degraded
    assert cluster.canonical_name == "固态电池产业化"
    assert cluster.category_id == "cat-energy"
    prompt, schema, max_retries = provider.calls[0]
    assert schema == NAMING_SCHEMA, "naming must use the frozen schema"
    assert max_retries == 2, "S2-3: at most 2 retries for structured output"
    assert "solid-state battery" in prompt
    assert "cat-energy" in prompt


def test_cluster_record_fields() -> None:
    cluster, _ = register(GoodProvider())
    assert isinstance(cluster, Cluster)
    assert cluster.cluster_id == "c-new-7"
    assert cluster.status == "active"
    assert cluster.first_seen == DAY
    assert cluster.last_active == DAY
    assert cluster.parent_cluster_ids == ["c-parent"]
    assert cluster.merged_into is None
    assert cluster.aliases == KEYWORDS
    assert cluster.centroid == DECISION.centroid


@pytest.mark.parametrize(
    "provider_cls", [WrongCategoryProvider, EmptyNameProvider, ExplodingProvider]
)
def test_failure_degrades_to_top_keyword_without_blocking(
    provider_cls: type[GoodProvider],
) -> None:
    cluster, degraded = register(provider_cls())
    assert degraded
    assert cluster.canonical_name == "solid-state battery", "top keyword fallback"
    assert cluster.category_id == "cat-ai", "fallback category applies"
    assert cluster.status == "active", "degradation never blocks registration"
