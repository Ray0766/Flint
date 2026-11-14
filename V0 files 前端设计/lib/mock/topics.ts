// 2.4 主题列表 · GET /projects/{project_id}/topics
// ⚠ 只读事实源：逐字取自《前端功能说明》2.4 示例 JSON。
// 含 speculative=true 与 false 各一，用于降权态对照。
import type { TopicsResponse, ComboCreateResponse } from "../types";

export const topics: TopicsResponse = {
  project_id: "proj-demo7c1",
  chosen_topic_id: "topic-demo7c1-1",
  topics: [
    {
      topic_id: "topic-demo7c1-1",
      seed_id: "seed-demo7c1",
      one_liner: "固态电池 × 家储的低成本集成路径",
      target_user_tag: "户用储能集成商",
      form_factor_tag: "硬件+BOM工具",
      why_now: {
        claim: "2026 年固态电解质中试线密集落地",
        speculative: false,
        evidences: [
          { event: "某厂中试线投产", event_date: "2026-06-20", citation_id: "cit-arxiv-2507-01234" },
        ],
      },
      keyword_mapping: { 固态电池: ["solid-state", "solid electrolyte"] },
    },
    {
      topic_id: "topic-demo7c1-2",
      seed_id: "seed-demo7c1",
      one_liner: "钠离子作为备用降本方案",
      target_user_tag: "户用储能集成商",
      form_factor_tag: "选型指南",
      why_now: {
        claim: "钠电成本或于两年内与锂交叉",
        speculative: true,   // evidences 为空 → 推测标，抑制溯源入口
        evidences: [],
      },
      keyword_mapping: { 钠离子: ["sodium-ion"] },
    },
  ],
};

/** 2.3 combo 响应，degraded=true 样例 → 标注「部分主题为降级生成」 */
export const comboCreated: ComboCreateResponse = {
  project_id: "proj-demo7c1",
  topic_ids: ["topic-demo7c1-1", "topic-demo7c1-2", "topic-demo7c1-3"],
  degraded: true,
};
