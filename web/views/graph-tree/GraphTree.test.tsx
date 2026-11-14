// GRAPH-12 验收：树视图 = primary 为根的 BFS 投影 + 未连接区（F13/F14）。
//
// acceptance①「同一存储双投影一致（图↔树切换零丢节点）」；
// acceptance②「未连接节点入独立区」。
//
// 两个视图是**同一份数据的两种画法**，不是两份数据。切一下视图少了两个节点，
// 用户不会想到「那是投影规则的问题」——他会以为自己把它们删了，
// 然后回到图谱里去找那两个再也找不到的东西。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { GraphTree, projectToTree } from "./GraphTree";

const CODE = codeOnly(readFileSync(join(__dirname, "GraphTree.tsx"), "utf8"));

//   n-1(primary) → n-2 → n-4
//         ↓
//        n-3           n-5（谁都不连）
const NODES = [
  { nodeId: "n-1", label: "根", primary: true },
  { nodeId: "n-2", label: "二", primary: false },
  { nodeId: "n-3", label: "三", primary: false },
  { nodeId: "n-4", label: "四", primary: false },
  { nodeId: "n-5", label: "五", primary: false },
];
const EDGES = [
  { fromNodeId: "n-1", toNodeId: "n-2", hypothesis: "h1" },
  { fromNodeId: "n-1", toNodeId: "n-3", hypothesis: "h2" },
  { fromNodeId: "n-2", toNodeId: "n-4", hypothesis: "h3" },
];

describe("projectToTree（投影规则）", () => {
  it("primary 是根，层级按 BFS 距离", () => {
    const tree = projectToTree(NODES, EDGES);

    expect(tree.rootId).toBe("n-1");
    expect(tree.depthOf["n-1"]).toBe(0);
    expect(tree.depthOf["n-2"]).toBe(1);
    expect(tree.depthOf["n-3"]).toBe(1);
    expect(tree.depthOf["n-4"]).toBe(2);
  });

  it("零丢节点：树里的节点 + 未连接区 = 图里的全部节点", () => {
    const tree = projectToTree(NODES, EDGES);

    const shown = [...Object.keys(tree.depthOf), ...tree.detachedIds].sort();
    expect(shown).toEqual(NODES.map((n) => n.nodeId).sort());
  });

  it("未连接的进独立区，NEVER 被挂到根下面充数", () => {
    const tree = projectToTree(NODES, EDGES);

    expect(tree.detachedIds).toEqual(["n-5"]);
    expect(tree.depthOf["n-5"]).toBeUndefined();
  });

  it("没有 primary 时整棵树为空、全部进未连接区（NEVER 挑一个当根）", () => {
    const noPrimary = NODES.map((n) => ({ ...n, primary: false }));

    const tree = projectToTree(noPrimary, EDGES);

    expect(tree.rootId).toBeNull();
    expect(tree.detachedIds).toEqual(["n-1", "n-2", "n-3", "n-4", "n-5"]);
    // 挑一个当根等于替用户回答「这张图在讲哪件事」（与 GRAPH-06/08 同一条纪律）
    expect(CODE).not.toMatch(/nodes\[0\]/);
  });

  it("有向：反向边不把父子关系倒过来", () => {
    // n-2 → n-1 只有反向边时，n-2 不该成为 n-1 的父
    const tree = projectToTree(NODES, [{ fromNodeId: "n-2", toNodeId: "n-1", hypothesis: "h" }]);

    expect(tree.rootId).toBe("n-1");
    expect(tree.depthOf["n-2"]).toBeUndefined();  // 从根出不去
    expect(tree.detachedIds).toContain("n-2");
  });

  it("环不让 BFS 转不出来：每个节点只落一层", () => {
    const cyclic = [
      ...EDGES,
      { fromNodeId: "n-4", toNodeId: "n-1", hypothesis: "回边" },
    ];

    const tree = projectToTree(NODES, cyclic);

    expect(tree.depthOf["n-1"]).toBe(0);
    expect(Object.keys(tree.depthOf).sort()).toEqual(["n-1", "n-2", "n-3", "n-4"]);
  });

  it("同深度的兄弟按 id 稳定排序：刷新不换位置", () => {
    const tree = projectToTree(NODES, EDGES);

    expect(tree.childrenOf["n-1"]).toEqual(["n-2", "n-3"]);
  });
});

describe("GraphTree（渲染）", () => {
  it("渲染出树与未连接区两块，节点计数与图一致", () => {
    render(<GraphTree nodes={NODES} edges={EDGES} />);

    const rows = screen.getAllByTestId("graph-tree-node");
    const detached = within(screen.getByTestId("graph-tree-detached")).getAllByTestId(
      "graph-tree-detached-node",
    );

    expect(rows.length + detached.length).toBe(NODES.length);
    expect(screen.getByTestId("graph-tree")).toHaveAttribute(
      "data-node-count", String(NODES.length),
    );
  });

  it("每一行带得出自己的深度与 id：树形是数据不是缩进", () => {
    render(<GraphTree nodes={NODES} edges={EDGES} />);

    const row = screen
      .getAllByTestId("graph-tree-node")
      .find((n) => n.getAttribute("data-node-id") === "n-4");

    expect(row).toHaveAttribute("data-depth", "2");
  });

  it("未连接区在树为空时也渲染：空态不是「什么都没有」", () => {
    render(<GraphTree nodes={[{ nodeId: "solo", label: "孤", primary: false }]} edges={[]} />);

    expect(screen.getByTestId("graph-tree-detached")).toBeInTheDocument();
    expect(screen.getAllByTestId("graph-tree-detached-node")).toHaveLength(1);
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
