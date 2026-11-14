// DESIGN-06 验收：工具调用时间线（30+ 折叠态 ≤40px；展开可回看全量）。
//
// acceptance：**30+ 调用折叠态高度 ≤40px（样式断言）；展开可回看全量**。
//
// 为什么要折叠：一轮设计生成可能调几十次工具。全量铺开的话，用户想看的那段
// 生成文字会被推到几屏之外——而工具调用是**过程**，不是他要读的东西。
// 但过程必须**可回看**：出了问题时「它到底做了什么」是唯一能查的线索，
// 折叠 NEVER 等于丢弃。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { COLLAPSED_MAX_HEIGHT_PX, ToolTimeline } from "./ToolTimeline";

const CODE = codeOnly(readFileSync(join(__dirname, "ToolTimeline.tsx"), "utf8"));

function calls(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    id: `call-${i}`,
    tool: i % 2 === 0 ? "search_docs" : "read_file",
    arguments: { q: `查询 ${i}` },
    ok: i !== 7,
  }));
}

describe("ToolTimeline（工具调用时间线）", () => {
  it("30+ 调用默认折叠，且折叠态高度上限 ≤40px", () => {
    render(<ToolTimeline calls={calls(34)} />);

    const box = screen.getByTestId("tool-timeline-collapsed");
    expect(COLLAPSED_MAX_HEIGHT_PX).toBeLessThanOrEqual(40);
    expect(box.style.maxHeight).toBe(`${COLLAPSED_MAX_HEIGHT_PX}px`);
    expect(box.style.overflow).toBe("hidden");
  });

  it("折叠态说得出被折了多少：一句「已折叠」等于什么都没说", () => {
    render(<ToolTimeline calls={calls(34)} />);

    const summary = screen.getByTestId("tool-timeline-summary");
    expect(summary).toHaveAttribute("data-count", "34");
    expect(summary.textContent).toContain("34");
  });

  it("展开可回看全量：34 条一条不少", () => {
    render(<ToolTimeline calls={calls(34)} />);

    fireEvent.click(screen.getByTestId("tool-timeline-toggle"));

    const rows = screen.getAllByTestId("tool-timeline-row");
    expect(rows).toHaveLength(34);
    expect(rows[0]).toHaveAttribute("data-call-id", "call-0");
    expect(rows[33]).toHaveAttribute("data-call-id", "call-33");
  });

  it("展开后没有高度上限：回看时 NEVER 还卡在 40px 里", () => {
    render(<ToolTimeline calls={calls(34)} />);

    fireEvent.click(screen.getByTestId("tool-timeline-toggle"));

    expect(screen.queryByTestId("tool-timeline-collapsed")).toBeNull();
    expect(screen.getByTestId("tool-timeline-expanded").style.maxHeight).toBe("");
  });

  it("少量调用不折叠：三条也折起来的话，用户要多点一次才能看见本就该看见的东西", () => {
    render(<ToolTimeline calls={calls(3)} />);

    expect(screen.queryByTestId("tool-timeline-collapsed")).toBeNull();
    expect(screen.getAllByTestId("tool-timeline-row")).toHaveLength(3);
  });

  it("失败的调用在折叠态也点得出来：出问题时那正是要找的一条", () => {
    render(<ToolTimeline calls={calls(34)} />);

    const summary = screen.getByTestId("tool-timeline-summary");
    expect(summary).toHaveAttribute("data-failed", "1");
    // 全成功时不显示失败计数，NEVER 挂一个恒亮的 0
    render(<ToolTimeline calls={calls(34).map((c) => ({ ...c, ok: true }))} />);
    expect(screen.getAllByTestId("tool-timeline-summary")[1]).toHaveAttribute(
      "data-failed", "0",
    );
  });

  it("每行带得出工具名与成败：回看要能一眼扫过去", () => {
    render(<ToolTimeline calls={calls(34)} />);
    fireEvent.click(screen.getByTestId("tool-timeline-toggle"));

    const row = screen
      .getAllByTestId("tool-timeline-row")
      .find((n) => n.getAttribute("data-call-id") === "call-7");

    expect(row).toHaveAttribute("data-tool", "read_file");
    expect(row).toHaveAttribute("data-ok", "false");
    expect(within(row as HTMLElement).getByTestId("tool-timeline-tool").textContent)
      .toBe("read_file");
  });

  it("参数不在折叠态里渲染：把几十条参数塞进 DOM 只为让它们不可见", () => {
    render(<ToolTimeline calls={calls(34)} />);

    expect(screen.queryByText(/查询 12/)).toBeNull();
  });

  it("空列表不渲染空壳：一个没有调用的时间线什么都不该占", () => {
    render(<ToolTimeline calls={[]} />);

    expect(screen.queryByTestId("tool-timeline")).toBeNull();
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
