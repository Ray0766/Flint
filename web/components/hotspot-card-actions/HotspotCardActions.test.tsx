// HOTSPOT-02 验收：三 handler 独立触发；动作区点击不冒泡到卡片跳转（双断言）。
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// NARROW-05: the buttons this suite drives are closed by the DEC-066 freeze
// (lib/frozen.ts). The code behind them is kept, so the suite turns the freeze
// off and keeps testing it; __tests__/app/frozen_entries.test.tsx checks that
// the entries are closed.
vi.mock("../../lib/frozen", async (importOriginal) => {
  const real = await importOriginal<typeof import("../../lib/frozen")>();
  const open = Object.fromEntries(Object.keys(real.FROZEN).map((k) => [k, false]));
  return { ...real, FROZEN: open, isFrozenNavHref: () => false };
});

import { HotspotCardActions } from "./HotspotCardActions";

function setup() {
  const onFavorite = vi.fn();
  const onAddToWorkbench = vi.fn();
  const onShare = vi.fn();
  const onCardClick = vi.fn();
  render(
    <div data-testid="card" onClick={onCardClick}>
      <HotspotCardActions
        onFavorite={onFavorite}
        onAddToWorkbench={onAddToWorkbench}
        onShare={onShare}
      />
    </div>,
  );
  return { onFavorite, onAddToWorkbench, onShare, onCardClick };
}

describe("HotspotCardActions", () => {
  it("收藏只触发收藏", () => {
    const h = setup();
    fireEvent.click(screen.getByTestId("action-favorite"));
    expect(h.onFavorite).toHaveBeenCalledTimes(1);
    expect(h.onAddToWorkbench).not.toHaveBeenCalled();
    expect(h.onShare).not.toHaveBeenCalled();
  });

  it("入台只触发入台", () => {
    const h = setup();
    fireEvent.click(screen.getByTestId("action-workbench"));
    expect(h.onAddToWorkbench).toHaveBeenCalledTimes(1);
    expect(h.onFavorite).not.toHaveBeenCalled();
    expect(h.onShare).not.toHaveBeenCalled();
  });

  it("分享只触发分享", () => {
    const h = setup();
    fireEvent.click(screen.getByTestId("action-share"));
    expect(h.onShare).toHaveBeenCalledTimes(1);
    expect(h.onFavorite).not.toHaveBeenCalled();
    expect(h.onAddToWorkbench).not.toHaveBeenCalled();
  });

  it("动作区点击不冒泡到卡片（三个按钮各验一次）", () => {
    for (const id of ["action-favorite", "action-workbench", "action-share"]) {
      const h = setup();
      fireEvent.click(screen.getAllByTestId(id).at(-1)!);
      expect(h.onCardClick).not.toHaveBeenCalled();
    }
  });

  it("动作区空白处点击同样不冒泡", () => {
    const h = setup();
    fireEvent.click(screen.getByTestId("card-actions"));
    expect(h.onCardClick).not.toHaveBeenCalled();
  });

  it("阴性对照：动作区**之外**的点击照常冒泡到卡片", () => {
    const h = setup();
    fireEvent.click(screen.getByTestId("card"));
    expect(h.onCardClick).toHaveBeenCalledTimes(1);
  });
});
