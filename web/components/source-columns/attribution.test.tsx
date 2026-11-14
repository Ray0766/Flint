/**
 * FIX-17：屏上看得出谁说的——判的是**渲染后的可见文本**。
 *
 * `HOTSPOT-07` 的 10 条判据（`SourceColumns.test.tsx`）用
 * `within(column).getByTestId(...)` 逐列查 `data-source-id`，判的是
 * 「来源 id 在 DOM 里且没混列」。**那条是对的、原样留着。**
 *
 * 但「在 DOM 里」与「在屏上」是两件事：读屏软件念不出一个属性，肉眼也看不见它。
 * 所以这一组一律走 `textContent` / `getByText`，`NEVER 只断言 data-* 属性在`。
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceColumns } from "./SourceColumns";
import { sourceName } from "./sourceName";
import zh from "../../messages/zh.json";

const messages = zh as Record<string, string>;

// 库里那条真实的两源分歧簇（`c-20260629-108`）：两个源说了不同的词，
// 而它们**同属未归区**——地区那一列在这里帮不上任何忙。
const TWO_SOURCES_ONE_REGION = [
  { sourceId: "ghtrend", region: "", text: "bci" },
  { sourceId: "gtrends", region: "", text: "脑机接口" },
];

describe("两条说法并排时，屏上写得出谁说的", () => {
  it("每条陈述前面有一个**看得见**的来源名", () => {
    render(<SourceColumns statements={TWO_SOURCES_ONE_REGION} />);

    const rows = screen.getAllByTestId("source-statement");
    expect(rows).toHaveLength(2);
    for (const row of rows) {
      const who = within(row).getByTestId("source-statement-who");
      expect(who.textContent?.trim()).not.toBe("");
    }
  });

  it("写的是那个源自己的名字，NEVER 张冠李戴", () => {
    render(<SourceColumns statements={TWO_SOURCES_ONE_REGION} />);

    const rows = screen.getAllByTestId("source-statement");
    const said = rows.map((row) => ({
      who: within(row).getByTestId("source-statement-who").textContent,
      text: within(row).getByTestId("source-statement-text").textContent,
    }));

    expect(said).toEqual([
      { who: messages["source.name.ghtrend"], text: "bci" },
      { who: messages["source.name.gtrends"], text: "脑机接口" },
    ]);
  });

  it("**改前的缺陷**：同区两条，只看屏上的字也分得出谁说的", () => {
    const { container } = render(<SourceColumns statements={TWO_SOURCES_ONE_REGION} />);

    // 整屏只有一列（两个源同属未归区）——地区帮不上忙的那种情形。
    expect(screen.getAllByTestId("source-column")).toHaveLength(1);

    // 而可见文本里两个来源名都在。改前这两句都读不到。
    const visible = container.textContent ?? "";
    expect(visible).toContain(messages["source.name.ghtrend"]);
    expect(visible).toContain(messages["source.name.gtrends"]);
  });

  it("署名与原话之间**看得出分界**（首版两格直接相邻，屏上连成一串）", () => {
    const { container } = render(<SourceColumns statements={TWO_SOURCES_ONE_REGION} />);

    // 改完看了一眼屏才发现的：`Google 趋势` + `脑机接口` 渲染出来是
    // 「Google 趋势脑机接口」——读者分不出名字在哪儿断开，
    // 而这个组件存在的理由正是让人分得出谁说的。
    const row = screen.getAllByTestId("source-statement")[1];
    expect(row.textContent).toBe(`${messages["source.name.gtrends"]}：脑机接口`);

    // 分隔符是**独立的一格**：样式失效时也分得开，且它 NEVER 混进原文。
    const sep = container.querySelector(".source-statement__sep");
    expect(sep?.textContent).toBe("：");
    expect(sep?.getAttribute("aria-hidden")).toBe("true");
    expect(screen.getAllByTestId("source-statement-text")[1].textContent).toBe("脑机接口");
  });

  it("认不出来的 id 原样显示，NEVER 编一个名字", () => {
    render(<SourceColumns statements={[
      { sourceId: "some-new-source", region: "CN", text: "一句话" },
    ]} />);

    const who = screen.getByTestId("source-statement-who");
    expect(who.textContent).toBe("some-new-source");
    // NEVER 说成「未知来源」：那把「我们没给它起过名」说成「这条来路不明」。
    expect(who.textContent).not.toContain("未知");
  });

  it("来源名 NEVER 顶替原文——两格各是各的", () => {
    render(<SourceColumns statements={TWO_SOURCES_ONE_REGION} />);

    const texts = screen.getAllByTestId("source-statement-text")
      .map((e) => e.textContent);
    expect(texts).toEqual(["bci", "脑机接口"]);      // 原文逐字，一个字没动
  });

  it("映射表本身：四个源各有各的名字，且互不相同", () => {
    const names = ["gtrends", "weibo", "ghtrend", "arxiv"].map(sourceName);

    expect(new Set(names).size).toBe(4);
    for (const name of names) expect(name).not.toMatch(/^source\.name\./);
  });
});
