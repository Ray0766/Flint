/**
 * REDESIGN-03 · 干预页每一行都要让人认得出是哪一块。
 *
 * ## 改前
 *
 * 干预页的摘要只认 `content.text`。带 span 的段落、表格、图表、质量卡、引用列表、缺口提示
 * 都没有这个字段，于是那六类块在屏上只剩三个键：用户在给一块看不见的东西点「再生成」。
 *
 * ## 摘要 NEVER 改写原文
 *
 * 摘要是**从头截一段**。段落里遇到第一个没有文字的 span（引用标、画像引用）就停——
 * 把后面的文字接上来的话，屏上会是一句原文里并不存在的话（中间的引用被悄悄拿掉了）。
 */
import { describe, expect, it } from "vitest";

import { blockExcerpt } from "./blockExcerpt";
import type { Block, BlockContent } from "./types";

function blockOf(content: BlockContent): Block {
  return {
    block_id: "b-1", deliverable_id: "d-1", section_id: "s-1", order: 0,
    type: content.kind, content, claim_ids: [], fact_ids: [],
    author: "system", revision: 1, locked: false, user_modified: false,
    needs_review: false, review_reason: null, review_severity: null,
  } as Block;
}

describe("blockExcerpt · 摘要是原文的开头一段", () => {
  it("标题与声明：原样给出自己的文字", () => {
    expect(blockExcerpt(blockOf({ kind: "heading", level: 2, text: "市场与需求" })))
      .toBe("市场与需求");
    expect(blockExcerpt(blockOf({ kind: "declaration", text: "结论均以引用为准。" })))
      .toBe("结论均以引用为准。");
  });

  it("段落：把开头连续的文字 span 接起来（陈述 span 也是原文）", () => {
    const block = blockOf({
      kind: "paragraph",
      spans: [
        { kind: "text", text: "检索增强生成已有落地，" },
        { kind: "claim", claim_id: "c-1", text: "该方向已出现中试证据", disputed_mark: false },
        { kind: "text", text: "。" },
      ],
    });

    expect(blockExcerpt(block)).toBe("检索增强生成已有落地，该方向已出现中试证据。");
  });

  it("段落：遇到第一个没有文字的 span 就停，并标出后面还有", () => {
    const block = blockOf({
      kind: "paragraph",
      spans: [
        { kind: "text", text: "本节口径取自 " },
        { kind: "profile", field_path: "research.publications[0]" },
        { kind: "text", text: " 与别处。" },
      ],
    });

    const excerpt = blockExcerpt(block);

    expect(excerpt).toBe("本节口径取自 …");
    // 被拿掉引用之后接起来的那句话，原文里没有。
    expect(excerpt).not.toContain("与别处");
    // 内部路径 NEVER 上屏。
    expect(excerpt).not.toContain("research.publications");
  });

  it("表格：给表头（它是这张表自己的字）", () => {
    const block = blockOf({
      kind: "table", header: ["项", "事实", "单价×数量"],
      rows: [[{ kind: "text", text: "向量库托管" }, { kind: "fact", fact_id: "f-1" }]],
    });

    expect(blockExcerpt(block)).toBe("项 · 事实 · 单价×数量");
  });

  it("没有自己文字的块：摘要是空的，NEVER 拿内部引用号顶上", () => {
    expect(blockExcerpt(blockOf({ kind: "chart", chart_id: "chart-demo-cost" }))).toBe("");
    expect(blockExcerpt(blockOf({ kind: "quality_card", card_ref: "qc-1" }))).toBe("");
    expect(blockExcerpt(blockOf({ kind: "citation_list", citation_ids: ["cit-1"] }))).toBe("");
    expect(blockExcerpt(blockOf({ kind: "gap_notice", hints_ref: "sec-04" }))).toBe("");
  });

  it("超过上限就截断并加省略号，截下来的那段与原文开头逐字相同", () => {
    const text = "字".repeat(200);

    const excerpt = blockExcerpt(blockOf({ kind: "declaration", text }), 80);

    expect(excerpt).toBe(`${"字".repeat(80)}…`);
  });
});
