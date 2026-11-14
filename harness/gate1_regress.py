"""Gate① 回归 harness：金标 20 例离线全跑（M2-051，技术方案 E12）。

- 零联网（S2-7）：输入只有 assets/goldcases/goldcases.json，判定链
  （规则族 + 引擎 + 真值脚本化对齐）全在进程内——测试以 socket 禁用
  证明零网络。
- 三线合跑：金标精确率/召回率（M2-045）+ 对齐一致率 >=95%（M2-046）+
  判 D 漏检率 <=10%（M2-047）。
- 逐例 trace：docs/trace/goldcases/{case_id}.md——inputs 清单（证据/断言/
  竞品/覆盖面）+ 判定依据（预测 verdict / all_satisfied / C 档失败项 /
  与金标比对）；内容确定性（无时间戳，重跑字节稳定）。
- 退出码：任一例判错 或 一致率/漏检率破线 → 1（回归红）。
运行：python -m harness.gate1_regress
"""
from __future__ import annotations

import json
from pathlib import Path

from eval.alignment import MIN_CONSISTENCY, run_alignment_eval
from eval.gate1 import DEFAULT_CASES, CaseResult, metrics, run_eval
from eval.missed_d import MAX_MISSED_RATE, missed_d_report
from flint.domain.models import JSON

REPO_ROOT = Path(__file__).resolve().parents[1]
TRACE_DIR = REPO_ROOT / "docs" / "trace" / "goldcases"


def case_trace(case: JSON, result: CaseResult) -> str:
    comps = "\n".join(
        f"  - {c['name']}（{c['intended_strength']}）{c['url']}"
        for c in case["competitors"]
    ) or "  -（无）"
    coverage = "\n".join(
        f"  - {e['query_text']}: executed={e['executed']} 新增竞品={e['new']}"
        for e in case["coverage_executions"]
    )
    failed = "、".join(result.failed_conditions) or "（无）"
    match_mark = "一致" if result.verdict_match else "**不一致**"
    return f"""# 金标 trace：{result.case_id}

## inputs 清单
- 大类：{case["category"]}；关键词：{"、".join(case["keywords"])}
- 证据 docs：{len(case["docs"])} 条（内联 fixture，离线）
- 证伪断言：{len(case["refute_claims"])} 条；支持断言：{len(case["support_claims"])} 条
- user_provided 判 A optin：{case["user_evidence_optin"]}
- 竞品（意图强度）：
{comps}
- refute 已执行：{case["refute_executed"]}；相关率：{case["refute_hit_rate"]}
- 覆盖执行面：
{coverage}

## 判定依据
- 预测 verdict：{result.predicted_verdict}；all_satisfied：{result.predicted_all}
- C 档失败项：{failed}
- 金标 expected：{result.expected_verdict}；all_satisfied：{result.expected_all}
- 比对：{match_mark}
"""


def main() -> int:
    cases: list[JSON] = json.loads(
        DEFAULT_CASES.read_text(encoding="utf-8")
    )["cases"]
    results = run_eval(cases)
    report = metrics(results)
    alignment = run_alignment_eval(cases)
    missed = missed_d_report(results)

    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    by_id = {str(c["case_id"]): c for c in cases}
    for result in results:
        path = TRACE_DIR / f"{result.case_id}.md"
        path.write_text(case_trace(by_id[result.case_id], result), encoding="utf-8")

    all_match = all(r.verdict_match and r.all_satisfied_match for r in results)
    alignment_ok = alignment["consistency"] >= MIN_CONSISTENCY
    missed_ok = missed["missed_rate"] <= MAX_MISSED_RATE
    summary = {
        "cases": len(results),
        "verdict_matches": sum(r.verdict_match for r in results),
        "all_satisfied_matches": sum(r.all_satisfied_match for r in results),
        "macro_precision": report["macro_precision"],
        "macro_recall": report["macro_recall"],
        "alignment_consistency": alignment["consistency"],
        "missed_d_rate": missed["missed_rate"],
        "traces": len(results),
        "green": all_match and alignment_ok and missed_ok,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if summary["green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
