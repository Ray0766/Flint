// HOTSPOT-07 验收：信息源 by_source 列渲染（分歧 fixture ≥2 列；合成句黑名单零命中）。
//
// 为什么「不合成」比「多列」更要紧：两国对同一件事说法不一致时，把它们揉成一句
// 「综合各国观点，总体而言……」读起来最顺，也最有害——读者失去了「谁说的」这个
// 唯一能判断可信度的东西，而那句综合结论**没有任何一个来源支持它**。
//
// 前端这一层是**复检**：后端 REGION-08 已经拦过一次，界面这一层再拦一次，
// 因为合成句最容易在渲染层被「顺手加一句摘要」重新引入。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceColumns, UNKNOWN_REGION_KEY } from "./SourceColumns";
import { SYNTHESIS_BLACKLIST } from "./synthesisBlacklist";

const REPO_ROOT = join(__dirname, "..", "..", "..");
const PY_SOURCE = join(REPO_ROOT, "flint", "region", "by_source_region.py");

// 分歧 fixture：两个地区对同一件事说法相反 —— 正是最想被「综合」掉的那种材料
const DISAGREEMENT = [
  { sourceId: "s-cn-1", region: "CN", text: "该技术路线已进入量产阶段" },
  { sourceId: "s-jp-1", region: "JP", text: "同技術は量産に至っていない" },
];

describe("SourceColumns（信息源分列）", () => {
  it("分歧 fixture 渲染 ≥2 列，每列标着自己的地区", () => {
    render(<SourceColumns statements={DISAGREEMENT} />);

    const columns = screen.getAllByTestId("source-column");
    expect(columns.length).toBeGreaterThanOrEqual(2);
    expect(columns.map((c) => c.getAttribute("data-region"))).toEqual(["CN", "JP"]);
  });

  it("每条陈述留在自己那一列，并带得出「谁说的」", () => {
    render(<SourceColumns statements={DISAGREEMENT} />);

    const [cn, jp] = screen.getAllByTestId("source-column");
    expect(within(cn).getByTestId("source-statement")).toHaveAttribute(
      "data-source-id",
      "s-cn-1",
    );
    expect(within(jp).getByTestId("source-statement")).toHaveAttribute(
      "data-source-id",
      "s-jp-1",
    );
  });

  it("原文逐字渲染：NEVER 翻译、NEVER 归一化（B9）", () => {
    render(<SourceColumns statements={DISAGREEMENT} />);

    const texts = screen.getAllByTestId("source-statement-text").map((n) => n.textContent);
    expect(texts).toEqual([DISAGREEMENT[0].text, DISAGREEMENT[1].text]);
  });

  it("合成句黑名单零命中：整棵渲染树里一句都不许有", () => {
    const { container } = render(<SourceColumns statements={DISAGREEMENT} />);
    const rendered = container.textContent ?? "";

    const hits = SYNTHESIS_BLACKLIST.filter((p) => new RegExp(p, "i").test(rendered));
    expect(hits).toEqual([]);
    // 阴性对照：这把尺子确实认得出合成句，否则「零命中」可能只是尺子不认
    expect(
      SYNTHESIS_BLACKLIST.filter((p) => new RegExp(p, "i").test("综合各国观点，总体而言……")),
    ).not.toEqual([]);
  });

  it("组件里没有摘要/结论槽：合成句最容易在渲染层被顺手加回来", () => {
    render(<SourceColumns statements={DISAGREEMENT} />);

    expect(screen.queryByTestId("source-summary")).toBeNull();
    expect(screen.queryByTestId("source-consensus")).toBeNull();
    const source = readFileSync(join(__dirname, "SourceColumns.tsx"), "utf8");
    expect(source).not.toMatch(/summary|consensus|synthes/i);
  });

  it("少数派不被合并：只有一条陈述的地区照样单独成列", () => {
    render(
      <SourceColumns
        statements={[
          ...DISAGREEMENT,
          { sourceId: "s-kr-1", region: "KR", text: "국내 도입은 검토 단계" },
        ]}
      />,
    );

    const columns = screen.getAllByTestId("source-column");
    expect(columns).toHaveLength(3);
    const kr = columns.find((c) => c.getAttribute("data-region") === "KR");
    expect(within(kr as HTMLElement).getAllByTestId("source-statement")).toHaveLength(1);
  });

  it("未归区的陈述单独成列且排在最后：NEVER 塞进某个地区，也 NEVER 丢掉", () => {
    render(
      <SourceColumns
        statements={[...DISAGREEMENT, { sourceId: "s-x", region: "", text: "来源地未知" }]}
      />,
    );

    const columns = screen.getAllByTestId("source-column");
    expect(columns).toHaveLength(3);
    expect(columns[2]).toHaveAttribute("data-region", UNKNOWN_REGION_KEY);
    expect(within(columns[2]).getByTestId("source-statement")).toHaveAttribute(
      "data-source-id",
      "s-x",
    );
  });

  it("空输入是明确的空态，不是一列空壳", () => {
    render(<SourceColumns statements={[]} />);

    expect(screen.queryAllByTestId("source-column")).toHaveLength(0);
    expect(screen.getByTestId("source-columns-empty")).toBeInTheDocument();
  });

  it("黑名单与后端 REGION-08 逐条同源：任一侧改动而另一侧没跟上即红", () => {
    const py = readFileSync(PY_SOURCE, "utf8");
    const block = py.match(/SYNTHESIS_BLACKLIST: tuple\[str, \.\.\.\] = \(([\s\S]*?)\n\)/);
    expect(block).not.toBeNull();
    const pyPatterns = [...(block as RegExpMatchArray)[1].matchAll(/r"([^"]+)"/g)].map(
      (m) => m[1],
    );

    expect(pyPatterns.length).toBeGreaterThan(0);
    expect(SYNTHESIS_BLACKLIST).toEqual(pyPatterns);
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    const source = readFileSync(join(__dirname, "SourceColumns.tsx"), "utf8");
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    expect(code).not.toMatch(/[一-鿿]/);
  });
});
