// PLAZA-04：三动作各自独立 + 点击排除区（HOTSPOT-02 既有判据）+ 三种「不成」各说各的话。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlazaCards } from "./PlazaCards";
import { addToWorkbench, favoriteCluster, shareCluster } from "./cardActions";
import { t } from "../../lib/i18n/t";
import type { PlazaCluster } from "../../lib/viewsClient";

const cluster = (i: number): PlazaCluster => ({
  cluster_id: `c${i}`,
  canonical_name: `热点 ${i}`,
  category_id: "cat-ai",
  status: "active",
  by_source: { weibo: 100 },
  total_heat: 100 - i,
});

function reply(status: number, body: unknown) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

afterEach(() => vi.unstubAllGlobals());

describe("PLAZA-04 卡片三动作", () => {
  it("三个动作各自独立触发，NEVER 一按全按", async () => {
    const seen: string[] = [];
    vi.stubGlobal("fetch", vi.fn((url: unknown) => {
      seen.push(String(url));
      return reply(200, { ok: true });
    }));
    const { container } = render(<PlazaCards clusters={[cluster(0)]} />);

    fireEvent.click(screen.getByTestId("action-favorite"));
    await waitFor(() => expect(seen).toHaveLength(1));
    expect(seen[0]).toContain("/favorites");

    fireEvent.click(screen.getByTestId("action-share"));
    await waitFor(() => expect(seen).toHaveLength(2));
    expect(seen[1]).toContain("/shares");

    fireEvent.click(screen.getByTestId("action-workbench"));
    await waitFor(() => expect(seen).toHaveLength(3));
    expect(seen[2]).toContain("/workbenches");
    expect(container).toBeTruthy();
  });

  it("**双断言**：点动作不跳转 · 点卡面跳转", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(200, { ok: true })));
    const onSelect = vi.fn();
    const { container } = render(
      <PlazaCards clusters={[cluster(0)]} onSelectCluster={onSelect} />,
    );

    // ① 点动作：请求发出去了，而卡片的跳转 NEVER 被触发。
    fireEvent.click(screen.getByTestId("action-favorite"));
    await waitFor(() => expect(screen.queryByTestId("action-outcome")).not.toBeNull());
    expect(onSelect).not.toHaveBeenCalled();

    // ② 点卡面：照常跳转——排除区 NEVER 把整张卡也挡住。
    fireEvent.click(container.querySelector("[data-plaza-list] .hotspot-card")!);
    expect(onSelect).toHaveBeenCalledWith("c0");
  });

  it("「还没接」照实说，NEVER 报成功", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      reply(200, { status: "not_provided", reason: "收藏还没有存储面" })));
    render(<PlazaCards clusters={[cluster(0)]} />);

    fireEvent.click(screen.getByTestId("action-favorite"));
    await waitFor(() => {
      const line = screen.getByTestId("action-outcome");
      expect(line.getAttribute("data-outcome-kind")).toBe("not_provided");
      expect(line.textContent).toBe(t("card.action.not_provided"));
    });
    expect(screen.queryByText(t("card.action.done"))).toBeNull();
  });

  it("「这类目标不支持」与「还没接」NEVER 共用一句话", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      reply(422, { detail: { allowed: ["deliverable", "graph", "topic"] } })));
    render(<PlazaCards clusters={[cluster(0)]} />);

    fireEvent.click(screen.getByTestId("action-share"));
    await waitFor(() => {
      const line = screen.getByTestId("action-outcome");
      expect(line.getAttribute("data-outcome-kind")).toBe("unsupported");
      // 允许清单**来自服务端**，前端不自带一份。
      expect(line.textContent).toContain("deliverable / graph / topic");
    });
    expect(screen.queryByText(t("card.action.not_provided"))).toBeNull();
  });

  it("框架的 404（没有 code）读成「还没接」，NEVER 读成「这一条不存在」", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(404, { detail: "Not Found" })));
    render(<PlazaCards clusters={[cluster(0)]} />);

    fireEvent.click(screen.getByTestId("action-workbench"));
    await waitFor(() =>
      expect(screen.getByTestId("action-outcome").getAttribute("data-outcome-kind"))
        .toBe("not_provided"));
  });

  it("带 code 的 404 是真的「这一条不存在」，走 failed 而不是「还没接」", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      reply(404, { code: "NOT_FOUND", message: "这个簇不在" })));
    render(<PlazaCards clusters={[cluster(0)]} />);

    fireEvent.click(screen.getByTestId("action-workbench"));
    await waitFor(() => {
      const line = screen.getByTestId("action-outcome");
      expect(line.getAttribute("data-outcome-kind")).toBe("failed");
      // 后端自己的说明原样带出来，NEVER 改写成一句通用的话。
      expect(line.textContent).toBe("这个簇不在");
    });
  });

  it("一张卡的答复 NEVER 显示到另一张卡上", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      reply(200, { status: "not_provided", reason: "x" })));
    const { container } = render(
      <PlazaCards clusters={[cluster(0), cluster(1)]} />,
    );

    const items = [...container.querySelectorAll("[data-plaza-list] > li")];
    fireEvent.click(items[0].querySelector("[data-testid='action-favorite']")!);
    await waitFor(() =>
      expect(items[0].querySelector("[data-testid='action-outcome']")).not.toBeNull());
    expect(items[1].querySelector("[data-testid='action-outcome']")).toBeNull();
  });

  it("结果挂在**哪个动作**上是记着的（三个动作各自独立）", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(200, { ok: true })));
    render(<PlazaCards clusters={[cluster(0)]} />);

    fireEvent.click(screen.getByTestId("action-share"));
    await waitFor(() =>
      expect(screen.getByTestId("action-outcome").getAttribute("data-outcome-of"))
        .toBe("share"));
  });

  it("按钮有字，NEVER 是三个空按钮（改前就是空的：读屏念不出、屏上 0 像素）", () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(200, {})));
    render(<PlazaCards clusters={[cluster(0)]} />);

    expect(screen.getByTestId("action-favorite").textContent).toBe(t("card.action.favorite"));
    expect(screen.getByTestId("action-workbench").textContent).toBe(t("card.action.workbench"));
    expect(screen.getByTestId("action-share").textContent).toBe(t("card.action.share"));
  });

  it("端点与请求体：三条各打各的，target_id 恒是那张卡的簇 id", async () => {
    const calls: [string, unknown][] = [];
    const fetchMock = vi.fn((url: unknown, init: unknown) => {
      calls.push([String(url), JSON.parse(String((init as RequestInit).body))]);
      return reply(200, {});
    });
    vi.stubGlobal("fetch", fetchMock);

    await favoriteCluster("", "c-9");
    await shareCluster("", "c-9");
    await addToWorkbench("", "c-9");

    expect(calls.map(([u]) => u)).toEqual(["/favorites", "/shares", "/workbenches"]);
    for (const [, body] of calls) {
      expect(JSON.stringify(body)).toContain("c-9");
    }
  });
});
