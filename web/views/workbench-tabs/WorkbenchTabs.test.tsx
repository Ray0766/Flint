// GRAPH-16 验收（隔离带·F15）：页签 + 常驻可折叠 AI 栏，**状态树无 mode 键**。
//
// acceptance①「store 键集无 mode（断言）；「默认/AI」仅存在于预设文案层」；
// acceptance②「被划掉时仅移除本卡，零下游」。
//
// 为什么不放 mode：它与「当前页签」「AI 栏是否折叠」会成为**两份真相**——
// 用户点开 AI 栏时 mode 该不该变？切到树页签时 mode 又是什么？每加一个入口就要
// 回答一次，任何一次答得不一致，界面上就会出现「模式说是 A、页签显示 B」。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { WorkbenchTabs } from "./WorkbenchTabs";
import {
  applyPreset,
  describePreset,
  INITIAL_STATE,
  PRESETS,
} from "./workbenchTabsStore";

const STORE_CODE = codeOnly(readFileSync(join(__dirname, "workbenchTabsStore.ts"), "utf8"));
const VIEW_CODE = codeOnly(readFileSync(join(__dirname, "WorkbenchTabs.tsx"), "utf8"));

function renderTabs() {
  return render(
    <WorkbenchTabs
      graphView={<div data-testid="stub-graph" />}
      treeView={<div data-testid="stub-tree" />}
      aiPanel={<div data-testid="stub-ai" />}
    />,
  );
}

describe("workbenchTabsStore（状态）", () => {
  it("键集恰是 tab 与 aiPanelCollapsed —— 没有 mode", () => {
    expect(Object.keys(INITIAL_STATE).sort()).toEqual(["aiPanelCollapsed", "tab"]);
    for (const preset of Object.values(PRESETS)) {
      expect(Object.keys(preset).sort()).toEqual(["aiPanelCollapsed", "tab"]);
    }
    expect(STORE_CODE).not.toMatch(/\bmode\b/);
    expect(VIEW_CODE).not.toMatch(/\bmode\b/);
  });

  it("预设是一次性组合，不是被存起来的状态", () => {
    const applied = applyPreset("ai");

    expect(applied).toEqual({ tab: "graph", aiPanelCollapsed: false });
    expect(Object.keys(applied).sort()).toEqual(["aiPanelCollapsed", "tab"]);
  });

  it("预设名是**派生**的：由两个键算出来，算不出就是 null", () => {
    expect(describePreset({ tab: "graph", aiPanelCollapsed: true })).toBe("default");
    expect(describePreset({ tab: "graph", aiPanelCollapsed: false })).toBe("ai");
    // 树页签 + 展开：不匹配任何预设 —— NEVER 硬塞一个 default 让它看起来像默认态
    expect(describePreset({ tab: "tree", aiPanelCollapsed: false })).toBeNull();
  });
});

describe("WorkbenchTabs（渲染）", () => {
  it("两个页签都在，默认停在图谱", () => {
    renderTabs();

    expect(screen.getAllByRole("tab").map((n) => n.getAttribute("data-tab"))).toEqual([
      "graph", "tree",
    ]);
    expect(screen.getByTestId("workbench-tabpanel")).toHaveAttribute("data-tab", "graph");
    expect(screen.getByTestId("stub-graph")).toBeInTheDocument();
  });

  it("切页签换的是投影，不改 AI 栏折叠态（两个键正交）", () => {
    renderTabs();

    fireEvent.click(screen.getByTestId("workbench-tab-tree"));

    expect(screen.getByTestId("workbench-tabpanel")).toHaveAttribute("data-tab", "tree");
    expect(screen.getByTestId("stub-tree")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-ai-panel")).toHaveAttribute(
      "data-collapsed", "true",
    );
  });

  it("AI 栏常驻：折叠时仍在场，只是内容收起来", () => {
    renderTabs();

    const panel = screen.getByTestId("workbench-ai-panel");
    expect(panel).toBeInTheDocument();               // 折叠 ≠ 消失
    expect(screen.queryByTestId("workbench-ai-panel-body")).toBeNull();

    fireEvent.click(screen.getByTestId("workbench-ai-toggle"));

    expect(screen.getByTestId("workbench-ai-panel-body")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-ai-toggle")).toHaveAttribute(
      "aria-expanded", "true",
    );
  });

  it("展开 AI 栏不改页签（反向正交）", () => {
    renderTabs();

    fireEvent.click(screen.getByTestId("workbench-tab-tree"));
    fireEvent.click(screen.getByTestId("workbench-ai-toggle"));

    expect(screen.getByTestId("workbench-tabpanel")).toHaveAttribute("data-tab", "tree");
  });

  it("「AI」预设只是把两个键设成一个组合，页面上以派生名呈现", () => {
    renderTabs();

    expect(screen.getByTestId("workbench-tabs")).toHaveAttribute("data-preset", "default");

    fireEvent.click(screen.getByTestId("workbench-preset-ai"));

    expect(screen.getByTestId("workbench-tabs")).toHaveAttribute("data-preset", "ai");
    expect(screen.getByTestId("workbench-ai-panel")).toHaveAttribute(
      "data-collapsed", "false",
    );
  });

  it("不匹配任何预设时 data-preset 为空，NEVER 谎称是默认态", () => {
    renderTabs();

    fireEvent.click(screen.getByTestId("workbench-tab-tree"));
    fireEvent.click(screen.getByTestId("workbench-ai-toggle"));

    expect(screen.getByTestId("workbench-tabs")).toHaveAttribute("data-preset", "");
  });

  it("复用容器 GRAPH-01，不另画一个外壳", () => {
    renderTabs();

    expect(screen.getByTestId("workbench-shell")).toBeInTheDocument();
    expect(VIEW_CODE).toMatch(/from "\.\.\/workbench-shell\/WorkbenchShell"/);
  });

  it("零下游：容器与其它 F 组卡都不引用本卡", () => {
    const shell = readFileSync(
      join(__dirname, "..", "workbench-shell", "WorkbenchShell.tsx"), "utf8",
    );
    expect(shell).not.toContain("workbench-tabs");
    // 被划掉时只需删掉本目录：依赖方向是**本卡 → 容器**，反向一条都没有
  });

  it("文案 key 化：两份源码代码行零 CJK", () => {
    expect(VIEW_CODE).not.toMatch(/[一-鿿]/);
    expect(STORE_CODE).not.toMatch(/[一-鿿]/);
  });
});
