// DESIGN-14 验收：演示模式（全屏 / 隐 chrome / 方向键翻页；退出恢复原态）。
//
// acceptance：**三行为齐全；退出恢复原态**。
//
// 「退出恢复原态」是这张卡最容易做漏的一半：演示完回到编辑器，若侧栏没回来、
// 滚动位置丢了、全屏没退，用户就得自己把工作台重新拼一遍——而他刚才只是
// 想给人看一眼。演示模式是**一次借用**，借完要原样还回去。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { PresentMode } from "./PresentMode";

const CODE = codeOnly(readFileSync(join(__dirname, "PresentMode.tsx"), "utf8"));

const PAGES = ["<h1>第一页</h1>", "<h1>第二页</h1>", "<h1>第三页</h1>"];

/** 假全屏 API：jsdom 没有真的全屏，记录进出即可。 */
function fakeFullscreen() {
  const calls: string[] = [];
  return {
    calls,
    api: {
      enter: () => {
        calls.push("enter");
      },
      exit: () => {
        calls.push("exit");
      },
    },
  };
}

describe("PresentMode（演示模式）", () => {
  it("进入即全屏、隐 chrome：三行为的前两条", () => {
    const { calls, api } = fakeFullscreen();
    render(<PresentMode pages={PAGES} fullscreen={api} onExit={vi.fn()} />);

    expect(calls).toEqual(["enter"]);
    expect(screen.getByTestId("present-mode")).toHaveAttribute("data-chrome", "hidden");
    expect(screen.queryByTestId("present-editor-chrome")).toBeNull();
  });

  it("方向键翻页：右前进、左后退", () => {
    const { api } = fakeFullscreen();
    render(<PresentMode pages={PAGES} fullscreen={api} onExit={vi.fn()} />);

    expect(screen.getByTestId("present-page")).toHaveAttribute("data-index", "0");

    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByTestId("present-page")).toHaveAttribute("data-index", "1");

    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByTestId("present-page")).toHaveAttribute("data-index", "0");
  });

  it("到头不循环：第一页再往左、最后一页再往右都停住", () => {
    const { api } = fakeFullscreen();
    render(<PresentMode pages={PAGES} fullscreen={api} onExit={vi.fn()} />);

    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByTestId("present-page")).toHaveAttribute("data-index", "0");

    for (let i = 0; i < 5; i += 1) fireEvent.keyDown(window, { key: "ArrowRight" });
    // 循环回第一页会让演示者以为自己按多了一次，讲错顺序
    expect(screen.getByTestId("present-page")).toHaveAttribute("data-index", "2");
  });

  it("当前页渲染的是那一页的内容", () => {
    const { api } = fakeFullscreen();
    render(<PresentMode pages={PAGES} fullscreen={api} onExit={vi.fn()} />);

    fireEvent.keyDown(window, { key: "ArrowRight" });

    expect(screen.getByTestId("present-page").getAttribute("srcdoc")).toBe(PAGES[1]);
  });

  it("Esc 退出：退全屏 + 通知调用方恢复原态", () => {
    const { calls, api } = fakeFullscreen();
    const onExit = vi.fn();
    render(<PresentMode pages={PAGES} fullscreen={api} onExit={onExit} />);

    fireEvent.keyDown(window, { key: "Escape" });

    expect(calls).toEqual(["enter", "exit"]);
    expect(onExit).toHaveBeenCalledTimes(1);
  });

  it("卸载也退全屏：NEVER 把浏览器留在全屏里", () => {
    const { calls, api } = fakeFullscreen();
    const { unmount } = render(
      <PresentMode pages={PAGES} fullscreen={api} onExit={vi.fn()} />,
    );

    unmount();

    expect(calls).toEqual(["enter", "exit"]);
  });

  it("退出后不再吃键盘：方向键该还给编辑器", () => {
    const { api } = fakeFullscreen();
    const { unmount } = render(
      <PresentMode pages={PAGES} fullscreen={api} onExit={vi.fn()} />,
    );
    unmount();

    const after = vi.fn();
    window.addEventListener("keydown", after);
    fireEvent.keyDown(window, { key: "ArrowRight" });

    expect(after).toHaveBeenCalledTimes(1);   // 事件正常抵达，没有被吞
    window.removeEventListener("keydown", after);
  });

  it("空页集不进演示：没有内容可讲时 NEVER 黑一屏", () => {
    const { calls, api } = fakeFullscreen();
    render(<PresentMode pages={[]} fullscreen={api} onExit={vi.fn()} />);

    expect(screen.queryByTestId("present-mode")).toBeNull();
    expect(calls).toEqual([]);
  });

  it("演示层不改内容：它只是换一种方式显示同一份产物", () => {
    for (const banned of ["applyEdit", "patchSource", "innerHTML", "setProperty"]) {
      expect(CODE).not.toContain(banned);
    }
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
