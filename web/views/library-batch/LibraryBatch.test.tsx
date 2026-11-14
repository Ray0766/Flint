// FAV-05（前端半）验收：整体回滚时不留假成功态；报错清单逐条摊开。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LibraryBatch, type BatchResult } from "./LibraryBatch";

const ids = ["f-1", "f-2", "f-3"];

describe("LibraryBatch", () => {
  it("未选中时提交按钮禁用（空批量在后端也是 ValueError）", () => {
    render(<LibraryBatch favoriteIds={ids} submit={vi.fn()} />);
    expect(screen.getByTestId("batch-submit")).toBeDisabled();
  });

  it("选中项才进提交集合", async () => {
    const submit = vi.fn(async (): Promise<BatchResult> => ({ ok: true, affected: ["f-1"] }));
    render(<LibraryBatch favoriteIds={ids} submit={submit} />);
    fireEvent.click(screen.getByTestId("batch-select-f-1"));
    fireEvent.click(screen.getByTestId("batch-submit"));
    await waitFor(() => expect(submit).toHaveBeenCalledWith(["f-1"]));
  });

  it("NEVER 乐观更新：请求返回前不显示成功态", async () => {
    let resolve!: (r: BatchResult) => void;
    const submit = vi.fn(() => new Promise<BatchResult>((r) => (resolve = r)));
    render(<LibraryBatch favoriteIds={ids} submit={submit} />);
    fireEvent.click(screen.getByTestId("batch-select-f-1"));
    fireEvent.click(screen.getByTestId("batch-submit"));
    expect(screen.queryByTestId("batch-ok")).toBeNull();      // 还没回
    resolve({ ok: true, affected: ["f-1"] });
    await waitFor(() => expect(screen.getByTestId("batch-ok")).toBeTruthy());
  });

  it("整体回滚时不留任何成功态", async () => {
    const submit = vi.fn(
      async (): Promise<BatchResult> => ({
        ok: false,
        failures: [{ favorite_id: "f-2", reason: "收藏不存在" }],
      }),
    );
    render(<LibraryBatch favoriteIds={ids} submit={submit} />);
    fireEvent.click(screen.getByTestId("batch-select-f-1"));
    fireEvent.click(screen.getByTestId("batch-submit"));
    await waitFor(() => expect(screen.getByTestId("batch-failures")).toBeTruthy());
    expect(screen.queryByTestId("batch-ok")).toBeNull();
  });

  it("报错清单逐条摊开：哪条 + 为什么", async () => {
    const failures = [
      { favorite_id: "f-2", reason: "收藏不存在" },
      { favorite_id: "f-3", reason: "不属于当前用户" },
    ];
    const submit = vi.fn(async (): Promise<BatchResult> => ({ ok: false, failures }));
    render(<LibraryBatch favoriteIds={ids} submit={submit} />);
    fireEvent.click(screen.getByTestId("batch-select-f-1"));
    fireEvent.click(screen.getByTestId("batch-submit"));
    await waitFor(() => expect(screen.getByTestId("batch-failure-f-2")).toBeTruthy());
    expect(screen.getByTestId("batch-failure-f-2").textContent).toBe("收藏不存在");
    expect(screen.getByTestId("batch-failure-f-3").textContent).toBe("不属于当前用户");
  });

  it("组件不自己发请求：submit 由上层注入", () => {
    const submit = vi.fn(async (): Promise<BatchResult> => ({ ok: true, affected: [] }));
    render(<LibraryBatch favoriteIds={ids} submit={submit} />);
    expect(submit).not.toHaveBeenCalled();
  });
});
