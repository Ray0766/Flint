// GRAPH-04 验收：拖动期零写请求；松手 1 次 PATCH；失败回弹原位。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GraphDrag } from "./GraphDrag";

/** 同步 rAF：把「下一帧」变成「立刻」，让测试能确定地驱动节流。 */
const syncRaf = (cb: () => void) => {
  cb();
  return 1;
};

function setup(persist = vi.fn(async () => {})) {
  render(
    <svg>
      <GraphDrag nodeId="n-1" initial={{ x: 10, y: 20 }} persist={persist} raf={syncRaf} />
    </svg>,
  );
  return { node: screen.getByTestId("graph-drag"), persist };
}

describe("GraphDrag", () => {
  it("拖动期**零写请求**", () => {
    const { node, persist } = setup();
    fireEvent.pointerDown(node);
    for (let i = 0; i < 20; i++) {
      fireEvent.pointerMove(node, { clientX: 10 + i, clientY: 20 + i });
    }
    expect(persist).not.toHaveBeenCalled();
  });

  it("松手恰一次落盘", async () => {
    const { node, persist } = setup();
    fireEvent.pointerDown(node);
    fireEvent.pointerMove(node, { clientX: 40, clientY: 50 });
    fireEvent.pointerUp(node, { clientX: 40, clientY: 50 });
    await waitFor(() => expect(persist).toHaveBeenCalledTimes(1));
    expect(persist).toHaveBeenCalledWith("n-1", { x: 40, y: 50 });
  });

  it("落盘失败回弹原位", async () => {
    const persist = vi.fn(async () => {
      throw new Error("网络错误");
    });
    const { node } = setup(persist);
    fireEvent.pointerDown(node);
    fireEvent.pointerMove(node, { clientX: 40, clientY: 50 });
    fireEvent.pointerUp(node, { clientX: 40, clientY: 50 });
    await waitFor(() => expect(node.getAttribute("data-x")).toBe("10"));
    expect(node.getAttribute("data-y")).toBe("20");
  });

  it("落盘成功则停在新位（阴性对照：回弹不是无条件的）", async () => {
    const { node } = setup();
    fireEvent.pointerDown(node);
    fireEvent.pointerUp(node, { clientX: 40, clientY: 50 });
    await waitFor(() => expect(node.getAttribute("data-x")).toBe("40"));
  });

  it("未按下时移动不生效（NEVER 幽灵拖动）", () => {
    const { node, persist } = setup();
    fireEvent.pointerMove(node, { clientX: 99, clientY: 99 });
    expect(node.getAttribute("data-x")).toBe("10");
    expect(persist).not.toHaveBeenCalled();
  });

  it("rAF 节流：一帧内多次移动只渲染一次最终位置", () => {
    const frames: Array<() => void> = [];
    render(
      <svg>
        <GraphDrag
          nodeId="n-2"
          initial={{ x: 0, y: 0 }}
          persist={vi.fn(async () => {})}
          raf={(cb) => {
            frames.push(cb);
            return frames.length;
          }}
        />
      </svg>,
    );
    const node = screen.getAllByTestId("graph-drag").at(-1)!;
    fireEvent.pointerDown(node);
    fireEvent.pointerMove(node, { clientX: 1, clientY: 1 });
    fireEvent.pointerMove(node, { clientX: 2, clientY: 2 });
    fireEvent.pointerMove(node, { clientX: 3, clientY: 3 });
    expect(frames).toHaveLength(1);   // 三次移动只排了一帧
  });
});
