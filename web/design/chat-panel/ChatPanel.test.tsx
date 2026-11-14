// DESIGN-01 验收（前端半）：对话面板 + SSE 流式渲染。
//
// acceptance①「delta 边到边渲染 NEVER 等整回合（流式断言）」。
//
// 为什么必须边到边：等整回合再显示，用户面对的是一个几十秒不动的界面——
// 他不知道是在想、还是卡住了、还是自己没点上。流式的价值不在快，在**可见**。
//
// 流式断言的关键是**在中途断言**：只在最后比对完整文本的话，一个「攒够了一次性渲染」
// 的实现同样会绿。所以这里每推一段就查一次页面。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { ChatPanel, type DeltaSource } from "./ChatPanel";

const CODE = codeOnly(readFileSync(join(__dirname, "ChatPanel.tsx"), "utf8"));

/** 手动可控的 delta 源：测试自己决定什么时候推下一段。 */
function manualSource(): DeltaSource & { push: (f: string) => void; end: () => void } {
  let onDelta: (fragment: string) => void = () => {};
  let onDone: () => void = () => {};
  return {
    subscribe(handlers) {
      onDelta = handlers.onDelta;
      onDone = handlers.onDone;
      return () => {};
    },
    push(fragment: string) {
      act(() => onDelta(fragment));
    },
    end() {
      act(() => onDone());
    },
  };
}

describe("ChatPanel（流式渲染）", () => {
  it("每来一段就渲染一段：中途查得到半截文本", () => {
    const source = manualSource();
    render(<ChatPanel source={source} />);

    source.push("半導体材料の");
    expect(screen.getByTestId("chat-answer").textContent).toBe("半導体材料の");

    source.push("新工法が");
    expect(screen.getByTestId("chat-answer").textContent).toBe("半導体材料の新工法が");

    source.push("量産段階に入った");
    expect(screen.getByTestId("chat-answer").textContent).toBe(
      "半導体材料の新工法が量産段階に入った",
    );
  });

  it("流式中就有「正在生成」态：用户看得出它在动，不是卡住", () => {
    const source = manualSource();
    render(<ChatPanel source={source} />);

    source.push("一段");
    expect(screen.getByTestId("chat-streaming")).toBeInTheDocument();

    source.end();
    expect(screen.queryByTestId("chat-streaming")).toBeNull();
  });

  it("结束后文本与逐段拼出来的逐字相同：流式不改变内容", () => {
    const source = manualSource();
    render(<ChatPanel source={source} />);

    const parts = ["一", "二", "三", "四"];
    for (const p of parts) source.push(p);
    source.end();

    expect(screen.getByTestId("chat-answer").textContent).toBe(parts.join(""));
  });

  it("零段就结束时不显示空回合：那是「没有回答」而不是「回答是空字符串」", () => {
    const source = manualSource();
    render(<ChatPanel source={source} />);

    source.end();

    expect(screen.queryByTestId("chat-answer")).toBeNull();
    expect(screen.getByTestId("chat-empty")).toBeInTheDocument();
  });

  it("同一条流重渲染不重订，卸载时退订：NEVER 留一条没人收的流", () => {
    const unsubscribe = vi.fn();
    const subscribe = vi.fn().mockReturnValue(unsubscribe);
    const source = { subscribe };                 // 同一个对象：模拟正常调用方
    const { unmount, rerender } = render(<ChatPanel source={source} />);

    rerender(<ChatPanel source={source} />);
    expect(subscribe).toHaveBeenCalledTimes(1);   // 重渲染不该再订一次（会收到重复片段）

    unmount();
    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("换了一条流就换订阅：旧的退掉、新的订上", () => {
    const unsubA = vi.fn();
    const sourceA = { subscribe: vi.fn().mockReturnValue(unsubA) };
    const sourceB = { subscribe: vi.fn().mockReturnValue(vi.fn()) };
    const { rerender } = render(<ChatPanel source={sourceA} />);

    rerender(<ChatPanel source={sourceB} />);

    // 换会话却仍收着上一条流，用户会看到别的会话的文字流进这一屏
    expect(unsubA).toHaveBeenCalledTimes(1);
    expect(sourceB.subscribe).toHaveBeenCalledTimes(1);
  });

  it("面板不自己开 EventSource：流由调用方注入（H4 一条通道）", () => {
    // 组件里 new 一个 EventSource 就等于绕开既有 JobEventStream 另开一条流
    for (const forbidden of ["EventSource", "fetch(", "WebSocket"]) {
      expect(CODE).not.toContain(forbidden);
    }
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
