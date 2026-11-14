// GRAPH-13 验收：移动端只读（触摸端禁拖禁连，可看可开分析）。
//
// acceptance：**触摸端拖/连 handler 不挂载；双击开分析仍可用**。
//
// 为什么是「不挂载」而不是「挂了但拦住」：挂上再拦，手指按住节点时它仍然会
// 抢走滚动手势——用户想滑动页面，画布却以为他在拖节点，于是页面卡住不动。
// 触摸端最该保住的是**能滑能看**，而不是把桌面交互硬塞进来再逐个屏蔽。
//
// 只读不等于残废：看得见、点得开分析，这两件在手机上恰恰是最常做的。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { GraphMobile } from "./GraphMobile";

const CODE = codeOnly(readFileSync(join(__dirname, "GraphMobile.tsx"), "utf8"));

const NODES = [
  { nodeId: "n-1", label: "半導体材料", primary: true },
  { nodeId: "n-2", label: "供应链", primary: false },
];

function setup(touch: boolean, overrides: Record<string, unknown> = {}) {
  const onOpenAnalysis = vi.fn();
  const onPersistPosition = vi.fn();
  const onCreateEdge = vi.fn();
  render(
    <GraphMobile
      nodes={NODES}
      touch={touch}
      onOpenAnalysis={onOpenAnalysis}
      onPersistPosition={onPersistPosition}
      onCreateEdge={onCreateEdge}
      {...overrides}
    />,
  );
  return { onOpenAnalysis, onPersistPosition, onCreateEdge };
}

describe("GraphMobile（触摸端只读）", () => {
  it("触摸端：节点上不挂拖动 handler（不是挂了再拦）", () => {
    setup(true);

    const node = screen.getAllByTestId("graph-mobile-node")[0];
    expect(node).toHaveAttribute("data-draggable", "false");
    expect(node).not.toHaveAttribute("onpointerdown");
    // 手指按住节点时画布 NEVER 抢走滚动手势：touch-action 必须留给浏览器
    expect(node.getAttribute("style") ?? "").not.toContain("touch-action: none");
  });

  it("触摸端：拖动手势不产生任何落盘请求", () => {
    const { onPersistPosition } = setup(true);
    const node = screen.getAllByTestId("graph-mobile-node")[0];

    fireEvent.pointerDown(node, { clientX: 0, clientY: 0, pointerType: "touch" });
    fireEvent.pointerMove(node, { clientX: 80, clientY: 80, pointerType: "touch" });
    fireEvent.pointerUp(node, { clientX: 80, clientY: 80, pointerType: "touch" });

    expect(onPersistPosition).not.toHaveBeenCalled();
  });

  it("触摸端：连线入口不渲染，长按也建不出边", () => {
    const { onCreateEdge } = setup(true);

    expect(screen.queryByTestId("graph-mobile-connect")).toBeNull();
    const node = screen.getAllByTestId("graph-mobile-node")[0];
    fireEvent.pointerDown(node, { pointerType: "touch" });
    fireEvent.pointerUp(node, { pointerType: "touch" });

    expect(onCreateEdge).not.toHaveBeenCalled();
  });

  it("触摸端：双击开分析仍然可用（只读 ≠ 残废）", () => {
    const { onOpenAnalysis } = setup(true);

    fireEvent.doubleClick(screen.getAllByTestId("graph-mobile-node")[0]);

    expect(onOpenAnalysis).toHaveBeenCalledTimes(1);
    expect(onOpenAnalysis).toHaveBeenCalledWith("n-1");
  });

  it("触摸端：只读横幅说清为什么，NEVER 让按钮静静消失", () => {
    setup(true);

    const banner = screen.getByTestId("graph-mobile-readonly-banner");
    expect(banner.textContent).toBeTruthy();
    expect(banner.textContent).not.toBe("graph.mobile.readonly");
  });

  it("桌面端阴性对照：同一组件挂上拖动与连线，落盘照常发生", () => {
    const { onPersistPosition, onCreateEdge } = setup(false);

    const node = screen.getAllByTestId("graph-mobile-node")[0];
    expect(node).toHaveAttribute("data-draggable", "true");

    fireEvent.pointerDown(node, { clientX: 0, clientY: 0 });
    fireEvent.pointerMove(node, { clientX: 40, clientY: 40 });
    fireEvent.pointerUp(node, { clientX: 40, clientY: 40 });
    expect(onPersistPosition).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByTestId("graph-mobile-connect"));
    expect(onCreateEdge).toHaveBeenCalledTimes(1);
  });

  it("桌面端不出只读横幅：那条横幅只在真的只读时才有意义", () => {
    setup(false);
    expect(screen.queryByTestId("graph-mobile-readonly-banner")).toBeNull();
  });

  it("节点内容两端一致：只读的是交互，不是信息", () => {
    setup(true);
    const touchLabels = screen
      .getAllByTestId("graph-mobile-node")
      .map((n) => n.textContent);

    expect(touchLabels).toEqual(NODES.map((n) => n.label));
  });

  it("触摸判定由外部传入，组件不自己嗅探 UA", () => {
    // UA 嗅探会在平板、触屏笔记本上判错，而判错的代价是「这台机器上拖不动」
    for (const forbidden of ["navigator.userAgent", "ontouchstart", "maxTouchPoints"]) {
      expect(CODE).not.toContain(forbidden);
    }
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
