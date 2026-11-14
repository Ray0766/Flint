// GRAPH-05 验收：双击节点开分析抽屉（不离台）。
//
// acceptance：**抽屉复用分析视图组件；路由不跳转断言**。
//
// 这是 V4 第一张装配卡（见 docs/trace/SELFCHECK-V3.md#④）：前面各卡都是组件级的，
// 而「不离台」这件事只有把**容器 + 真实子组件**拼起来才验得到——
// 单测一个抽屉壳子，抽屉里装的是不是那个分析视图、画布是不是还活着，都测不到。
// 所以本卡的测试用**真的 GraphNode + 真的 AnalysisView**，不用替身。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GraphNode } from "../graph-node/GraphNode";
import { GraphOpenAnalysis } from "./GraphOpenAnalysis";

type Call = { url: string; method: string };

function spyFetch(calls: Call[]): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: (init?.method ?? "GET").toUpperCase() });
    if (url.includes("/verdict")) {
      return new Response(
        JSON.stringify({
          verdict: {
            verdict: "C_opportunity", all_satisfied: ["C_opportunity"],
            key_citation_ids: ["cit-1"], rationale_fact_ids: [], competitors: [],
            constraints_checked: true, gaps: [],
          },
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    return new Response(JSON.stringify({ evidence_cards: [] }), {
      status: 200, headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

function renderCanvas(calls: Call[]) {
  return render(
    <GraphOpenAnalysis clusterId="c-1" verdictJobId="job-1" fetchImpl={spyFetch(calls)}>
      <GraphNode nodeId="n-1" sourceKind="cluster" nameNative="半導体材料の新工法" />
    </GraphOpenAnalysis>,
  );
}

describe("GraphOpenAnalysis（双击开分析抽屉）", () => {
  it("双击节点打开抽屉，抽屉里是**那个**分析视图（复用而非另画一份）", async () => {
    const calls: Call[] = [];
    renderCanvas(calls);

    expect(screen.queryByTestId("graph-analysis-drawer")).toBeNull();
    fireEvent.doubleClick(screen.getByTestId("graph-node"));

    // AnalysisView 自己的 testid 出现 = 抽屉里装的确实是它
    expect(await screen.findByTestId("analysis-view")).toBeInTheDocument();
    expect(screen.getByTestId("analysis-view")).toHaveAttribute("data-cluster-id", "c-1");
    expect(await screen.findByTestId("analysis-verdict")).toHaveAttribute(
      "data-verdict",
      "C_opportunity",
    );
  });

  it("不离台：画布与那个节点在抽屉打开后仍然在场", async () => {
    const calls: Call[] = [];
    renderCanvas(calls);

    fireEvent.doubleClick(screen.getByTestId("graph-node"));
    await screen.findByTestId("analysis-view");

    expect(screen.getByTestId("graph-node")).toBeInTheDocument();
    expect(screen.getByTestId("graph-node")).toHaveAttribute("data-node-id", "n-1");
  });

  it("路由不跳转：地址栏一个字符都没变", async () => {
    const before = window.location.href;
    const calls: Call[] = [];
    renderCanvas(calls);

    fireEvent.doubleClick(screen.getByTestId("graph-node"));
    await screen.findByTestId("analysis-view");

    expect(window.location.href).toBe(before);
  });

  it("源码里没有任何跳转手段：抽屉是就地打开的", () => {
    const source = readFileSync(join(__dirname, "GraphOpenAnalysis.tsx"), "utf8");
    for (const forbidden of [
      "pushState", "replaceState", "location.href", "location.assign",
      "useRouter", "router.push", "<a ", "href=", "window.open",
    ]) {
      expect(source).not.toContain(forbidden);
    }
  });

  it("复用不复制：import 分析视图，且自己不画判定/证据槽", () => {
    const source = readFileSync(join(__dirname, "GraphOpenAnalysis.tsx"), "utf8");
    expect(source).toMatch(/from "\.\.\/\.\.\/views\/analysis\/AnalysisView"/);
    for (const copied of [
      "analysis-verdict", "analysis-evidence", "analysis-verdict-unjudged",
    ]) {
      expect(source).not.toContain(copied);
    }
  });

  it("单击不开抽屉：画布上点一下是选中，不是打开一屏东西", () => {
    const calls: Call[] = [];
    renderCanvas(calls);

    fireEvent.click(screen.getByTestId("graph-node"));

    expect(screen.queryByTestId("graph-analysis-drawer")).toBeNull();
    expect(calls).toHaveLength(0); // 连读请求都不该发
  });

  it("关闭抽屉回到画布：节点还在，抽屉不留残影", async () => {
    const calls: Call[] = [];
    renderCanvas(calls);

    fireEvent.doubleClick(screen.getByTestId("graph-node"));
    await screen.findByTestId("analysis-view");
    fireEvent.click(screen.getByTestId("graph-analysis-drawer-close"));

    expect(screen.queryByTestId("graph-analysis-drawer")).toBeNull();
    expect(screen.queryByTestId("analysis-view")).toBeNull();
    expect(screen.getByTestId("graph-node")).toBeInTheDocument();
  });

  it("打开抽屉只读不算：全程零写请求（点开一个热点 NEVER 顺手跑一次分析）", async () => {
    const calls: Call[] = [];
    renderCanvas(calls);

    fireEvent.doubleClick(screen.getByTestId("graph-node"));
    await screen.findByTestId("analysis-verdict");

    expect(calls.length).toBeGreaterThanOrEqual(2); // 阴性对照：读确实发生了
    expect(calls.every((c) => c.method === "GET")).toBe(true);
    expect(calls.some((c) => c.url.includes("/analysis"))).toBe(false);
  });

  it("抽屉是对话框语义：带 role 与可达的关闭控件", async () => {
    const calls: Call[] = [];
    renderCanvas(calls);

    fireEvent.doubleClick(screen.getByTestId("graph-node"));
    const drawer = await screen.findByTestId("graph-analysis-drawer");

    expect(drawer).toHaveAttribute("role", "dialog");
    expect(drawer).toHaveAttribute("aria-modal", "false"); // 不离台：画布仍可交互
    expect(screen.getByTestId("graph-analysis-drawer-close")).toBeInTheDocument();
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    const source = readFileSync(join(__dirname, "GraphOpenAnalysis.tsx"), "utf8");
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    expect(code).not.toMatch(/[一-鿿]/);
  });
});
