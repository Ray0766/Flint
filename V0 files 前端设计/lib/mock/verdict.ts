// 2.5 Gate 判定 · GET /jobs/{job_id}/verdict
// ⚠ 只读事实源：逐字取自《前端功能说明》2.5 示例 JSON。
// 样例形态：D_insufficient + 两类缺口 + unknown 竞品。
// A / B / C 三档在业务屏中不存在数据，只在 /styleguide 做视觉对照，禁止编造。
import type { VerdictResponse } from "../types";

export const verdictD: VerdictResponse = {
  job_id: "job-9d2e",
  verdict: {
    verdict: "D_insufficient",
    all_satisfied: ["D_insufficient"],
    key_citation_ids: [],
    rationale_fact_ids: [],
    competitors: [
      {
        name: "某储能 SaaS",
        url: "https://example.com/x",
        strength: "unknown",   // 须标为「未知」，视觉上不得与 weak 同形
        strength_signals: [],
        pricing: null,
      },
    ],
    constraints_checked: {
      order: ["A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"],
      demoted_by_alignment: false,
      rule_a: { satisfied: false, used_user_evidence_only: false, blocked_pending_optin: false },
      rule_b: { satisfied: false, by_count: false, by_strength: false, reachable_count: 1, strong_names: [] },
      rule_c: {
        satisfied: false,
        failed_conditions: ["coverage_not_met", "strong_or_unknown_competitor"],
        blocking_competitors: ["某储能 SaaS"],
      },
      gap_count: 2,
    },
    gaps: [
      {
        missing_what: "商业竞品市场源覆盖不足",
        cause: "missing_data",          // → 展示 suggested_sources + action
        suggested_sources: ["weibo", "news"],
        action: "search",
        target_count: 2,
        required_scope: null,
      },
      {
        missing_what: "需 owner 授权商业竞品市场源",
        cause: "missing_permission",    // → 展示 required_scope + 「请 owner 授权」
        suggested_sources: [],
        action: "request_permission",
        target_count: null,
        required_scope: "market_sources",
      },
    ],
  },
};
