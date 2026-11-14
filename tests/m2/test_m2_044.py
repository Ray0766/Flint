"""M2-044 acceptance tests: gold case asset (20 cases).

Acceptance (tasks.json M2-044):
  - each of A/B/C/D has >=4 cases and >=1 crossing major categories
  - every case's evidence is fixture-inlined, offline replayable
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from fixtures._generate_goldcases import build
from flint.domain.models import Doc
from flint.evidence.compliance import check_provenance, restore_docs

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"

TIERS = ("A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient")


def load_cases() -> list[dict]:
    return list(json.loads(ASSET.read_text(encoding="utf-8"))["cases"])


def test_twenty_cases_four_per_tier_cross_category() -> None:
    cases = load_cases()
    assert len(cases) == 20
    by_tier: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        by_tier[case["tier"]].append(case)
    assert sorted(by_tier) == sorted(TIERS)
    for tier in TIERS:
        assert len(by_tier[tier]) >= 4, f"{tier} needs >=4 cases"
        categories = {c["category"] for c in by_tier[tier]}
        assert len(categories) >= 2, f"{tier} needs >=1 cross-major-category case"


def test_asset_matches_generator_deterministically() -> None:
    on_disk = json.loads(ASSET.read_text(encoding="utf-8"))
    assert on_disk == build(), "asset regenerates byte-identically (offline replay)"
    assert build() == build(), "generator is deterministic"


def test_every_case_offline_complete() -> None:
    for case in load_cases():
        docs_by_id = {d["doc_id"]: d for d in case["docs"]}
        referenced = (
            [c["doc_id"] for c in case["refute_claims"]]
            + [c["doc_id"] for c in case["support_claims"]]
            + [i for comp in case["competitors"] for i in comp["source_doc_ids"]]
        )
        for doc_id in referenced:
            assert doc_id in docs_by_id, f"{case['case_id']}: dangling {doc_id}"

        payload = json.dumps(case["docs"], ensure_ascii=False).encode("utf-8")
        docs = restore_docs(payload)
        assert all(isinstance(d, Doc) for d in docs)
        assert check_provenance(docs) == [], f"{case['case_id']}: provenance violation"

        for claims in (case["refute_claims"], case["support_claims"]):
            for item in claims:
                key = f"{item['claim']}|{item['doc_id']}"
                assert key in case["alignment_truth"], f"missing truth for {key}"


def test_expected_shape_and_verdict_consistency() -> None:
    for case in load_cases():
        expected = case["expected"]
        assert expected["all_satisfied"], "all_satisfied never empty"
        assert expected["verdict"] == expected["all_satisfied"][0]
        assert expected["verdict"] in TIERS
        assert case["tier"] == expected["verdict"], "tier field mirrors expected verdict"
        for comp in case["competitors"]:
            assert set(comp["signals"]) == {
                "funded_or_scaled", "mature_pricing",
                "same_target_user", "active_last_12m",
            }
