// GRAPH-07 验收（前端半）：连线松手弹假设框；空值**不发请求**。
//
// 为什么空值要在前端就拦住：让请求飞出去再被 422 弹回来，用户看到的是一次失败，
// 而他其实只是还没写。更糟的是画布上那根线该不该留——发出去了就得处理「服务端拒了
// 但线还在」的中间态。不发，就没有这个中间态。
//
// 服务端那一道是**独立的**一道（tests/v04/graph/test_edge_hypothesis.py），
// 不是这一道的回声：curl 一发照样能建空假设边。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GraphEdgeDraft } from "./GraphEdgeDraft";

const SOURCE = readFileSync(join(__dirname, "GraphEdgeDraft.tsx"), "utf8");

function setup(overrides: Record<string, unknown> = {}) {
  const onCreate = vi.fn().mockResolvedValue({ edgeId: "e-1" });
  const utils = render(
    <GraphEdgeDraft fromNodeId="n-1" toNodeId="n-2" onCreate={onCreate} {...overrides} />,
  );
  return { onCreate, ...utils };
}

describe("GraphEdgeDraft（连线 + 强制假设）", () => {
  it("松手即弹假设框，且此刻还没有边被建出来", () => {
    const { onCreate } = setup();

    expect(screen.getByTestId("graph-edge-hypothesis-input")).toBeInTheDocument();
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("空假设不发请求：提交被拦在本地", async () => {
    const { onCreate } = setup();

    fireEvent.click(screen.getByTestId("graph-edge-submit"));

    await screen.findByTestId("graph-edge-hypothesis-required");
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("只有空白同样不发：空格填不出一条假设", async () => {
    const { onCreate } = setup();

    fireEvent.change(screen.getByTestId("graph-edge-hypothesis-input"), {
      target: { value: "   \t " },
    });
    fireEvent.click(screen.getByTestId("graph-edge-submit"));

    await screen.findByTestId("graph-edge-hypothesis-required");
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("写了假设才发，且原样带上两端与文本（阴性对照：这条路是通的）", async () => {
    const { onCreate } = setup();

    fireEvent.change(screen.getByTestId("graph-edge-hypothesis-input"), {
      target: { value: "两者共用同一条供应链" },
    });
    fireEvent.click(screen.getByTestId("graph-edge-submit"));

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    expect(onCreate).toHaveBeenCalledWith({
      fromNodeId: "n-1",
      toNodeId: "n-2",
      hypothesis: "两者共用同一条供应链",
    });
  });

  it("方向不可互换：from → to 原样送出（有向边）", async () => {
    const { onCreate } = setup({ fromNodeId: "n-9", toNodeId: "n-3" });

    fireEvent.change(screen.getByTestId("graph-edge-hypothesis-input"), {
      target: { value: "上游变动会传导到下游" },
    });
    fireEvent.click(screen.getByTestId("graph-edge-submit"));

    await waitFor(() => expect(onCreate).toHaveBeenCalled());
    const arg = onCreate.mock.calls[0][0] as { fromNodeId: string; toNodeId: string };
    expect([arg.fromNodeId, arg.toNodeId]).toEqual(["n-9", "n-3"]);
  });

  it("取消连线不留半根线：草稿消失且什么都没发", () => {
    const onCancel = vi.fn();
    const { onCreate } = setup({ onCancel });

    fireEvent.click(screen.getByTestId("graph-edge-cancel"));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("服务端拒了（含 422 EMPTY_HYPOTHESIS）不谎报成功：出错误态且草稿还在", async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error("EMPTY_HYPOTHESIS"));
    render(
      <GraphEdgeDraft fromNodeId="n-1" toNodeId="n-2" onCreate={onCreate} />,
    );

    fireEvent.change(screen.getByTestId("graph-edge-hypothesis-input"), {
      target: { value: "有假设" },
    });
    fireEvent.click(screen.getByTestId("graph-edge-submit"));

    await screen.findByTestId("graph-edge-error");
    // 草稿还在 = 用户写的那句话没被清掉，改一下就能再提交
    expect(screen.getByTestId("graph-edge-hypothesis-input")).toHaveValue("有假设");
  });

  it("提交中不重复发：连点两下只发一次", async () => {
    let resolveIt: (v: unknown) => void = () => {};
    const pending = new Promise((r) => {
      resolveIt = r;
    });
    const onCreate = vi.fn().mockReturnValue(pending);
    render(<GraphEdgeDraft fromNodeId="n-1" toNodeId="n-2" onCreate={onCreate} />);

    fireEvent.change(screen.getByTestId("graph-edge-hypothesis-input"), {
      target: { value: "有假设" },
    });
    fireEvent.click(screen.getByTestId("graph-edge-submit"));
    fireEvent.click(screen.getByTestId("graph-edge-submit"));

    expect(onCreate).toHaveBeenCalledTimes(1);
    resolveIt({ edgeId: "e-1" });
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    // 剥注释的口径与 tools/i18n_scan.mjs 一致：块注释、整行 `//`、**行尾 `//`** 都不算
    // 界面文案（DEC-008：注释不发给用户）。比扫描器更严没有意义——严出来的红是假的。
    const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .map((l) => l.replace(/\/\/.*$/, ""))
      .join("\n");
    expect(code).not.toMatch(/[一-鿿]/);
  });
});
