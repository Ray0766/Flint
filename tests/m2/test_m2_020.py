"""M2-020 acceptance tests: refute retrieval template families.

Acceptance (tasks.json M2-020):
  - five families (limitations/failure/replication/retraction/discontinued)
    each have a case
  - intent=refute activates all five families
"""
from __future__ import annotations

import pytest

from flint.retrieval.refute_templates import REFUTE_FAMILIES, refute_queries


def test_five_families_defined() -> None:
    assert sorted(REFUTE_FAMILIES) == [
        "discontinued", "failure", "limitations", "replication", "retraction",
    ]


@pytest.mark.parametrize(
    ("family", "marker"),
    [
        ("limitations", "limitations"),
        ("failure", "failure"),
        ("replication", "replication"),
        ("retraction", "retraction"),
        ("discontinued", "discontinued"),
    ],
)
def test_each_family_produces_a_query(family: str, marker: str) -> None:
    queries = refute_queries("solid-state battery", locale="en")
    match = [q for q in queries if marker in q.text]
    assert match, f"family {family} must contribute a query"
    assert all("solid-state battery" in q.text for q in match)


def test_refute_intent_activates_all_five() -> None:
    queries = refute_queries("solid-state battery", locale="en")
    assert len(queries) == 5
    assert all(q.intent == "refute" for q in queries)
    assert all(q.locale == "en" for q in queries)


def test_source_kinds_match_family_targets() -> None:
    by_marker = {q.text: q.source_kinds for q in refute_queries("x", locale="en")}
    retraction = next(k for k in by_marker if "retraction" in k)
    assert "paper" in by_marker[retraction]
    discontinued = next(k for k in by_marker if "discontinued" in k)
    assert {"repo", "news", "product"} & set(by_marker[discontinued])
