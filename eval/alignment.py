"""对齐抽检一致率评测（M2-046，PDD v0.3.1 §7 M2 线：>=95%）。

- 从金标 20 例抽 (claim, citation) 对（确定序、上限可配），跑 stage1 对齐
  判定，与金标真值表对照 → 一致率报告。
- provider 可注入：离线 CI 用真值脚本化 provider 验管道（E9：LLM 输出不进
  CI 断言）；每夜评测同一 harness 换真 LLM。
- <95% 退出码 1（§7 写死的 M2 线，默认 0.95 可配）。
运行：python -m eval.alignment [--cases PATH] [--min 0.95] [--cap 50]
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval.gate1 import DEFAULT_CASES, TruthAligner
from flint.align.stage1 import LLMCitationAligner
from flint.domain.models import JSON, Doc
from flint.evidence.compliance import restore_docs

MIN_CONSISTENCY = 0.95


@dataclass(frozen=True)
class SampledPair:
    case_id: str
    claim: str
    doc: Doc
    truth: str


def sample_pairs(cases: list[dict[str, Any]], cap: int = 50) -> list[SampledPair]:
    pairs: list[SampledPair] = []
    for case in cases:
        docs_by_id = {
            d.doc_id: d
            for d in restore_docs(
                json.dumps(case["docs"], ensure_ascii=False).encode("utf-8")
            )
        }
        for item in [*case["refute_claims"], *case["support_claims"]]:
            key = f"{item['claim']}|{item['doc_id']}"
            pairs.append(
                SampledPair(
                    case_id=str(case["case_id"]),
                    claim=str(item["claim"]),
                    doc=docs_by_id[str(item["doc_id"])],
                    truth=str(case["alignment_truth"][key]),
                )
            )
    return pairs[:cap]


def run_alignment_eval(
    cases: list[dict[str, Any]], provider: Any = None, cap: int = 50
) -> JSON:
    truth_table: dict[str, str] = {}
    for case in cases:
        truth_table.update(case["alignment_truth"])
    aligner = LLMCitationAligner(
        provider=provider if provider is not None else TruthAligner(truth_table)
    )
    sampled = sample_pairs(cases, cap)
    disagreements = []
    for pair in sampled:
        predicted = aligner.align(pair.claim, pair.doc, stage="verdict")
        if predicted != pair.truth:
            disagreements.append(
                {"case_id": pair.case_id, "doc_id": pair.doc.doc_id,
                 "truth": pair.truth, "predicted": predicted}
            )
    consistency = (
        (len(sampled) - len(disagreements)) / len(sampled) if sampled else 1.0
    )
    return {
        "sampled": len(sampled),
        "consistency": consistency,
        "disagreements": disagreements,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="alignment consistency eval")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--min", type=float, default=MIN_CONSISTENCY)
    parser.add_argument("--cap", type=int, default=50)
    args = parser.parse_args(argv)
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))["cases"]
    report = run_alignment_eval(cases, cap=args.cap)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if report["consistency"] < args.min else 0


if __name__ == "__main__":
    raise SystemExit(main())
