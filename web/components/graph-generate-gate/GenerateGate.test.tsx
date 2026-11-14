// GRAPH-08 验收：空假设阻断生成 + AI 栏摘要条（F9/F10）。
//
// acceptance①「存在空假设边 → 按钮置灰 + 计数徽章 + 点击高亮定位」；
// acceptance②「摘要条列 primary / 边数 / 假设完整度三项」。
//
// 为什么置灰之外**必须**给计数和定位：一个灰着的按钮只说明「不能生成」，
// 不说明「缺什么、在哪」。用户面对一张十几个节点的图，会挨个点开每条边去找——
// 那正是系统已经知道答案却不肯说的时候。
//
// GRAPH-07 之后新建的边不可能空假设（前后端各拦一道）。这道闸挡的是**别的来路**：
// 早于该规则入库的边、批量导入、以及将来任何绕过 UI 的写入。闸门 NEVER 假设
// 上游一定干净——它要在拿到数据的那一刻自己看一眼。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { GenerateGate } from "./GenerateGate";

const SOURCE = readFileSync(join(__dirname, "GenerateGate.tsx"), "utf8");
// 六次同一个坑之后抽出来的共享口径：先剥注释再扫，否则「解释自己不做 X 的那句话」
// 会被当成做了 X（web/test-utils/source.ts 的 docstring 记了那六处）。
const CODE = codeOnly(SOURCE);

const CLEAN_EDGES = [
  { edgeId: "e-1", fromNodeId: "n-1", toNodeId: "n-2", hypothesis: "共用供应链" },
  { edgeId: "e-2", fromNodeId: "n-2", toNodeId: "n-3", hypothesis: "同一监管口径" },
];
const DIRTY_EDGES = [
  ...CLEAN_EDGES,
  { edgeId: "e-3", fromNodeId: "n-1", toNodeId: "n-3", hypothesis: "" },
  { edgeId: "e-4", fromNodeId: "n-3", toNodeId: "n-4", hypothesis: "   " },
];

describe("GenerateGate（空假设阻断 + 摘要条）", () => {
  it("有空假设边：生成按钮置灰，且点它不触发生成", () => {
    const onGenerate = vi.fn();
    render(
      <GenerateGate edges={DIRTY_EDGES} primaryNodeId="n-1" onGenerate={onGenerate} />,
    );

    const button = screen.getByTestId("generate-button");
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onGenerate).not.toHaveBeenCalled();
  });

  it("计数徽章报出**几条**缺假设：空串与纯空白都算", () => {
    render(<GenerateGate edges={DIRTY_EDGES} primaryNodeId="n-1" onGenerate={vi.fn()} />);

    const badge = screen.getByTestId("generate-gate-badge");
    expect(badge).toHaveAttribute("data-count", "2");
    expect(badge.textContent).toContain("2");
  });

  it("点徽章逐条定位：把缺假设的边 id 交出去，NEVER 只说一句「有问题」", () => {
    const onLocate = vi.fn();
    render(
      <GenerateGate
        edges={DIRTY_EDGES}
        primaryNodeId="n-1"
        onGenerate={vi.fn()}
        onLocate={onLocate}
      />,
    );

    fireEvent.click(screen.getByTestId("generate-gate-badge"));

    expect(onLocate).toHaveBeenCalledTimes(1);
    expect(onLocate).toHaveBeenCalledWith(["e-3", "e-4"]);
  });

  it("阴性对照：边都写了假设时按钮可用且点得动", () => {
    const onGenerate = vi.fn();
    render(
      <GenerateGate edges={CLEAN_EDGES} primaryNodeId="n-1" onGenerate={onGenerate} />,
    );

    const button = screen.getByTestId("generate-button");
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onGenerate).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("generate-gate-badge")).toBeNull();
  });

  it("摘要条三项都在：primary / 边数 / 假设完整度", () => {
    render(<GenerateGate edges={DIRTY_EDGES} primaryNodeId="n-1" onGenerate={vi.fn()} />);

    const bar = screen.getByTestId("graph-summary-bar");
    expect(bar).toHaveAttribute("data-primary-node-id", "n-1");
    expect(bar).toHaveAttribute("data-edge-count", "4");
    expect(bar).toHaveAttribute("data-hypothesis-complete", "2");
    expect(bar).toHaveAttribute("data-hypothesis-total", "4");
  });

  it("没有 primary 时如实说没有：NEVER 挑一个节点冒充主", () => {
    render(<GenerateGate edges={CLEAN_EDGES} primaryNodeId={null} onGenerate={vi.fn()} />);

    const bar = screen.getByTestId("graph-summary-bar");
    expect(bar).toHaveAttribute("data-primary-node-id", "");
    expect(screen.getByTestId("graph-summary-primary").textContent).toBeTruthy();
    // 主是「这张图在讲哪件事」，挑一个冒充等于替用户回答了那个问题
    expect(bar.getAttribute("data-primary-node-id")).not.toBe("n-1");
  });

  it("空图不谎报完整：零条边时完整度是 0/0 而不是「全都齐了」", () => {
    render(<GenerateGate edges={[]} primaryNodeId={null} onGenerate={vi.fn()} />);

    const bar = screen.getByTestId("graph-summary-bar");
    expect(bar).toHaveAttribute("data-edge-count", "0");
    expect(bar).toHaveAttribute("data-hypothesis-complete", "0");
    expect(bar).toHaveAttribute("data-hypothesis-total", "0");
    // 一张空图没有可生成的东西：按钮同样不可点，但**理由不是缺假设**
    expect(screen.getByTestId("generate-button")).toBeDisabled();
    expect(screen.queryByTestId("generate-gate-badge")).toBeNull();
  });

  it("闸门自己看数据，不接受外部传进来的「已检查过」结论", () => {
    // props 面不留 hasEmptyHypothesis / isValid 这类由调用方给的判断
    expect(CODE).not.toMatch(/hasEmpty|isValid/);
    // 判断就在本文件里做：拿到 edges 的那一刻自己数一遍
    expect(CODE).toContain("hypothesis.trim()");
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .map((l) => l.replace(/\/\/.*$/, ""))
      .join("\n");
    expect(code).not.toMatch(/[一-鿿]/);
  });
});
