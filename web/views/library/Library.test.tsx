// FAV-03 验收：四维排序生效；卡片复用 HOTSPOT-01 组件（不复制）。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Library, SORT_KEYS, sortItems, type LibraryItem } from "./Library";

const items: LibraryItem[] = [
  { favoriteId: "f-b", nameNative: "電池", createdAt: "2026-08-02",
    region: "US", verdictAtSave: "B_hard", inWorkbench: false },
  { favoriteId: "f-a", nameNative: "半導体", createdAt: "2026-08-01",
    region: "JP", verdictAtSave: "A_refuted", inWorkbench: true },
  { favoriteId: "f-c", nameNative: "材料", createdAt: "2026-08-03",
    region: null, verdictAtSave: null, inWorkbench: false },
];

const ids = (key: Parameters<typeof sortItems>[1]) =>
  sortItems(items, key).map((i) => i.favoriteId);

describe("Library", () => {
  it("四个排序键齐全", () => {
    expect([...SORT_KEYS]).toEqual([
      "created_at", "region", "verdict_at_save", "in_workbench",
    ]);
  });

  it("created_at 排序生效", () => {
    expect(ids("created_at")).toEqual(["f-a", "f-b", "f-c"]);
  });

  it("region 排序生效，未归区排最后（NEVER 猜一个区）", () => {
    expect(ids("region")).toEqual(["f-a", "f-b", "f-c"]);
  });

  it("verdict_at_save 用**收藏当时**的判定，不是当前判定", () => {
    expect(ids("verdict_at_save")).toEqual(["f-a", "f-b", "f-c"]);
    const source = readFileSync(join(__dirname, "Library.tsx"), "utf8");
    expect(source).toContain("verdictAtSave");
  });

  it("in_workbench 排序：已入台在前", () => {
    expect(ids("in_workbench")).toEqual(["f-a", "f-b", "f-c"]);
  });

  it("排序稳定：同分项按 favoriteId 兜底，NEVER 每次刷新换位置", () => {
    const same: LibraryItem[] = [
      { favoriteId: "f-z", nameNative: "x", createdAt: "2026-08-01" },
      { favoriteId: "f-a", nameNative: "y", createdAt: "2026-08-01" },
    ];
    expect(sortItems(same, "created_at").map((i) => i.favoriteId)).toEqual(["f-a", "f-z"]);
  });

  it("卡片复用 HotspotCard（不复制）", () => {
    const source = readFileSync(join(__dirname, "Library.tsx"), "utf8");
    expect(source).toContain('from "../../components/hotspot-card/HotspotCard"');
    const code = source.split("\n").filter((l) => !l.trim().startsWith("//")).join("\n");
    for (const copied of ["hotspot-region", "hotspot-verdict", "native-primary"]) {
      expect(code).not.toContain(copied);
    }
  });

  it("渲染时主行仍是 name_native", () => {
    render(<Library items={items} />);
    expect(screen.getAllByTestId("native-primary")[0].textContent).toBe("半導体");
  });

  it("空态是明确状态，不是加载失败", () => {
    render(<Library items={[]} />);
    expect(screen.getByTestId("library-empty")).toBeTruthy();
    expect(screen.queryByTestId("library")).toBeNull();
  });
});
