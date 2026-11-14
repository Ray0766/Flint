/**
 * REDESIGN-03 · 干预页：每一行都认得出是哪一块，争议理由那个框说得出自己是什么。
 *
 * 改前六类块（带引用的段落、表格、图表、质量卡、引用列表、缺口提示）在这一屏上没有任何内容，
 * 只有「锁定 / 再生成 / 一个没有名字的输入框 / 争议」。
 */
import { render } from "@testing-library/react";
import { Suspense, act } from "react";
import { describe, expect, it, vi } from "vitest";

import zh from "../../messages/zh.json";
import InterventionsPage from "../../app/deliverables/[id]/interventions/page";

const base = {
  deliverable_id: "d-1", section_id: "s-1", claim_ids: [], fact_ids: [],
  author: "system", revision: 1, locked: false, user_modified: false,
  needs_review: false, review_reason: null, review_severity: null,
};

const BLOCKS = [
  { ...base, block_id: "b-head", order: 0, type: "heading",
    content: { kind: "heading", level: 2, text: "市场与需求" } },
  { ...base, block_id: "b-para", order: 1, type: "paragraph",
    content: { kind: "paragraph", spans: [
      { kind: "text", text: "检索增强生成已有落地，" },
      { kind: "cite", citation_id: "cit-demo-1" },
    ] } },
  { ...base, block_id: "b-table", order: 2, type: "table",
    content: { kind: "table", header: ["项", "事实"], rows: [] } },
  { ...base, block_id: "b-chart", order: 3, type: "chart",
    content: { kind: "chart", chart_id: "chart-demo-cost" } },
  { ...base, block_id: "b-locked", order: 4, type: "declaration", locked: true,
    content: { kind: "declaration", text: "结论均以引用为准。" } },
];

vi.mock("../../lib/useScreenData", () => ({
  useScreenData: () => ({
    state: { kind: "ready", data: { deliverable_id: "d-1", blocks: BLOCKS } },
    refetch: () => undefined,
  }),
}));

async function renderPage(): Promise<HTMLElement> {
  let container!: HTMLElement;
  await act(async () => {
    ({ container } = render(
      <Suspense fallback={null}>
        <InterventionsPage params={Promise.resolve({ id: "d-1" })} />
      </Suspense>,
    ));
  });
  return container;
}

const row = (c: HTMLElement, id: string): HTMLElement =>
  c.querySelector(`.intervention-row[data-block-id="${id}"]`) as HTMLElement;

describe("干预页 · 每一行都认得出是哪一块（REDESIGN-03）", () => {
  it("每一行都有块类型：原值在 data-block-type 上，屏上是人话", async () => {
    const c = await renderPage();

    for (const block of BLOCKS) {
      const kind = row(c, block.block_id).querySelector("[data-block-type]") as HTMLElement;
      expect(kind, block.block_id).toBeTruthy();
      expect(kind.getAttribute("data-block-type")).toBe(block.type);
      expect(kind.textContent).toBe(
        (zh as Record<string, string>)[`enum.block_type.${block.type}`]);
      // 原值 NEVER 当标签。
      expect(kind.textContent).not.toBe(block.type);
    }
  });

  it("带引用的段落与表格有摘要；图表没有自己的字，只留类型", async () => {
    const c = await renderPage();

    expect(row(c, "b-para").querySelector(".intervention-row__excerpt")?.textContent)
      .toBe("检索增强生成已有落地，…");
    expect(row(c, "b-table").querySelector(".intervention-row__excerpt")?.textContent)
      .toBe("项 · 事实");
    expect(row(c, "b-chart").querySelector(".intervention-row__excerpt")).toBeNull();
    // 内部引用号 NEVER 上屏。
    expect(c.textContent).not.toContain("chart-demo-cost");
    expect(c.textContent).not.toContain("cit-demo-1");
  });

  it("争议理由那个框有名字：读屏读得出，空着时看得见一句提示", async () => {
    const c = await renderPage();

    const reason = row(c, "b-head").querySelector(
      '[data-testid="dispute-reason"]') as HTMLTextAreaElement;

    expect(reason.getAttribute("aria-label")).toBe(zh["block.dispute.reason_label"]);
    expect(reason.getAttribute("placeholder")).toBe(zh["block.dispute.reason_placeholder"]);
  });

  it("受保护的块照旧没有动作键，只说原因", async () => {
    const c = await renderPage();

    const locked = row(c, "b-locked");
    expect(locked.getAttribute("data-protected")).toBe("true");
    expect(locked.querySelector("[data-intervention-panel]")).toBeNull();
    expect(locked.querySelector("[data-protected-reason]")?.textContent)
      .toBe(zh["intervention.protected.locked"]);
  });
});
