// DESIGN-26 验收：反向高亮（节点 ↔ 首个引用 Block 滚动定位）。
//
// acceptance：**点节点滚动到首引用 Block；点 Block 高亮来源节点**。
//
// 为什么「首个」而不是「全部」：一个节点常被文书里好几处引用。一次把七处都高亮，
// 用户还是不知道该看哪；滚到**第一处**并高亮它，是一个明确的落点，
// 他从那里往下读就行。其余引用不是丢了——它们仍在，只是这次跳转不替他决定看哪个。
//
// 为什么找不到就明说：一个点了没反应的节点，用户会以为界面卡了，然后反复点。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import {
  firstReferencingBlock,
  nodesReferencedByBlock,
  planNodeToBlockJump,
} from "./crossHighlight";

const CODE = codeOnly(readFileSync(join(__dirname, "crossHighlight.ts"), "utf8"));

// 文书顺序即数组顺序：b-1 引用 n-1、b-2 引用 n-2 与 n-1、b-3 无引用
const BLOCKS = [
  { blockId: "b-1", order: 0, sourceNodeIds: ["n-1"] },
  { blockId: "b-2", order: 1, sourceNodeIds: ["n-2", "n-1"] },
  { blockId: "b-3", order: 2, sourceNodeIds: [] },
];

describe("firstReferencingBlock（节点 → 首个引用 Block）", () => {
  it("按文书顺序取第一处引用", () => {
    expect(firstReferencingBlock(BLOCKS, "n-1")?.blockId).toBe("b-1");
    expect(firstReferencingBlock(BLOCKS, "n-2")?.blockId).toBe("b-2");
  });

  it("顺序按 order 而不是数组下标：数组可能是乱序读回来的", () => {
    const shuffled = [BLOCKS[1], BLOCKS[0], BLOCKS[2]];

    expect(firstReferencingBlock(shuffled, "n-1")?.blockId).toBe("b-1");
  });

  it("没有任何引用时返回 null，NEVER 退而求其次跳到第一个 Block", () => {
    expect(firstReferencingBlock(BLOCKS, "n-404")).toBeNull();
  });
});

describe("nodesReferencedByBlock（Block → 来源节点）", () => {
  it("一个 Block 的全部来源节点都交出去", () => {
    expect(nodesReferencedByBlock(BLOCKS, "b-2")).toEqual(["n-2", "n-1"]);
  });

  it("无引用的 Block 返回空数组", () => {
    expect(nodesReferencedByBlock(BLOCKS, "b-3")).toEqual([]);
  });

  it("未知 Block 返回空数组而不是抛：点到一个还没渲染出来的块不该炸", () => {
    expect(nodesReferencedByBlock(BLOCKS, "b-404")).toEqual([]);
  });
});

describe("planNodeToBlockJump（跳转计划）", () => {
  it("找得到时给出滚动目标与高亮目标", () => {
    const plan = planNodeToBlockJump(BLOCKS, "n-1");

    expect(plan).toEqual({
      found: true,
      scrollToBlockId: "b-1",
      highlightBlockId: "b-1",
      reason: null,
    });
  });

  it("找不到时明说原因：点了没反应的节点会让用户以为界面卡了", () => {
    const plan = planNodeToBlockJump(BLOCKS, "n-404");

    expect(plan.found).toBe(false);
    expect(plan.scrollToBlockId).toBeNull();
    expect(plan.reason).toBe("no_reference");
  });

  it("计划是数据：这一层不碰 DOM，滚动由调用方执行", () => {
    // 直接在这里 scrollIntoView，测试就只能在 jsdom 里验一个假滚动，
    // 而真正的容器/偏移量归调用方——两边各滚一次会把页面弹两下
    for (const banned of ["scrollIntoView", "document.", "window.scroll"]) {
      expect(CODE).not.toContain(banned);
    }
  });

  it("同一次跳转算两遍结果一样（纯函数）", () => {
    expect(planNodeToBlockJump(BLOCKS, "n-1")).toEqual(
      planNodeToBlockJump(BLOCKS, "n-1"),
    );
  });
});

describe("双向一致", () => {
  it("跳过去的那个 Block，反查得回原节点（往返闭合）", () => {
    const plan = planNodeToBlockJump(BLOCKS, "n-2");
    const back = nodesReferencedByBlock(BLOCKS, plan.scrollToBlockId as string);

    expect(back).toContain("n-2");
  });

  it("空文书不炸：一份还没生成内容的样板照样能点节点", () => {
    const plan = planNodeToBlockJump([], "n-1");

    expect(plan.found).toBe(false);
    expect(plan.reason).toBe("no_reference");
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});

describe("高亮是短暂的（由调用方决定时长，本层只给标记）", () => {
  it("不在这一层设定时器：定时器归 UI，纯函数里不该有时间", () => {
    for (const banned of ["setTimeout", "setInterval", "requestAnimationFrame"]) {
      expect(CODE).not.toContain(banned);
    }
    expect(vi.isMockFunction(planNodeToBlockJump)).toBe(false);
  });
});
