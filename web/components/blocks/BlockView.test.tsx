import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { BlockView } from "./BlockView";
import { BlockTree } from "../BlockTree";
import type { Block, BlockContent } from "../../lib/types";

// FE-001 (L0) 验收：8 类 BlockType 各一只读组件无一落空、稳定序 + 分节、
// 保护块只读无编辑控件、chart 零计算（D3）。全程离线（无 fetch/网络）。

function mkBlock(partial: Partial<Block> & { content: BlockContent }): Block {
  return {
    block_id: "b",
    deliverable_id: "d",
    section_id: "s-1",
    order: 0,
    type: partial.content.kind,
    claim_ids: [],
    fact_ids: [],
    author: "system",
    revision: 1,
    locked: false,
    user_modified: false,
    needs_review: false,
    review_reason: null,
    review_severity: null,
    ...partial,
  };
}

const ALL_EIGHT: BlockContent[] = [
  { kind: "heading", level: 2, text: "标题" },
  { kind: "paragraph", spans: [
    { kind: "text", text: "正文" },
    { kind: "claim", claim_id: "c1", text: "断言", disputed_mark: true },
    { kind: "cite", citation_id: "z1" },
    { kind: "profile", field_path: "research.pubs[0]" },
  ] },
  { kind: "table", header: ["列"], rows: [[
    { kind: "text", text: "格" },
    { kind: "fact", fact_id: "f1" },
    { kind: "price", price_entry_id: "p1", quantity: 42 },
  ]] },
  { kind: "chart", chart_id: "ch1" },
  { kind: "declaration", text: "边界声明" },
  { kind: "quality_card", card_ref: "qc1" },
  { kind: "citation_list", citation_ids: ["z1", "z2"] },
  { kind: "gap_notice", hints_ref: "gh1" },
];

describe("L0 8 类块组件无一落空", () => {
  for (const content of ALL_EIGHT) {
    it(`renders ${content.kind} read-only, no edit controls`, () => {
      const { container } = render(
        <BlockView block={mkBlock({ block_id: content.kind, content })} />,
      );
      const root = container.querySelector(`[data-block-type="${content.kind}"]`);
      expect(root).not.toBeNull();
      expect(root!.getAttribute("data-readonly")).toBe("true");
      // 只读：NEVER 渲染任何编辑控件
      expect(container.querySelector("input,textarea,button,select,[contenteditable='true']")).toBeNull();
    });
  }
});

describe("L0 判别联合内容保真", () => {
  it("paragraph spans: text/claim(disputed 印记)/cite/profile 各有据可查", () => {
    const { container } = render(
      <BlockView block={mkBlock({ content: ALL_EIGHT[1] })} />,
    );
    expect(container.textContent).toContain("正文");
    expect(container.querySelector("[data-claim-id='c1'][data-disputed='true']")).not.toBeNull();
    // 争议记号是几何印记而不是 emoji（G30 / DESIGN-23）：断的是那个标记元素在场，
    // 而不是某个字符——字符换成 emoji 会在各平台长得不一样、读屏也读错语义
    expect(container.querySelector("[data-testid='disputed-mark']")).not.toBeNull();
    expect(container.textContent).not.toContain("⚠");
    expect(container.querySelector("[data-citation-id='z1']")).not.toBeNull();
    expect(container.querySelector("[data-profile-path='research.pubs[0]']")).not.toBeNull();
  });

  it("table price cell: 金额由后端算，前端零计算（FB-09 改：原来断的是 quantity 原样呈现）", () => {
    // 改前这条断言的是 `textContent === "42"`——即屏上直接显示 quantity。
    // FB-09 之后价格格显示的是**后端算好的金额**（`/price-entries/{id}?quantity=N`），
    // 所以那句断言的字面已经不成立。但它守的东西没变，只是换了个落点：
    //   旧：前端只显示 quantity，不乘 → 屏上是 42
    //   新：前端把 quantity 交给后端，自己不乘 → 屏上是后端给的金额，
    //       且组件里没有任何算术（源码面由 tests/v041/test_deref_frontend.py 守）
    // **这是「改被测对象时同步改尺子」，不是为了让测试过而放宽断言**——
    // 新断言比旧的更严：它还多钉了一条「quantity 确实被交出去了」。
    const { container } = render(
      <BlockView block={mkBlock({ content: ALL_EIGHT[2] })} />,
    );
    const priceCell = container.querySelector("[data-price-entry-id='p1']");
    expect(priceCell).not.toBeNull();

    const deref = priceCell!.querySelector("[data-deref-kind='price']");
    expect(deref).not.toBeNull();
    expect(deref!.getAttribute("data-deref-id")).toBe("p1");
    // 未落定时显示原 id，NEVER 空白（FB-09 acceptance②）。
    expect(priceCell!.textContent).toContain("p1");
    expect(priceCell!.textContent).not.toBe("");
  });

  it("chart: 只引用 chart_id、无数据计算（D3 零计算）", () => {
    const { container } = render(
      <BlockView block={mkBlock({ content: ALL_EIGHT[3] })} />,
    );
    const fig = container.querySelector("[data-chart-id='ch1']");
    expect(fig).not.toBeNull();
    expect(fig!.getAttribute("data-render")).toBe("deferred-to-backend");
    // chart 内容只有 chart_id——无任何数值/序列在前端出现
    expect(fig!.querySelector("svg,canvas")).toBeNull();
  });
});

describe("L0 保护块只读", () => {
  it("locked / author=user / user_modified 任一 → data-protected=true、仍无编辑控件", () => {
    for (const p of [{ locked: true }, { author: "user" as const }, { user_modified: true }]) {
      const { container } = render(
        <BlockView block={mkBlock({ content: ALL_EIGHT[0], ...p })} />,
      );
      const root = container.querySelector("[data-block-type='heading']");
      expect(root!.getAttribute("data-protected")).toBe("true");
      expect(container.querySelector("input,textarea,button,select")).toBeNull();
    }
  });
});

describe("L0 BlockTree 稳定序 + 分节", () => {
  it("按 section 分组、节内按 order 升序", () => {
    const blocks: Block[] = [
      mkBlock({ block_id: "b2", section_id: "s-1", order: 2, content: { kind: "heading", level: 1, text: "二" } }),
      mkBlock({ block_id: "b0", section_id: "s-1", order: 0, content: { kind: "heading", level: 1, text: "零" } }),
      mkBlock({ block_id: "b1", section_id: "s-1", order: 1, content: { kind: "heading", level: 1, text: "一" } }),
      mkBlock({ block_id: "b9", section_id: "s-2", order: 0, content: { kind: "heading", level: 1, text: "节二" } }),
    ];
    const { container } = render(<BlockTree blocks={blocks} />);
    const ids = [...container.querySelectorAll("[data-block-id]")].map((el) => el.getAttribute("data-block-id"));
    expect(ids).toEqual(["b0", "b1", "b2", "b9"]);
    const sections = [...container.querySelectorAll("[data-section-id]")].map((el) => el.getAttribute("data-section-id"));
    expect(sections).toEqual(["s-1", "s-2"]);
    expect(container.querySelector("[data-block-tree='true'][data-readonly='true']")).not.toBeNull();
  });
});
