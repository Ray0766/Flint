"""判 D 漏检率评测（M2-047，PDD v0.3.1 §7 M2 线：<=10%）。

- 漏检定义：金标可检索到证据（expected != D）却被判 D 的比例——
  「信息明明够却说信息不足」是产品可信度的直接损伤面。
- 输入复用 eval.gate1 的逐例结果；>10% 退出码 1（默认 0.10 可配）。
运行：python -m eval.missed_d [--cases PATH] [--max 0.10]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.gate1 import DEFAULT_CASES, CaseResult, run_eval
from flint.domain.models import JSON

MAX_MISSED_RATE = 0.10


def missed_d_report(results: list[CaseResult]) -> JSON:
    retrievable = [r for r in results if r.expected_verdict != "D_insufficient"]
    missed = [
        r for r in retrievable if r.predicted_verdict == "D_insufficient"
    ]
    rate = len(missed) / len(retrievable) if retrievable else 0.0
    return {
        "retrievable_cases": len(retrievable),
        "missed_d": [
            {"case_id": r.case_id, "expected": r.expected_verdict} for r in missed
        ],
        "missed_rate": rate,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="missed-D rate eval")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--max", type=float, default=MAX_MISSED_RATE)
    args = parser.parse_args(argv)
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    report = missed_d_report(run_eval(cases))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if report["missed_rate"] > args.max else 0


if __name__ == "__main__":
    raise SystemExit(main())
