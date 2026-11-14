/**
 * UI-05 · 收藏图书馆屏（v2 屏 2.15）。
 *
 * 两条最要紧的判据：
 *
 * 1. **stale 只由后端说了算**——前端 NEVER 按时间戳推断，
 *    且「没判过」NEVER 显示成「最新」；
 * 2. **列表 NEVER 出现空壳**——内容不在了就说内容不在了。
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import { Suspense, type ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FavoritesLibrary, type FavoriteItem } from
  "../../components/favorites-library/FavoritesLibrary";
import FavoritesPage from "../../app/favorites/page";
import zh from "../../messages/zh.json";

let fetchMock: ReturnType<typeof vi.fn>;

function jsonOnce(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => "application/json" },
    json: async () => body,
  };
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

async function renderAsync(ui: ReactElement) {
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(<Suspense fallback={null}>{ui}</Suspense>);
  });
  return result;
}

const item = (over: Partial<FavoriteItem> = {}): FavoriteItem => ({
  favoriteId: "fav-1",
  targetKind: "cluster",
  targetId: "c-1",
  hasSnapshot: true,
  stale: false,
  ...over,
});

const state = (c: HTMLElement): string | null | undefined =>
  c.querySelector("[data-favorites-state]")?.getAttribute("data-favorites-state");

describe("UI-05 · 三态分得开", () => {
  it("没查过 → 「接口未提供」，NEVER 说「还没有收藏」", () => {
    const { container } = render(<FavoritesLibrary favorites={null} />);

    expect(state(container)).toBe("not_provided");
    expect(screen.getByText(zh["favorites.not_provided"])).toBeTruthy();
    expect(screen.queryByText(zh["favorites.empty"])).toBeNull();
  });

  it("查过了、确实一条都没有 → 空态 + 去广场的入口", () => {
    const { container } = render(<FavoritesLibrary favorites={[]} />);

    expect(state(container)).toBe("empty");
    expect(screen.getByText(zh["favorites.empty"])).toBeTruthy();
    expect(container.querySelector("a")?.getAttribute("href")).toBe("/plaza");
  });

  it("两种「没有收藏」用不同标记（否则界面上分不出来）", () => {
    const a = render(<FavoritesLibrary favorites={null} />);
    const b = render(<FavoritesLibrary favorites={[]} />);

    expect(state(a.container)).not.toBe(state(b.container));
  });
});

describe("UI-05 · stale 只由后端说了算", () => {
  it("后端说陈旧就标陈旧", () => {
    render(<FavoritesLibrary favorites={[item({ stale: true })]} />);

    expect(screen.getByText(zh["favorites.stale.yes"])).toBeTruthy();
  });

  it("后端说不陈旧就标最新", () => {
    render(<FavoritesLibrary favorites={[item({ stale: false })]} />);

    expect(screen.getByText(zh["favorites.stale.no"])).toBeTruthy();
  });

  it("**没判过 NEVER 显示成「最新」**", () => {
    const { container } = render(
      <FavoritesLibrary favorites={[item({ stale: null })]} />);

    expect(screen.getByText(zh["favorites.stale.not_checked"])).toBeTruthy();
    expect(screen.queryByText(zh["favorites.stale.no"])).toBeNull();
    expect(container.querySelector("[data-favorite-stale]")?.getAttribute(
      "data-favorite-stale")).toBe("not_checked");
  });

  it("三种状态各有各的机器可读标记", () => {
    const { container } = render(
      <FavoritesLibrary favorites={[
        item({ favoriteId: "a", stale: true }),
        item({ favoriteId: "b", stale: false }),
        item({ favoriteId: "c", stale: null }),
      ]} />);
    const marks = [...container.querySelectorAll("[data-favorite-stale]")]
      .map((n) => n.getAttribute("data-favorite-stale"));

    expect(new Set(marks).size).toBe(3);
  });
});

describe("UI-05 · 列表 NEVER 出现空壳", () => {
  it("内容不在了就说内容不在了", () => {
    const { container } = render(
      <FavoritesLibrary favorites={[item({ hasSnapshot: false })]} />);

    expect(container.querySelector("[data-favorite-no-content]")).toBeTruthy();
    expect(screen.getByText(zh["favorites.content_gone"])).toBeTruthy();
  });

  it("有内容时不显示那句话", () => {
    const { container } = render(
      <FavoritesLibrary favorites={[item({ hasSnapshot: true })]} />);

    expect(container.querySelector("[data-favorite-no-content]")).toBeNull();
  });
});

describe("UI-05 · 零计算", () => {
  it("顺序照后端给的来，不排序", () => {
    const { container } = render(
      <FavoritesLibrary favorites={[
        item({ favoriteId: "z", targetId: "z-1" }),
        item({ favoriteId: "a", targetId: "a-1" }),
      ]} />);
    const shown = [...container.querySelectorAll(".favorites__target")]
      .map((n) => n.textContent);

    expect(shown).toEqual(["z-1", "a-1"]);
  });
});

describe("UI-05 · 屏本体", () => {
  // 这两条**本来钉的是「屏上写死、一个请求都不发」**——那是这一族还没挂上时的实情。
  // `WIRE-11` 把它挂上、`WIRE-12` 让它在没有存储面时照实说 `not_provided` 之后，
  // 屏改成真取数，这两条于是**同时红**。红得对：它们就是来提醒
  //「这一屏的取数口径变了，回来确认新口径」的。以下是改后的口径。

  it("屏上真的发了那次请求——NEVER 再把答案写死在页面里", async () => {
    fetchMock.mockResolvedValue(jsonOnce({ status: "not_provided", reason: "r" }));

    await renderAsync(<FavoritesPage />);

    expect(screen.getByText(zh["favorites.title"])).toBeTruthy();
    expect(fetchMock.mock.calls.map((c) => String(c[0])).some(
      (u) => u.includes("/favorites"))).toBe(true);
  });

  it("后端说 not_provided → 屏上「接口未提供」，NEVER 说成空态", async () => {
    fetchMock.mockResolvedValue(jsonOnce({
      status: "not_provided",
      reason: "收藏还没有存储面（迁移里没有 favorites 表）",
    }));

    await renderAsync(<FavoritesPage />);

    await waitFor(() => {
      expect(screen.getByText(zh["favorites.not_provided"])).toBeTruthy();
    });
    expect(screen.queryByText(zh["favorites.empty"])).toBeNull();
  });

  it("后端真给了空表 → 屏上「一条都没有」，NEVER 说成「没查过」", async () => {
    // **缝的另一侧**：`{"items": []}` 是「查过了、确实没有」。
    // 只认 `not_provided` 一种的话，这个意思在屏上就没地方表达了。
    fetchMock.mockResolvedValue(jsonOnce({ items: [] }));

    await renderAsync(<FavoritesPage />);

    await waitFor(() => {
      expect(screen.getByText(zh["favorites.empty"])).toBeTruthy();
    });
    expect(screen.queryByText(zh["favorites.not_provided"])).toBeNull();
  });

  it("后端给了收藏 → 逐条渲染，NEVER 前端再算一遍 stale", async () => {
    fetchMock.mockResolvedValue(jsonOnce({
      items: [{
        favorite_id: "fav-9", target_kind: "cluster", target_id: "c-9",
        has_snapshot: true, snapshot_stale: true,
      }],
    }));

    const { container } = await renderAsync(<FavoritesPage />);

    await waitFor(() => {
      expect(container.querySelector('[data-favorite-stale="true"]')).not.toBeNull();
    });
    expect(screen.getByText(zh["favorites.stale.yes"])).toBeTruthy();
  });

  it("本屏用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of [
      "favorites.title", "favorites.meta", "favorites.not_provided",
      "favorites.empty", "favorites.to_plaza", "favorites.stale.yes",
      "favorites.stale.no", "favorites.stale.not_checked", "favorites.content_gone",
    ]) {
      expect(zh[key as keyof typeof zh]).toBeTruthy();
      expect(en[key]).toBeTruthy();
    }
  });
});
