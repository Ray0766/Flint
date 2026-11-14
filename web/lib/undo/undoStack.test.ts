// GRAPH-10 验收：撤销栈共链（跨视图单栈，§6-H5）。
//
// acceptance①「图谱操作与既有视图共用一条链（全局栈实例唯一断言）」；
// acceptance②「跨视图交替操作后连续 undo 顺序正确」。
//
// 为什么必须是一条链：用户按 ⌘Z 时脑子里是**一条时间线**——他要撤的是「我刚才做的
// 那件事」，不管那件事发生在图谱上还是编辑器里。每个视图各留一条栈的话，
// 同一个 ⌘Z 在不同视图下撤掉的是不同时刻的操作，而用户并不知道自己此刻在哪条栈上。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { beforeEach, describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { clearUndo, getUndoStack, pushUndo, undo, undoDepth, UNDO_LIMIT } from "./undoStack";

const CODE = codeOnly(readFileSync(join(__dirname, "undoStack.ts"), "utf8"));

beforeEach(() => {
  clearUndo();
});

describe("undoStack（跨视图单栈）", () => {
  it("全局实例唯一：另一次 import 操作的是同一条栈（双向可见）", async () => {
    // 断的是**状态共享**而不是返回值同一：`getUndoStack()` 按设计回的是副本，
    // 用 toBe 比两次副本永远不等，那条红是判据错了不是实现错了。
    pushUndo({ view: "graph", label: "move-node", undo: vi.fn() });

    const again = await import("./undoStack");
    expect(again.undoDepth()).toBe(1);          // 这边推的，那边看得见

    await again.undo();
    expect(undoDepth()).toBe(0);                // 那边撤的，这边也看得见

    again.pushUndo({ view: "editor", label: "edit-block", undo: vi.fn() });
    expect(undoDepth()).toBe(1);
  });

  it("没有第二条栈可造：模块不导出工厂或类", () => {
    expect(CODE).not.toMatch(/export\s+(class|function\s+createUndo)/);
    expect(CODE).not.toMatch(/new\s+UndoStack/);
  });

  it("跨视图交替操作后，连续 undo 按时间倒序撤", async () => {
    const order: string[] = [];
    pushUndo({ view: "graph", label: "add-node", undo: () => void order.push("a") });
    pushUndo({ view: "editor", label: "edit-block", undo: () => void order.push("b") });
    pushUndo({ view: "graph", label: "add-edge", undo: () => void order.push("c") });
    pushUndo({ view: "library", label: "favorite", undo: () => void order.push("d") });

    await undo();
    await undo();
    await undo();
    await undo();

    expect(order).toEqual(["d", "c", "b", "a"]); // 一条时间线，不是每个视图各撤各的
    expect(undoDepth()).toBe(0);
  });

  it("undo 回报撤掉的是哪一条：调用方据此提示用户", async () => {
    pushUndo({ view: "graph", label: "add-edge", undo: vi.fn() });

    const entry = await undo();

    expect(entry?.view).toBe("graph");
    expect(entry?.label).toBe("add-edge");
  });

  it("空栈上 undo 返回 null 而不是抛错：新开一页按 ⌘Z 不该炸", async () => {
    expect(await undo()).toBeNull();
    expect(undoDepth()).toBe(0);
  });

  it("撤销动作失败时**留在栈上**：用户还能再试一次", async () => {
    const failing = vi.fn().mockRejectedValue(new Error("boom"));
    pushUndo({ view: "graph", label: "move-node", undo: failing });

    await expect(undo()).rejects.toThrow("boom");

    expect(undoDepth()).toBe(1); // 先执行后出栈：失败就没出栈，NEVER 悄悄吞掉那一步
  });

  it("异步撤销被等到底：下一次 undo 不会插到上一次前面", async () => {
    const order: string[] = [];
    const slow = () =>
      new Promise<void>((resolve) => {
        setTimeout(() => {
          order.push("slow");
          resolve();
        }, 5);
      });
    pushUndo({ view: "graph", label: "slow", undo: slow });
    pushUndo({ view: "editor", label: "fast", undo: () => void order.push("fast") });

    await undo();
    await undo();

    expect(order).toEqual(["fast", "slow"]);
  });

  it("上限满了丢**最旧**的：刚做的那步永远撤得回来", () => {
    for (let i = 0; i < UNDO_LIMIT + 5; i += 1) {
      pushUndo({ view: "graph", label: `op-${i}`, undo: vi.fn() });
    }

    expect(undoDepth()).toBe(UNDO_LIMIT);
    const stack = getUndoStack();
    expect(stack[stack.length - 1].label).toBe(`op-${UNDO_LIMIT + 4}`);
    expect(stack[0].label).toBe("op-5"); // 头 5 条被丢掉的是最旧的
  });

  it("读到的栈是副本：外部改它 NEVER 影响真身", () => {
    pushUndo({ view: "graph", label: "add-node", undo: vi.fn() });

    getUndoStack().pop();

    expect(undoDepth()).toBe(1);
  });

  it("view 与 label 都必填：一条说不出自己是什么的撤销项没法提示用户", () => {
    expect(() => pushUndo({ view: "", label: "x", undo: vi.fn() })).toThrow();
    expect(() => pushUndo({ view: "graph", label: "  ", undo: vi.fn() })).toThrow();
  });
});
