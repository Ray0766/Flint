// K6-01 验收：多工作台切换入口（切换 / 归档 / 恢复）。
//
// ## 数据层早就有了，本卡接的是交互
//
// `flint/graph/multi.py`（GRAPH-14）已有多台存储、`archived` 字段、按 owner 列举、
// 归档与取消归档。入口 flag 当时是 **off**，原话：「打开一个没有交互稿的入口，
// 用户会遇到一半能用一半不能用的界面，那比『暂时只有一台』糟得多」。
// K6 交互定了，本卡把入口做出来。
//
// ## 交互形态照抄谁（卡面要求：拿不准先搜权威产品）
//
// Slack 的工作区切换器：**一个常驻入口 → 展开成一份列表 → 点一项就切过去**
// （见 trace §3 的出处）。本卡照这个形状：一个按钮 + 一份列表，
// **不做多层菜单**——多台在本产品里是「同一个人的几个思考现场」，不是租户树。
//
// ## GRAPH-16 的纪律不破
//
// 切的是**工作台**，不是**模式**。`workbenchTabsStore` 的原话：状态树里没有 mode，
// 因为它与「当前页签」「AI 栏折叠态」会成为两份真相。本卡的状态同理只有
// 两个正交的键：`currentId` 与 `showArchived`——**NEVER 出现 mode 键**，
// 下面有一条逐字盯着它。

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import zh from "../../messages/zh.json";
import {
  INITIAL_SWITCH_STATE,
  WorkbenchSwitch,
  type Workbench,
  archivedOf,
  visibleWorkbenches,
} from "./WorkbenchSwitch";

const BENCHES: Workbench[] = [
  { graphId: "g1", title: "锂电池回收", archived: false },
  { graphId: "g2", title: "固态电池", archived: false },
  { graphId: "g3", title: "旧的调研", archived: true },
];

function renderSwitch(overrides: Partial<React.ComponentProps<typeof WorkbenchSwitch>> = {}) {
  const props = {
    workbenches: BENCHES,
    currentId: "g1",
    onSwitch: vi.fn(),
    onArchive: vi.fn(),
    onUnarchive: vi.fn(),
    ...overrides,
  };
  render(<WorkbenchSwitch {...props} />);
  return props;
}

describe("WorkbenchSwitch", () => {
  // ── ① 三个动作都能用（acceptance②）

  it("默认只列未归档的台——归档的不在切换列表里", () => {
    renderSwitch();
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));

    const items = screen.getAllByTestId(/^workbench-item-/);
    expect(items.map((el) => el.getAttribute("data-graph-id"))).toEqual(["g1", "g2"]);
  });

  it("切换：点一项就带出它的 id", () => {
    const props = renderSwitch();
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));
    fireEvent.click(screen.getByTestId("workbench-item-g2"));

    expect(props.onSwitch).toHaveBeenCalledWith("g2");
  });

  it("切到当前这台不重复触发——避免一次无意义的重载", () => {
    const props = renderSwitch();
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));
    fireEvent.click(screen.getByTestId("workbench-item-g1"));

    expect(props.onSwitch).not.toHaveBeenCalled();
  });

  it("归档：每台有归档按钮，带出它自己的 id", () => {
    const props = renderSwitch();
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));
    fireEvent.click(screen.getByTestId("workbench-archive-g2"));

    expect(props.onArchive).toHaveBeenCalledWith("g2");
  });

  it("恢复：展开归档区之后才有恢复按钮，且带出被归档那台的 id", () => {
    const props = renderSwitch();
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));
    expect(screen.queryByTestId("workbench-unarchive-g3")).toBeNull();

    fireEvent.click(screen.getByTestId("workbench-show-archived"));
    fireEvent.click(screen.getByTestId("workbench-unarchive-g3"));

    expect(props.onUnarchive).toHaveBeenCalledWith("g3");
  });

  it("归档区里 NEVER 出现删除入口——归档不是删除（数据删除是 owner 人审节点）", () => {
    renderSwitch();
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));
    fireEvent.click(screen.getByTestId("workbench-show-archived"));

    expect(screen.queryByTestId(/^workbench-delete-/)).toBeNull();
  });

  it("最后一台不给归档——归档掉全部会让用户落到一个没有工作台的界面", () => {
    renderSwitch({ workbenches: [BENCHES[0], BENCHES[2]] });
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));

    expect(screen.getByTestId("workbench-archive-g1")).toBeDisabled();
  });

  // ── ② 当前台看得出来是哪台

  it("当前台带 aria-current，且列表里只有一个", () => {
    renderSwitch();
    fireEvent.click(screen.getByTestId("workbench-switch-trigger"));

    const current = screen.getAllByTestId(/^workbench-item-/)
      .filter((el) => el.getAttribute("aria-current") === "true");
    expect(current).toHaveLength(1);
    expect(current[0].getAttribute("data-graph-id")).toBe("g1");
  });

  it("入口按钮上显示当前台的名字——不展开也知道自己在哪台", () => {
    renderSwitch();

    expect(screen.getByTestId("workbench-switch-trigger").textContent).toContain("锂电池回收");
  });

  it("一台都没有时入口不消失，而是说明现在没有台", () => {
    renderSwitch({ workbenches: [], currentId: "" });

    expect(screen.getByTestId("workbench-switch-trigger")).toBeTruthy();
    expect(screen.getByTestId("workbench-switch-trigger").textContent).toContain(
      zh["workbench.switch.empty"],
    );
  });

  // ── ③ GRAPH-16：切的是台，不是模式（acceptance③）

  it("状态键恒为两个正交的键，NEVER 有 mode", () => {
    expect(Object.keys(INITIAL_SWITCH_STATE).sort()).toEqual(["currentId", "showArchived"]);
  });

  it("整个模块的源码里没有 mode 键", async () => {
    const source = await import("./WorkbenchSwitch?raw").then((m) => m.default as string);
    const code = source
      .split("\n")
      .filter((line) => !line.trim().startsWith("//"))
      .join("\n");

    expect(/\bmode\s*[:=]/.test(code)).toBe(false);
  });

  // ── ④ 文案走 i18n key（acceptance④）

  it("界面上的中文都来自词条，组件源码里零 CJK 字面量", async () => {
    const source = await import("./WorkbenchSwitch?raw").then((m) => m.default as string);
    const code = source
      .split("\n")
      .filter((line) => !line.trim().startsWith("//"))
      .join("\n");

    expect(code).not.toMatch(/[一-鿿]/);
  });

  it("用到的 key 在 zh 与 en 两份词条里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    const keys = [
      "workbench.switch.label",
      "workbench.switch.empty",
      "workbench.switch.archive",
      "workbench.switch.unarchive",
      "workbench.switch.showArchived",
      "workbench.switch.archivedSection",
      "workbench.switch.lastOne",
    ];

    for (const key of keys) {
      expect((zh as Record<string, string>)[key], `zh 缺 ${key}`).toBeTruthy();
      expect(en[key], `en 缺 ${key}`).toBeTruthy();
    }
  });

  // ── ⑤ 纯函数那两条：列表与归档分组是可单独验的

  it("visibleWorkbenches 按归档态分组，两组互不重叠", () => {
    expect(visibleWorkbenches(BENCHES).map((w) => w.graphId)).toEqual(["g1", "g2"]);
    expect(archivedOf(BENCHES).map((w) => w.graphId)).toEqual(["g3"]);
  });

  it("空列表两组都空，NEVER 抛错", () => {
    expect(visibleWorkbenches([])).toEqual([]);
    expect(archivedOf([])).toEqual([]);
  });
});
