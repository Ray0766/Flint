"""M2-046 acceptance tests: alignment spot-check consistency (>=95%).

Acceptance (tasks.json M2-046):
  - sampled (claim, citation) pairs compared to gold truth, consistency report
  - <95% exits 1 (PDD 0.3.1 section-7 M2 line)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.alignment import MIN_CONSISTENCY, main, run_alignment_eval, sample_pairs
from flint.domain.models import JSON

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"


def load_cases() -> list[dict]:
    return list(json.loads(ASSET.read_text(encoding="utf-8"))["cases"])


class NoisyProvider:
    """每第 3 对翻转判定：制造 <95% 一致率的注入面。"""

    def __init__(self, truth: dict[str, str]) -> None:
        self.truth = truth
        self.calls = 0

    def generate(self, prompt: str, tools: list[JSON] | None) -> Any:
        raise NotImplementedError

    def generate_structured(self, prompt: str, schema: JSON, max_retries: int) -> JSON:
        claim = prompt.split("断言：", 1)[1].split("\n证据（doc_id=", 1)[0]
        doc_id = prompt.split("证据（doc_id=", 1)[1].split("）", 1)[0]
        actual = self.truth[f"{claim}|{doc_id}"]
        self.calls += 1
        if self.calls % 3 == 0:
            return {"alignment": "unsupported" if actual == "supports" else "supports"}
        return {"alignment": actual}


def test_line_is_95_percent() -> None:
    assert MIN_CONSISTENCY == 0.95


def test_sampling_is_deterministic_and_capped() -> None:
    cases = load_cases()
    first = sample_pairs(cases, cap=10)
    second = sample_pairs(cases, cap=10)
    assert [(p.case_id, p.doc.doc_id) for p in first] == [
        (p.case_id, p.doc.doc_id) for p in second
    ]
    assert len(first) == 10


def test_truth_provider_full_consistency() -> None:
    report = run_alignment_eval(load_cases())
    assert report["sampled"] > 0
    assert report["consistency"] == 1.0
    assert report["disagreements"] == []


def test_noisy_provider_fails_line() -> None:
    cases = load_cases()
    truth: dict[str, str] = {}
    for case in cases:
        truth.update(case["alignment_truth"])
    report = run_alignment_eval(cases, provider=NoisyProvider(truth))
    assert report["consistency"] < 0.95
    assert report["disagreements"], "disagreements listed for audit"


def test_cli_exit_codes(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["consistency"] == 1.0
    assert main(["--min", "1.01"]) == 1, "unreachable line proves exit path"
