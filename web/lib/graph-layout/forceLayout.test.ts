// GRAPH-11 验收：力导向**一次性**布局（收敛即停 + 零新依赖）。
//
// acceptance①「迭代收敛后停止（无持续 rAF 断言）；50 节点内布局完成」；
// acceptance②「package.json 无新增布局依赖」。
//
// 为什么必须是一次性而不是持续模拟：持续 rAF 的力导向图会一直微微地动，
// 用户想点的节点会在指尖底下漂走；而且它每一帧都在烧电。摆位置是**一次**动作，
// 摆完就该停——不是一个永远在跑的动画。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { layoutGraph, LAYOUT_MAX_ITERATIONS } from "./forceLayout";

const CODE = codeOnly(readFileSync(join(__dirname, "forceLayout.ts"), "utf8"));

function chain(n: number) {
  const nodes = Array.from({ length: n }, (_, i) => ({ nodeId: `n-${i}` }));
  const edges = Array.from({ length: n - 1 }, (_, i) => ({
    fromNodeId: `n-${i}`,
    toNodeId: `n-${i + 1}`,
  }));
  return { nodes, edges };
}

describe("layoutGraph（一次性力导向）", () => {
  it("跑完就停：返回迭代次数，且不超过上限", () => {
    const { nodes, edges } = chain(12);

    const result = layoutGraph(nodes, edges);

    expect(result.iterations).toBeGreaterThan(0);
    expect(result.iterations).toBeLessThanOrEqual(LAYOUT_MAX_ITERATIONS);
    expect(result.converged).toBe(true);
  });

  it("没有持续动画：源码里既不排帧也不设定时器", () => {
    for (const forbidden of [
      "requestAnimationFrame", "setInterval", "setTimeout", "cancelAnimationFrame",
    ]) {
      expect(CODE).not.toContain(forbidden);
    }
  });

  it("零新依赖：本模块不 import 任何第三方包", () => {
    expect(CODE).not.toMatch(/from\s+"[^./]/);   // 只允许相对路径 import
  });

  it("package.json 无新增布局依赖", () => {
    const pkg = JSON.parse(
      readFileSync(join(__dirname, "..", "..", "package.json"), "utf8"),
    ) as { dependencies: Record<string, string>; devDependencies: Record<string, string> };
    const all = Object.keys({ ...pkg.dependencies, ...pkg.devDependencies });

    for (const banned of ["d3", "d3-force", "elkjs", "dagre", "cytoscape", "vis-network"]) {
      expect(all).not.toContain(banned);
    }
  });

  it("50 个节点也跑得完，且每个节点都拿到了位置", () => {
    const { nodes, edges } = chain(50);

    const result = layoutGraph(nodes, edges);

    expect(Object.keys(result.positions)).toHaveLength(50);
    for (const nodeId of nodes.map((n) => n.nodeId)) {
      const at = result.positions[nodeId];
      expect(Number.isFinite(at.x)).toBe(true);
      expect(Number.isFinite(at.y)).toBe(true);
    }
  });

  it("确定性：同样的输入两次跑出逐字相同的位置", () => {
    const { nodes, edges } = chain(20);

    const a = layoutGraph(nodes, edges);
    const b = layoutGraph(nodes, edges);

    expect(a.positions).toEqual(b.positions);
    expect(a.iterations).toBe(b.iterations);
    // 随机初值会让同一张图每次打开都换个样子，用户会以为数据变了
    expect(CODE).not.toContain("Math.random");
  });

  it("相连的节点比不相连的近：布局真的在做事", () => {
    const nodes = [{ nodeId: "a" }, { nodeId: "b" }, { nodeId: "c" }];
    const edges = [{ fromNodeId: "a", toNodeId: "b" }];

    const { positions } = layoutGraph(nodes, edges);
    const dist = (p: { x: number; y: number }, q: { x: number; y: number }) =>
      Math.hypot(p.x - q.x, p.y - q.y);

    expect(dist(positions.a, positions.b)).toBeLessThan(dist(positions.a, positions.c));
  });

  it("节点不重叠：两两之间留得下一个身位", () => {
    const { nodes, edges } = chain(10);

    const { positions } = layoutGraph(nodes, edges);
    const ids = nodes.map((n) => n.nodeId);
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        const p = positions[ids[i]];
        const q = positions[ids[j]];
        expect(Math.hypot(p.x - q.x, p.y - q.y)).toBeGreaterThan(1);
      }
    }
  });

  it("锁定的节点原地不动：用户摆过的位置 NEVER 被自动布局挪走", () => {
    const { nodes, edges } = chain(6);

    const { positions } = layoutGraph(nodes, edges, {
      pinned: { "n-0": { x: 500, y: 500 } },
    });

    expect(positions["n-0"]).toEqual({ x: 500, y: 500 });
  });

  it("空图与单节点不炸：零边也算合法输入", () => {
    expect(layoutGraph([], []).positions).toEqual({});
    const single = layoutGraph([{ nodeId: "solo" }], []);
    expect(Number.isFinite(single.positions.solo.x)).toBe(true);
  });

  it("悬空边被忽略而不是让布局崩掉：端点不在节点表里就跳过", () => {
    const nodes = [{ nodeId: "a" }, { nodeId: "b" }];
    const edges = [
      { fromNodeId: "a", toNodeId: "b" },
      { fromNodeId: "a", toNodeId: "ghost" },
    ];

    const { positions } = layoutGraph(nodes, edges);

    expect(Object.keys(positions).sort()).toEqual(["a", "b"]);
    expect(Number.isFinite(positions.a.x)).toBe(true);
  });
});
