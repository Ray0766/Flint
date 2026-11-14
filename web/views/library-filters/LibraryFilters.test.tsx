// FAV-04 验收：三过滤器可组合；空结果态有引导文案（key 化）。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { applyFilters, LibraryFilters } from "./LibraryFilters";
import type { LibraryItem } from "../library/Library";

const items: LibraryItem[] = [
  { favoriteId: "f-jp", nameNative: "電池", createdAt: "2026-08-01", region: "JP", verdictAtSave: "A_refuted" },
  { favoriteId: "f-us", nameNative: "半導体", createdAt: "2026-08-05", region: "US", verdictAtSave: "B_hard" },
  { favoriteId: "f-nil", nameNative: "材料", createdAt: "2026-08-10", region: null, verdictAtSave: null },
];
const ids = (f: Parameters<typeof applyFilters>[1]) =>
  applyFilters(items, f).map((i) => i.favoriteId);

describe("LibraryFilters", () => {
  it("未设即不过滤（空 filters 全通过）", () => {
    expect(ids({})).toEqual(["f-jp", "f-us", "f-nil"]);
  });

  it("region 单独生效", () => {
    expect(ids({ region: "JP" })).toEqual(["f-jp"]);
  });

  it("判定单独生效，且按**收藏当时**的判定筛", () => {
    expect(ids({ verdictAtSave: "B_hard" })).toEqual(["f-us"]);
  });

  it("日期区间是闭区间，单端也生效", () => {
    expect(ids({ from: "2026-08-05" })).toEqual(["f-us", "f-nil"]);
    expect(ids({ to: "2026-08-05" })).toEqual(["f-jp", "f-us"]);
    expect(ids({ from: "2026-08-01", to: "2026-08-01" })).toEqual(["f-jp"]);
  });

  it("三者可组合（合取）", () => {
    expect(ids({ region: "US", verdictAtSave: "B_hard", from: "2026-08-01" })).toEqual(["f-us"]);
    expect(ids({ region: "US", verdictAtSave: "A_refuted" })).toEqual([]);
  });

  it("null 值不参与过滤：未归区的项 NEVER 被当成某个区", () => {
    expect(ids({ region: "JP" })).not.toContain("f-nil");
    expect(ids({})).toContain("f-nil");
  });

  it("空结果态有引导文案", () => {
    render(<LibraryFilters items={items} filters={{ region: "FR" }} />);
    expect(screen.getByTestId("library-filtered-empty")).toBeTruthy();
    expect(screen.getByTestId("library-filtered-empty-hint").textContent).toBeTruthy();
  });

  it("空态文案 key 化（源码里无 CJK 字面量）", () => {
    const source = readFileSync(join(__dirname, "LibraryFilters.tsx"), "utf8");
    // 剥注释要连**块注释**一起剥：JSDoc（/** 中文说明 */）不以 // 开头，
    // 只滤 // 行会把说明文字当成代码——首轮就是这么红的。
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    expect(code).not.toMatch(/[\u4e00-\u9fff]/);
    expect(source).toContain('t("library.filtered.empty")');
  });

  it("有结果时不显示空态", () => {
    render(<LibraryFilters items={items} filters={{ region: "JP" }} />);
    expect(screen.queryByTestId("library-filtered-empty")).toBeNull();
    expect(screen.getByTestId("library-filtered")).toHaveAttribute("data-count", "1");
  });
});
