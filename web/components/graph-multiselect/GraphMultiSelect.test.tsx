// GRAPH-09 验收：框选 + ⌘A + 批量设角色（**批量路径上主唯一仍生效**）。
//
// acceptance：批量设 primary 时仍只留最后一个为主（约束穿透断言）。
//
// 为什么这条要单独验：主唯一在单个路径上（GRAPH-06）已经守住了，而批量是
// **另一条路**——一次选中八个节点点「设为主」，很容易实现成「给八个都打上 primary」。
// 那之后图里有八个主，I12-1 破了，而界面上看不出来：每个节点都显示自己是主。
//
// 选择本身也有两条纪律：框选是**加选**不是替换（否则用户第二次框选就丢了第一次的），
// ⌘A 全选只选**画布内**的节点（把不在图里的东西也选上，随后的批量操作会作用到
// 用户根本没看见的对象上）。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { GraphMultiSelect } from "./GraphMultiSelect";

const CODE = codeOnly(readFileSync(join(__dirname, "GraphMultiSelect.tsx"), "utf8"));

const NODES = [
  { nodeId: "n-1", x: 10, y: 10 },
  { nodeId: "n-2", x: 30, y: 30 },
  { nodeId: "n-3", x: 200, y: 200 },
];

function setup(overrides: Record<string, unknown> = {}) {
  const onBatchRole = vi.fn().mockResolvedValue({ primaryNodeId: "n-2" });
  const utils = render(
    <GraphMultiSelect nodes={NODES} onBatchRole={onBatchRole} {...overrides} />,
  );
  return { onBatchRole, ...utils };
}

function marquee(from: [number, number], to: [number, number]): void {
  const canvas = screen.getByTestId("graph-multiselect-canvas");
  fireEvent.pointerDown(canvas, { clientX: from[0], clientY: from[1] });
  fireEvent.pointerMove(canvas, { clientX: to[0], clientY: to[1] });
  fireEvent.pointerUp(canvas, { clientX: to[0], clientY: to[1] });
}

describe("GraphMultiSelect（框选 + ⌘A + 批量角色）", () => {
  it("框选把框内的节点选上，框外的不动", () => {
    setup();

    marquee([0, 0], [50, 50]);

    expect(screen.getByTestId("graph-selection")).toHaveAttribute(
      "data-selected", "n-1,n-2",
    );
  });

  it("再框一次是**加选**不是替换：第一次选中的还在", () => {
    setup();

    marquee([0, 0], [20, 20]);      // n-1
    marquee([150, 150], [250, 250]); // n-3

    expect(screen.getByTestId("graph-selection")).toHaveAttribute(
      "data-selected", "n-1,n-3",
    );
  });

  it("⌘A 全选只选画布内的节点", () => {
    setup();

    fireEvent.keyDown(window, { key: "a", metaKey: true });

    expect(screen.getByTestId("graph-selection")).toHaveAttribute(
      "data-selected", "n-1,n-2,n-3",
    );
  });

  it("Esc 清空选择：不留一个看不见的选中集", () => {
    setup();

    fireEvent.keyDown(window, { key: "a", metaKey: true });
    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.getByTestId("graph-selection")).toHaveAttribute("data-selected", "");
  });

  it("批量设 primary：一次请求、带全部选中项与角色，NEVER 拆成 N 次各自设主", async () => {
    const { onBatchRole } = setup();

    fireEvent.keyDown(window, { key: "a", metaKey: true });
    fireEvent.click(screen.getByTestId("graph-batch-primary"));

    await vi.waitFor(() => expect(onBatchRole).toHaveBeenCalledTimes(1));
    expect(onBatchRole).toHaveBeenCalledWith(["n-1", "n-2", "n-3"], "primary");
  });

  it("约束穿透：批量之后图里仍只有一个主，且就是服务端说的那个", async () => {
    const onBatchRole = vi.fn().mockResolvedValue({ primaryNodeId: "n-3" });
    render(<GraphMultiSelect nodes={NODES} onBatchRole={onBatchRole} />);

    fireEvent.keyDown(window, { key: "a", metaKey: true });
    fireEvent.click(screen.getByTestId("graph-batch-primary"));

    const bar = await screen.findByTestId("graph-multiselect-primary");
    expect(bar).toHaveAttribute("data-primary-node-id", "n-3");
    // 界面上被标成主的节点恰一个——批量把 N 个都标成主，I12-1 就破了而界面看不出来
    expect(screen.getAllByTestId("graph-multiselect-node").filter(
      (n) => n.getAttribute("data-primary") === "true",
    )).toHaveLength(1);
  });

  it("主由服务端定，前端 NEVER 自己挑「最后一个」", async () => {
    // 选中顺序是 n-1,n-2,n-3，服务端偏偏说主是 n-1：界面必须听服务端的
    const onBatchRole = vi.fn().mockResolvedValue({ primaryNodeId: "n-1" });
    render(<GraphMultiSelect nodes={NODES} onBatchRole={onBatchRole} />);

    fireEvent.keyDown(window, { key: "a", metaKey: true });
    fireEvent.click(screen.getByTestId("graph-batch-primary"));

    const bar = await screen.findByTestId("graph-multiselect-primary");
    expect(bar).toHaveAttribute("data-primary-node-id", "n-1");
    expect(CODE).not.toMatch(/selected\[selected\.length\s*-\s*1\]/);
  });

  it("批量设次要/辅助不产生主：回值没有主时界面上一个主都没有", async () => {
    const onBatchRole = vi.fn().mockResolvedValue({ primaryNodeId: null });
    render(<GraphMultiSelect nodes={NODES} onBatchRole={onBatchRole} />);

    fireEvent.keyDown(window, { key: "a", metaKey: true });
    fireEvent.click(screen.getByTestId("graph-batch-secondary"));

    await vi.waitFor(() => expect(onBatchRole).toHaveBeenCalled());
    expect(onBatchRole).toHaveBeenCalledWith(["n-1", "n-2", "n-3"], "secondary");
    expect(screen.getAllByTestId("graph-multiselect-node").filter(
      (n) => n.getAttribute("data-primary") === "true",
    )).toHaveLength(0);
  });

  it("没选中任何节点时不发批量请求：空批量没有语义", () => {
    const { onBatchRole } = setup();

    fireEvent.click(screen.getByTestId("graph-batch-primary"));

    expect(onBatchRole).not.toHaveBeenCalled();
  });

  it("批量失败不谎报：出错误态且不改主标记", async () => {
    const onBatchRole = vi.fn().mockRejectedValue(new Error("boom"));
    render(<GraphMultiSelect nodes={NODES} onBatchRole={onBatchRole} />);

    fireEvent.keyDown(window, { key: "a", metaKey: true });
    fireEvent.click(screen.getByTestId("graph-batch-primary"));

    await screen.findByTestId("graph-multiselect-error");
    expect(screen.getByTestId("graph-multiselect-primary")).toHaveAttribute(
      "data-primary-node-id", "",
    );
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
