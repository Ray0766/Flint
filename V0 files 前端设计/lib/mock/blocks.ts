// 2.7 深度报告 L0 · GET /deliverables/{deliverable_id}/blocks
// ⚠ 只读事实源：逐字取自《前端功能说明》2.7 示例 JSON。
// 五个 block 覆盖：locked / advisory+disputed / blocking / chart 占位 / gap_notice。
import type { BlocksResponse, DeliverableMeta, ErrorBody } from "../types";

export const reportBlocks: BlocksResponse = {
  deliverable_id: "del-demo7c1-report",
  blocks: [
    {
      block_id: "blk-001",
      deliverable_id: "del-demo7c1-report",
      section_id: "sec-intro",
      order: 0,
      type: "declaration",
      content: { kind: "declaration", text: "本报告结论均以引用为准，未引用处为推测。" },
      claim_ids: [],
      fact_ids: [],
      author: "system",
      revision: 1,
      locked: true,            // 保护块：只读，钉在顶部，无任何控件
      user_modified: false,
      needs_review: false,
      review_reason: null,
      review_severity: null,
    },
    {
      block_id: "blk-002",
      deliverable_id: "del-demo7c1-report",
      section_id: "sec-market",
      order: 0,
      type: "paragraph",
      content: {
        kind: "paragraph",
        spans: [
          { kind: "text", text: "固态电池家储市场" },
          { kind: "claim", claim_id: "clm-01", text: "该方向已有中试证据", disputed_mark: true },
          { kind: "cite", citation_id: "cit-arxiv-2507-01234" },
        ],
      },
      claim_ids: ["clm-01"],
      fact_ids: [],
      author: "system",
      revision: 2,
      locked: false,
      user_modified: false,
      needs_review: true,
      review_reason: "fact_disputed",
      review_severity: "advisory",   // 可折叠，不挡导出
    },
    {
      block_id: "blk-003",
      deliverable_id: "del-demo7c1-report",
      section_id: "sec-cost",
      order: 0,
      type: "table",
      content: {
        kind: "table",
        header: ["项", "事实", "单价×数量"],
        rows: [
          [
            { kind: "text", text: "电芯" },
            { kind: "fact", fact_id: "fact-cell-cost" },
            { kind: "price", price_entry_id: "pe-cell-2026", quantity: 100.0 }, // 原样呈现，不做任何计算
          ],
        ],
      },
      claim_ids: [],
      fact_ids: ["fact-cell-cost"],
      author: "system",
      revision: 1,
      locked: false,
      user_modified: false,
      needs_review: true,
      review_reason: "fact_removed",
      review_severity: "blocking",   // 阻塞标 + 挡导出；--spark 的唯一出场
    },
    {
      block_id: "blk-004",
      deliverable_id: "del-demo7c1-report",
      section_id: "sec-cost",
      order: 1,
      type: "chart",
      content: { kind: "chart", chart_id: "chart-cost-trend" }, // 只有 id，无数据点
      claim_ids: [],
      fact_ids: [],
      author: "system",
      revision: 1,
      locked: false,
      user_modified: false,
      needs_review: false,
      review_reason: null,
      review_severity: null,
    },
    {
      block_id: "blk-005",
      deliverable_id: "del-demo7c1-report",
      section_id: "sec-gap",
      order: 0,
      type: "gap_notice",
      content: { kind: "gap_notice", hints_ref: "sec-gap-hints" }, // 解引用接口未建
      claim_ids: [],
      fact_ids: [],
      author: "user",          // 保护块：只读
      revision: 1,
      locked: false,
      user_modified: false,
      needs_review: false,
      review_reason: null,
      review_severity: null,
    },
  ],
};

export const reportMeta: DeliverableMeta = {
  deliverable_id: "del-demo7c1-report",
  type: "report",
  version: 1,
  ledger_version: 1,
  reproducible: true,
};

/** 导出命中 409：用 detail.blocking_block_ids 高亮待处理块 */
export const exportBlockedError: ErrorBody = {
  code: "EXPORT_BLOCKED",
  message: "存在未处理的阻塞复核，无法导出",
  detail: { blocking_block_ids: ["blk-003"] },
};

/** pdf / pack 依赖缺失时的 503 */
export const serviceUnavailableError: ErrorBody = {
  code: "SERVICE_UNAVAILABLE",
  message: "PDF 渲染依赖不可用",
  detail: null,
};
