"""M3-025 acceptance tests: rule-A orchestration wiring.

Acceptance (tasks.json M3-025):
  - refute docs -> refute claim pairs -> non-empty rule-A input in gate1
    (M2 exit leftover 4 closed)
  - gold A-tier cases re-verified through the orchestration path (not just
    the rule layer)
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from eval.gate1 import TruthAligner
from flint.compose.refute_claims import build_refute_pairs, is_refute_evidence
from flint.domain.models import Doc, Query
from flint.jobs.gate1 import (
    Gate1Deps,
    _judge_payload,
    _validate_verdict,
    build_offline_deps,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"
FETCHED = datetime(2026, 7, 26, 12, 0, 0, tzinfo=UTC).isoformat()


def doc(doc_id: str, title: str, refute_flag: bool = False) -> Doc:
    meta: dict = {"fetched_at": FETCHED}
    if refute_flag:
        meta["refute_evidence"] = True
    return Doc(
        doc_id=doc_id, source_id="crossref", kind="paper", title=title,
        url=f"https://a/{doc_id}", published_at=date(2026, 1, 1),
        meta=meta, origin="retrieved", access="public",
    )


def test_pairs_only_from_refute_evidence_docs() -> None:
    docs = [
        doc("d-1", "solid state battery retraction notice"),
        doc("d-2", "solid state battery survey"),
        doc("d-3", "ordinary study", refute_flag=True),
    ]
    assert is_refute_evidence(docs[0]) and not is_refute_evidence(docs[1])
    pairs = build_refute_pairs(["固态电池"], docs)
    assert [d.doc_id for _c, d in pairs] == ["d-1", "d-3"]
    assert all("固态电池" in claim for claim, _d in pairs)
    assert "retraction notice" in pairs[0][0], "claim binds the doc title"


def test_orchestration_reaches_verdict_a_with_refute_evidence() -> None:
    """编排层可达 A：注入含证伪证据的 searcher，走 _judge_payload ->
    _validate_verdict 全链（非仅规则层）。"""
    base = build_offline_deps(dsn="postgresql://unused", repo_root=REPO_ROOT)

    def searcher(query: Query) -> list[Doc]:
        if query.intent == "refute":
            return [doc("d-ref", "failed replication of the approach")]
        if query.intent == "support":
            return [doc("d-sup", "adoption study")]
        return []  # no competitors

    deps = Gate1Deps(
        dsn=base.dsn, provider=base.provider, searcher=searcher,
        term_map=base.term_map, now=base.now,
    )
    keywords = ["固态电池"]
    from flint.jobs.gate1 import _plan_queries

    plan = _plan_queries(deps, keywords, "zh-CN")
    # `GATE1-DEDUP`：这里原先也自带一份取数循环（第三份抄本）。
    # 改成与 gate1 走同一对函数——取数只发生一次，且去重口径只有一处。
    from flint.jobs.gate1 import _fetch_docs_by_query, _flatten_docs

    docs_by_query = _fetch_docs_by_query(deps, plan)
    all_docs = _flatten_docs(plan, docs_by_query)
    judge = _judge_payload(deps, keywords, plan, all_docs, docs_by_query)
    assert judge["refute_claims"], "rule-A input is non-empty in orchestration"
    verdict = _validate_verdict(deps, judge, all_docs)
    assert verdict["verdict"] == "A_infeasible"
    assert "A_infeasible" in verdict["all_satisfied"]
    assert verdict["key_citation_ids"] == ["d-ref"]


def test_gold_a_tier_reverified_through_orchestration_path() -> None:
    """金标 A 档五例经 _validate_verdict（编排校验相位）复验。"""
    cases = json.loads(ASSET.read_text(encoding="utf-8"))["cases"]
    a_cases = [c for c in cases if c["tier"] == "A_infeasible"]
    assert len(a_cases) == 5

    from flint.competitor.signals import SignalEvaluation
    from flint.competitor.strength import judge_strength

    for case in a_cases:
        docs_by_id = {d["doc_id"]: d for d in case["docs"]}
        all_docs = [
            Doc(
                doc_id=d["doc_id"], source_id=d["source_id"], kind=d["kind"],
                title=d["title"], url=d["url"],
                published_at=date.fromisoformat(d["published_at"]),
                meta=d["meta"], origin=d["origin"], access=d["access"],
            )
            for d in docs_by_id.values()
        ]
        competitors = []
        for comp in case["competitors"]:
            evaluation = SignalEvaluation(evaluated=dict(comp["signals"]))
            competitors.append(
                {"name": comp["name"], "url": comp["url"],
                 "strength": judge_strength(evaluation),
                 "strength_signals": list(evaluation.fired)}
            )
        judge = {
            "refute_executed": case["refute_executed"],
            "refute_hit_rate": case["refute_hit_rate"],
            "executions": [
                {"query_text": e["query_text"], "executed": e["executed"],
                 "new": e["new"]}
                for e in case["coverage_executions"]
            ],
            "total_competitors": len(competitors),
            "competitors": competitors,
            "support_claims": case["support_claims"],
            "refute_claims": case["refute_claims"],
            "user_evidence_optin": case["user_evidence_optin"],
        }
        deps = Gate1Deps(
            dsn="postgresql://unused",
            provider=TruthAligner(dict(case["alignment_truth"])),
            searcher=lambda q: [],
            term_map=None,  # type: ignore[arg-type]
            now=datetime(2026, 7, 26, tzinfo=UTC),
        )
        verdict = _validate_verdict(deps, judge, all_docs)
        assert verdict["verdict"] == "A_infeasible", case["case_id"]
        assert verdict["all_satisfied"] == case["expected"]["all_satisfied"], (
            case["case_id"]
        )
