"""Gate① 金标评测：精确率/召回率（M2-045，PDD v0.3.1 §7 M2 线）。

- 逐例把金标场景喂进真实规则族（rule_a/b/c/d + engine.decide），对齐走
  真值表脚本化 provider（离线零 LLM，S2-7）；与金标 expected 对照。
- 指标：四档混淆矩阵 → 各档 precision/recall → macro 平均；报告 JSON。
- 线值 X/Y 配置化（--min-precision / --min-recall）；低于线退出码 1。
  初值待 owner 定（S4 Open Question 新登记，M2-052 签字时收口）——
  未传线值时只出报告不判死（exit 0）。
运行：python -m eval.gate1 [--cases PATH] [--min-precision X] [--min-recall Y]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from flint.align.stage1 import LLMCitationAligner
from flint.competitor.coverage import QueryExecution, assess_coverage
from flint.competitor.signals import SignalEvaluation
from flint.competitor.strength import judge_strength
from flint.domain.models import JSON, Competitor, Doc, StrengthSignal, Verdict
from flint.evidence.compliance import restore_docs
from flint.gate.engine import VERDICT_ORDER, decide
from flint.gate.rule_a import evaluate_rule_a
from flint.gate.rule_b import evaluate_rule_b
from flint.gate.rule_c import evaluate_rule_c
from flint.gate.rule_d import derive_gaps

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"


class TruthAligner:
    """对齐真值表脚本化 provider（金标附带真值；离线确定性）。"""

    def __init__(self, truth: dict[str, str]) -> None:
        self._truth = truth

    def generate(self, prompt: str, tools: list[JSON] | None) -> Any:
        raise RuntimeError("offline eval: free-form generation disabled")

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        claim = prompt.split("断言：", 1)[1].split("\n证据（doc_id=", 1)[0]
        doc_id = prompt.split("证据（doc_id=", 1)[1].split("）", 1)[0]
        return {"alignment": self._truth[f"{claim}|{doc_id}"]}


@dataclass
class CaseResult:
    case_id: str
    expected_verdict: str
    predicted_verdict: str
    expected_all: list[str]
    predicted_all: list[str]
    verdict_match: bool
    all_satisfied_match: bool
    failed_conditions: list[str] = field(default_factory=list)


def _competitors(case: dict[str, Any]) -> list[Competitor]:
    built: list[Competitor] = []
    for comp in case["competitors"]:
        evaluation = SignalEvaluation(
            evaluated={
                cast(StrengthSignal, k): v for k, v in comp["signals"].items()
            }
        )
        built.append(
            Competitor(
                name=str(comp["name"]),
                url=str(comp["url"]),
                strength=judge_strength(evaluation),
                strength_signals=list(evaluation.fired),
                pricing=None,
            )
        )
    return built


def _pairs(
    claims: list[dict[str, str]], docs_by_id: dict[str, Doc]
) -> list[tuple[str, Doc]]:
    return [(item["claim"], docs_by_id[item["doc_id"]]) for item in claims]


def run_case(case: dict[str, Any]) -> CaseResult:
    docs = restore_docs(
        json.dumps(case["docs"], ensure_ascii=False).encode("utf-8")
    )
    docs_by_id = {d.doc_id: d for d in docs}
    aligner = LLMCitationAligner(
        provider=TruthAligner(dict(case["alignment_truth"]))
    )
    competitors = _competitors(case)
    rule_a = evaluate_rule_a(
        aligner,
        _pairs(case["refute_claims"], docs_by_id),
        user_evidence_optin=bool(case["user_evidence_optin"]),
    )
    rule_b = evaluate_rule_b(competitors)
    coverage = assess_coverage(
        [
            QueryExecution(
                query_text=str(e["query_text"]),
                executed=bool(e["executed"]),
                new_competitors=int(e["new"]),
            )
            for e in case["coverage_executions"]
        ],
        total_competitors=len(competitors),
        hit_rate=float(case["refute_hit_rate"]),
    )
    rule_c = evaluate_rule_c(
        aligner,
        _pairs(case["support_claims"], docs_by_id),
        refute_executed=bool(case["refute_executed"]),
        refute_hit_rate=float(case["refute_hit_rate"]),
        coverage=coverage,
        competitors=competitors,
    )
    demoted = rule_a.demote_to_d or rule_c.demote_to_d
    lands_on_d = demoted or not (
        rule_a.satisfied or rule_b.satisfied or rule_c.satisfied
    )
    gaps = (
        derive_gaps(
            rule_c, coverage, competitors, missing_scopes=[],
            alignment_demoted=demoted,
        )
        if lands_on_d
        else []
    )
    verdict = decide(rule_a, rule_b, rule_c, gaps=gaps, competitors=competitors)
    expected = case["expected"]
    return CaseResult(
        case_id=str(case["case_id"]),
        expected_verdict=str(expected["verdict"]),
        predicted_verdict=verdict.verdict,
        expected_all=list(expected["all_satisfied"]),
        predicted_all=list(verdict.all_satisfied),
        verdict_match=verdict.verdict == expected["verdict"],
        all_satisfied_match=list(verdict.all_satisfied)
        == list(expected["all_satisfied"]),
        failed_conditions=list(rule_c.failed_conditions),
    )


def run_eval(cases: list[dict[str, Any]]) -> list[CaseResult]:
    return [run_case(case) for case in cases]


def metrics(results: list[CaseResult]) -> JSON:
    tiers: tuple[Verdict, ...] = VERDICT_ORDER
    per_tier: JSON = {}
    precisions: list[float] = []
    recalls: list[float] = []
    for tier in tiers:
        tp = sum(
            1 for r in results
            if r.predicted_verdict == tier and r.expected_verdict == tier
        )
        fp = sum(
            1 for r in results
            if r.predicted_verdict == tier and r.expected_verdict != tier
        )
        fn = sum(
            1 for r in results
            if r.predicted_verdict != tier and r.expected_verdict == tier
        )
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        per_tier[tier] = {"tp": tp, "fp": fp, "fn": fn,
                          "precision": precision, "recall": recall}
        precisions.append(precision)
        recalls.append(recall)
    mismatches = [
        {"case_id": r.case_id, "expected": r.expected_verdict,
         "predicted": r.predicted_verdict}
        for r in results
        if not r.verdict_match
    ]
    all_satisfied_mismatches = [
        {"case_id": r.case_id, "expected": r.expected_all,
         "predicted": r.predicted_all}
        for r in results
        if not r.all_satisfied_match
    ]
    return {
        "cases": len(results),
        "verdict_accuracy": sum(r.verdict_match for r in results) / len(results),
        "per_tier": per_tier,
        "macro_precision": sum(precisions) / len(precisions),
        "macro_recall": sum(recalls) / len(recalls),
        "mismatches": mismatches,
        "all_satisfied_mismatches": all_satisfied_mismatches,
    }


def below_lines(
    report: JSON, min_precision: float | None, min_recall: float | None
) -> bool:
    if min_precision is not None and report["macro_precision"] < min_precision:
        return True
    return min_recall is not None and report["macro_recall"] < min_recall


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="gate1 gold-set eval")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--min-precision", type=float, default=None)
    parser.add_argument("--min-recall", type=float, default=None)
    args = parser.parse_args(argv)
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    report = metrics(run_eval(cases))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if below_lines(report, args.min_precision, args.min_recall) else 0


if __name__ == "__main__":
    raise SystemExit(main())
