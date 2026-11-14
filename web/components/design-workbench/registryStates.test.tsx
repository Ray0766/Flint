// DESIGN-03：模板注册表四态 —— **阴性对照四条，断言屏上四种话互不相同**。
//
// 三态版把「这套部署根本没有 templates 表」塞进任一已有值都是谎
// （`docs/blocked/UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md` 逐条列过）：
// 塞进 `down` → 屏上写「不可用，请稍后重试」，而真相是重试一万次也不会有；
// 塞进 `not_checked` → 我们明明查过了。
//
// 所以下面每一态都单独构造一次，并**逐条断言另外三态的话不在场**：
// 只断言「本态的话在」的话，一个把四句话全渲染出来的实现照样全绿。
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DesignWorkbench, type RegistryState } from "./DesignWorkbench";
import zh from "../../messages/zh.json";

const OK = { html: "<p>x</p>", error: null };

/** 四态 → 它该说的那句话。`ok` 不说话（固化放开）。 */
const LINES: Record<Exclude<RegistryState, "ok">, string> = {
  not_checked: zh["design.solidify.not_checked"],
  not_provided: zh["design.solidify.not_provided"],
  down: zh["design.solidify.registry_down"],
};

const BLOCKED = ["not_checked", "not_provided", "down"] as const;

describe("DESIGN-03 模板注册表四态", () => {
  it("四句话互不相同——长得一样的三种阻断等于没分开", () => {
    const said = Object.values(LINES);

    expect(new Set(said).size).toBe(said.length);
    for (const line of said) expect(line.length).toBeGreaterThan(4);
  });

  it.each(BLOCKED)("%s：只说自己那句，另外三态的话都不在场", (state) => {
    const { container } = render(
      <DesignWorkbench preview={OK} registryAvailable={state} />);

    expect(screen.getByText(LINES[state])).toBeTruthy();
    for (const other of BLOCKED) {
      if (other === state) continue;
      expect(screen.queryByText(LINES[other])).toBeNull();
    }
    expect(container.querySelector("[data-design-blocked]")
      ?.getAttribute("data-design-blocked")).toBe(state);
  });

  it.each(BLOCKED)("%s：固化置灰", (state) => {
    const { container } = render(
      <DesignWorkbench preview={OK} registryAvailable={state} />);

    expect(container.querySelector(".design__solidify")?.hasAttribute("disabled"))
      .toBe(true);
  });

  it("ok：固化放开，且一句阻断的话都不说", () => {
    const { container } = render(
      <DesignWorkbench preview={OK} registryAvailable="ok" />);

    expect(container.querySelector(".design__solidify")?.hasAttribute("disabled"))
      .toBe(false);
    expect(container.querySelector("[data-design-blocked]")).toBeNull();
    for (const line of Object.values(LINES)) {
      expect(screen.queryByText(line)).toBeNull();
    }
  });

  it("「这里没有」NEVER 说成「坏了」——那句话要说得出「重试也不会有」", () => {
    expect(LINES.not_provided).not.toBe(LINES.down);
    expect(LINES.not_provided).toContain("重试");
  });

  it("四态都不影响探索：E6 要说清**还能做什么**", () => {
    for (const state of ["not_checked", "not_provided", "down", "ok"] as const) {
      const { unmount } = render(
        <DesignWorkbench preview={OK} registryAvailable={state} />);
      expect(screen.getAllByText(zh["design.explore.still_open"]).length)
        .toBeGreaterThan(0);
      unmount();
    }
  });
});
