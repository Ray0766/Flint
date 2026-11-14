// GRAPH-01 验收：/workbench 路由归 F 组；容器不含 mode 概念（对 F15 两案中立）。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WORKBENCH_ROUTE, WorkbenchShell } from "./WorkbenchShell";

describe("WorkbenchShell", () => {
  it("路由是 /workbench（J4 定名，归 F 组）", () => {
    expect(WORKBENCH_ROUTE).toBe("/workbench");
    render(<WorkbenchShell>画布</WorkbenchShell>);
    expect(screen.getByTestId("workbench-shell")).toHaveAttribute("data-route", "/workbench");
  });

  it("容器里没有 mode 概念（源码断言，只看代码行）", () => {
    const source = readFileSync(join(__dirname, "WorkbenchShell.tsx"), "utf8");
    const code = source
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    for (const forbidden of ["mode", "Mode", "tab", "Tab"]) {
      expect(code).not.toContain(forbidden);
    }
  });

  it("props 面上没有布局决策：只有 children 与可选 aside", () => {
    const source = readFileSync(join(__dirname, "WorkbenchShell.tsx"), "utf8");
    expect(source).toContain("children: ReactNode");
    expect(source).toContain("aside?: ReactNode");
    for (const forbidden of ["layout", "variant", "preset"]) {
      expect(source.replace(/\/\/.*$/gm, "")).not.toContain(forbidden);
    }
  });

  it("主区原样渲染子节点（容器不关心它是什么）", () => {
    render(
      <WorkbenchShell>
        <div data-testid="canvas">图谱画布</div>
      </WorkbenchShell>,
    );
    expect(screen.getByTestId("canvas")).toBeTruthy();
  });

  it("侧栏是可选插槽：不给就不渲染，NEVER 留一个空壳", () => {
    render(<WorkbenchShell>画布</WorkbenchShell>);
    expect(screen.queryByTestId("workbench-aside")).toBeNull();
  });

  it("给了侧栏就渲染，内容原样透传", () => {
    render(
      <WorkbenchShell aside={<div data-testid="evidence-drawer">证据卡面板</div>}>
        画布
      </WorkbenchShell>,
    );
    expect(screen.getByTestId("evidence-drawer")).toBeTruthy();
  });

  it("两案中立：容器的**导出面**上没有页签/模式符号", async () => {
    // 初版这里拿一个空对象查 keys —— 那是空转的：不管容器导出什么它都绿。
    // 改成真的把模块导入进来看导出名。
    const mod = await import("./WorkbenchShell");
    const exported = Object.keys(mod);
    expect(exported.sort()).toEqual(["WORKBENCH_ROUTE", "WorkbenchShell"]);
    for (const name of exported) {
      expect(name.toLowerCase()).not.toContain("mode");
      expect(name.toLowerCase()).not.toContain("tab");
    }
  });
});
