// GRAPH-03 验收：region/日期/stale/判定辅助槽齐全；子组件复用不复制。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GraphNode } from "./GraphNode";

const NATIVE = "全固体電池の量産ライン";
const full = {
  nodeId: "n-1",
  sourceKind: "cluster" as const,
  nameNative: NATIVE,
  nameLang: "ja",
  nameDisplay: {
    text: "All-solid-state battery line",
    translated: true,
    translator: "identity@v1",
    source_field: "name_native",
  },
  firstSeen: "2026-08-01",
  region: "JP",
  stale: true,
  verdict: "C_opportunity",
};

describe("GraphNode", () => {
  it("四个辅助槽齐全（region/日期/stale/判定）", () => {
    render(<GraphNode {...full} />);
    for (const id of [
      "hotspot-region",
      "hotspot-first-seen",
      "hotspot-stale",
      "hotspot-verdict",
    ]) {
      expect(screen.getByTestId(id)).toBeTruthy();
    }
  });

  it("主行仍是 name_native（经 NativeName，非本组件另写）", () => {
    render(<GraphNode {...full} />);
    expect(screen.getByTestId("native-primary").textContent).toBe(NATIVE);
  });

  it("子组件**复用不复制**：源码 import HotspotCard，且不自绘任何槽", () => {
    const source = readFileSync(join(__dirname, "GraphNode.tsx"), "utf8");
    expect(source).toContain('from "../hotspot-card/HotspotCard"');
    const code = source.split("\n").filter((l) => !l.trim().startsWith("//")).join("\n");
    for (const copied of [
      "hotspot-region",
      "hotspot-first-seen",
      "hotspot-stale",
      "hotspot-verdict",
      "native-primary",
    ]) {
      expect(code).not.toContain(copied);
    }
  });

  it("节点带 source_kind：它是既有实体的投影，不是新造的东西（§6-H8）", () => {
    render(<GraphNode {...full} />);
    expect(screen.getByTestId("graph-node")).toHaveAttribute("data-source-kind", "cluster");
  });

  it("primary 默认 false（I12-1：图内 primary 恒 ≤1，默认不抢）", () => {
    render(<GraphNode {...full} />);
    expect(screen.getByTestId("graph-node")).toHaveAttribute("data-primary", "false");
    render(<GraphNode {...full} nodeId="n-2" primary />);
    expect(screen.getAllByTestId("graph-node")[1]).toHaveAttribute("data-primary", "true");
  });

  it("字段缺失时槽位仍逐个隐藏（继承 HotspotCard 的纪律，不因复用而走样）", () => {
    render(<GraphNode nodeId="n-3" sourceKind="topic" nameNative={NATIVE} />);
    for (const id of ["hotspot-region", "hotspot-stale", "hotspot-verdict"]) {
      expect(screen.queryByTestId(id)).toBeNull();
    }
  });
});
