// HOTSPOT-01 验收：六信息槽齐全；缺失逐槽隐藏；主行恒 name_native。
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { HotspotCard } from "./HotspotCard";

const NATIVE = "全固体電池の量産ライン";
const display = {
  text: "All-solid-state battery line",
  translated: true,
  translator: "identity@v1",
  source_field: "name_native",
};

const full = {
  nameNative: NATIVE,
  nameLang: "ja",
  nameDisplay: display,
  firstSeen: "2026-08-01",
  region: "JP",
  stale: true,
  verdict: "C_opportunity",
};

describe("HotspotCard", () => {
  it("六信息槽齐全", () => {
    render(<HotspotCard {...full} />);
    for (const id of [
      "native-primary",
      "native-secondary",
      "hotspot-first-seen",
      "hotspot-region",
      "hotspot-stale",
      "hotspot-verdict",
    ]) {
      expect(screen.getByTestId(id)).toBeTruthy();
    }
  });

  it("主行恒 name_native（组件树断言：走 NativeName，不另写一份）", () => {
    render(<HotspotCard {...full} />);
    expect(screen.getByTestId("native-primary").textContent).toBe(NATIVE);
  });

  it("译名存在时也 NEVER 取代主行", () => {
    render(<HotspotCard {...full} />);
    expect(screen.getByTestId("native-primary").textContent).not.toBe(display.text);
    expect(screen.getByTestId("native-secondary").textContent).toContain(display.text);
  });

  it("字段缺失逐槽隐藏，NEVER 假数据占位", () => {
    render(<HotspotCard nameNative={NATIVE} nameLang="ja" />);
    for (const id of [
      "native-secondary",
      "hotspot-first-seen",
      "hotspot-region",
      "hotspot-stale",
      "hotspot-verdict",
    ]) {
      expect(screen.queryByTestId(id)).toBeNull();
    }
    const card = screen.getByTestId("hotspot-card");
    for (const placeholder of ["—", "暂无", "N/A", "null", "undefined"]) {
      expect(card.textContent).not.toContain(placeholder);
    }
  });

  it("stale=false 与 stale 未判定都不显示陈旧标记（两者都不是「陈旧」）", () => {
    render(<HotspotCard nameNative={NATIVE} stale={false} />);
    expect(screen.queryByTestId("hotspot-stale")).toBeNull();
    render(<HotspotCard nameNative={NATIVE} />);
    expect(screen.queryByTestId("hotspot-stale")).toBeNull();
  });

  it("未归区时不显示地区槽 —— NEVER 猜一个区填上", () => {
    render(<HotspotCard nameNative={NATIVE} region={null} />);
    expect(screen.queryByTestId("hotspot-region")).toBeNull();
  });

  it("只有主行也能渲染（最小可用态）", () => {
    render(<HotspotCard nameNative={NATIVE} />);
    expect(screen.getByTestId("native-primary").textContent).toBe(NATIVE);
  });
});
