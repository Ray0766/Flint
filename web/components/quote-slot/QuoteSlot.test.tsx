// I18N-05 验收：译文引用必带原文展开；无原文数据时只显原文槽。
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QuoteSlot, type QuoteDisplay } from "./QuoteSlot";

const ORIGINAL = "量産ラインは２０２７年に稼働する見込み。";
const display: QuoteDisplay = {
  text: "The production line is expected to start in 2027.",
  translated: true,
  translator: "identity@v1",
  source_field: "quote_span",
};

describe("QuoteSlot", () => {
  it("译文呈现时必带展开控件（B10）", () => {
    render(<QuoteSlot quoteSpan={ORIGINAL} display={display} />);
    expect(screen.getByTestId("quote-translated").textContent).toBe(display.text);
    expect(screen.getByTestId("quote-expand")).toBeTruthy();
  });

  it("展开后渲染 source_field 指向的原文字节", () => {
    render(<QuoteSlot quoteSpan={ORIGINAL} display={display} />);
    fireEvent.click(screen.getByTestId("quote-expand"));
    const original = screen.getByTestId("quote-original");
    expect(original.textContent).toBe(ORIGINAL);          // 逐字，含全角数字
    expect(original).toHaveAttribute("data-source-field", "quote_span");
  });

  it("展开态可收起，且 aria-expanded 如实反映", () => {
    render(<QuoteSlot quoteSpan={ORIGINAL} display={display} />);
    const button = screen.getByTestId("quote-expand");
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(button);
    expect(screen.queryByTestId("quote-original")).toBeNull();
  });

  it("无译文数据时只显原文槽，且不出现展开控件", () => {
    render(<QuoteSlot quoteSpan={ORIGINAL} />);
    expect(screen.getByTestId("quote-original-only").textContent).toBe(ORIGINAL);
    expect(screen.queryByTestId("quote-expand")).toBeNull();
  });

  it("原文 NEVER 被译文替代：展开前后原文字节一致", () => {
    render(<QuoteSlot quoteSpan={ORIGINAL} display={display} />);
    fireEvent.click(screen.getByTestId("quote-expand"));
    expect(screen.getByTestId("quote-original").textContent).toBe(ORIGINAL);
    expect(screen.getByTestId("quote-translated").textContent).not.toBe(ORIGINAL);
  });
});
