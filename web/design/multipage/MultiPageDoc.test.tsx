// DESIGN-19 验收：多页面文档（L0 概览 + 章节结构；375px 无横滚）。
//
// acceptance：**L0 概览+章节结构；375px 容器无横向滚动断言**。
//
// 为什么 375px 单独立一条：横向滚动在手机上是**看不见的丢失**——用户不知道右边
// 还有内容，他只会觉得这一段写得没头没尾。而横滚最常见的来源不是文字，
// 是某个写死宽度的容器（表格、代码块、图）。所以断言落在**容器的样式约束**上，
// 而不是靠人在真机上滑一遍。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { MOBILE_WIDTH_PX, MultiPageDoc, buildOutline } from "./MultiPageDoc";

const CODE = codeOnly(readFileSync(join(__dirname, "MultiPageDoc.tsx"), "utf8"));

const PAGES = [
  { pageId: "p-1", title: "概览", level: 0, html: "<h1>概览</h1>" },
  { pageId: "p-2", title: "市场", level: 1, html: "<h2>市场</h2>" },
  { pageId: "p-3", title: "竞品", level: 1, html: "<h2>竞品</h2>" },
];

describe("buildOutline（L0 + 章节结构）", () => {
  it("L0 是根，章节挂在它下面", () => {
    const outline = buildOutline(PAGES);

    expect(outline.overviewId).toBe("p-1");
    expect(outline.sectionIds).toEqual(["p-2", "p-3"]);
  });

  it("没有 L0 时如实说没有：NEVER 把第一章顶上来充当概览", () => {
    const outline = buildOutline(PAGES.slice(1));

    expect(outline.overviewId).toBeNull();
    expect(outline.sectionIds).toEqual(["p-2", "p-3"]);
    // 顶上来的话，用户点「概览」看到的是「市场」，而他以为那就是全文的开头
    expect(CODE).not.toMatch(/pages\[0\]/);
  });

  it("多个 L0 时取第一个并报出重复：结构错了要说出来", () => {
    const outline = buildOutline([
      ...PAGES,
      { pageId: "p-4", title: "另一个概览", level: 0, html: "<h1>x</h1>" },
    ]);

    expect(outline.overviewId).toBe("p-1");
    expect(outline.duplicateOverviewIds).toEqual(["p-4"]);
  });

  it("章节顺序照给定顺序：重排会让目录与正文对不上", () => {
    const outline = buildOutline([PAGES[2], PAGES[0], PAGES[1]]);

    expect(outline.sectionIds).toEqual(["p-3", "p-2"]);
  });
});

describe("MultiPageDoc（渲染）", () => {
  it("概览与章节各自成页，页数与输入一致", () => {
    render(<MultiPageDoc pages={PAGES} />);

    expect(screen.getByTestId("doc-overview")).toBeInTheDocument();
    expect(screen.getAllByTestId("doc-section")).toHaveLength(2);
    expect(screen.getByTestId("multipage-doc")).toHaveAttribute("data-page-count", "3");
  });

  it("目录逐条指向对应页", () => {
    render(<MultiPageDoc pages={PAGES} />);

    const nav = screen.getByTestId("doc-outline");
    const links = within(nav).getAllByTestId("doc-outline-item");

    expect(links.map((n) => n.getAttribute("data-page-id"))).toEqual([
      "p-1", "p-2", "p-3",
    ]);
  });

  it("375px 容器：宽度上限与禁横滚都写在样式约束里", () => {
    render(<MultiPageDoc pages={PAGES} />);

    const frame = screen.getByTestId("multipage-doc");
    expect(MOBILE_WIDTH_PX).toBe(375);
    expect(frame.style.maxWidth).toBe("100%");
    expect(frame.style.overflowX).toBe("hidden");
  });

  it("每一页内容也不许横向溢出：溢出的是页而不是外壳", () => {
    render(<MultiPageDoc pages={PAGES} />);

    for (const page of [
      screen.getByTestId("doc-overview"),
      ...screen.getAllByTestId("doc-section"),
    ]) {
      expect(page.style.maxWidth).toBe("100%");
      expect(page.style.overflowX).toBe("hidden");
    }
  });

  it("源码里没有写死的像素宽度：写死宽度正是横滚最常见的来源", () => {
    // 允许 375 出现在常量与断言口径里，但**不允许**作为容器宽度写死
    expect(CODE).not.toMatch(/width:\s*["']?\d+px/);
    expect(CODE).not.toMatch(/minWidth:\s*["']?\d+px/);
  });

  it("空页集不渲染空壳", () => {
    render(<MultiPageDoc pages={[]} />);

    expect(screen.queryByTestId("multipage-doc")).toBeNull();
  });

  it("页面内容逐字进入（承 DESIGN-02 零构建）", () => {
    render(<MultiPageDoc pages={PAGES} />);

    expect(screen.getByTestId("doc-overview").getAttribute("srcdoc")).toBe(
      "<h1>概览</h1>",
    );
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
