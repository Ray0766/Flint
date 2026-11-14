// HOTSPOT-09 验收（前端半）：分享菜单三项（一键入台 / 分享给朋友 / 只读外链）。
//
// acceptance①「入台项调 GRAPH-02 端点（E1 零新链路）」：入台与工作台里的 F1 是
// **同一个动作**，因此走同一个端点。另开一条链路的坏处不是多写代码，而是幂等键会
// 分叉——同一个热点从广场入台一次、从工作台入台一次，画布上会出现两张一模一样的卡片。
//
// acceptance②「friend 项渲染『即将上线』」：后端那一半抛 NotImplementedError
// （tests/v04/share/test_friend_stub.py）。前端这一半要做到的是：**点它什么都不发**——
// 一个看起来能点、点了却悄悄失败的菜单项，比明说「即将上线」糟得多。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ShareMenu } from "./ShareMenu";

type Call = { url: string; method: string; body: unknown };

function spyFetch(calls: Call[]): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({
      url: String(input),
      method: (init?.method ?? "GET").toUpperCase(),
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    return new Response(JSON.stringify({ node_id: "n-1" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as unknown as typeof fetch;
}

function renderMenu(calls: Call[], overrides: Record<string, unknown> = {}) {
  return render(
    <ShareMenu
      workbenchId="wb-1"
      sourceKind="cluster"
      sourceId="c-1"
      fetchImpl={spyFetch(calls)}
      {...overrides}
    />,
  );
}

describe("ShareMenu（分享菜单）", () => {
  it("入台项调 GRAPH-02 端点：POST /workbenches/{id}/nodes，带 source_kind + source_id", async () => {
    const calls: Call[] = [];
    renderMenu(calls);

    fireEvent.click(screen.getByTestId("share-menu-add-to-workbench"));
    await vi.waitFor(() => expect(calls).toHaveLength(1));

    expect(calls[0].method).toBe("POST");
    expect(calls[0].url).toBe("/workbenches/wb-1/nodes");
    expect(calls[0].body).toEqual({ source_kind: "cluster", source_id: "c-1" });
  });

  it("零新链路：源码里只有这一个端点形态，NEVER 另起一条入台路径", () => {
    const source = readFileSync(join(__dirname, "ShareMenu.tsx"), "utf8");
    const endpoints = [...source.matchAll(/`\/[a-z0-9/{}$.\w-]*`/gi)].map((m) => m[0]);
    expect(endpoints).toEqual(["`/workbenches/${workbenchId}/nodes`"]);
  });

  it("入台成功后把 node_id 交给调用方：界面 NEVER 自己编一个节点 id", async () => {
    const calls: Call[] = [];
    const onAdded = vi.fn();
    renderMenu(calls, { onAdded });

    fireEvent.click(screen.getByTestId("share-menu-add-to-workbench"));
    await vi.waitFor(() => expect(onAdded).toHaveBeenCalledTimes(1));

    expect(onAdded).toHaveBeenCalledWith("n-1");
  });

  it("friend 项渲染「即将上线」且不可点：点它一个请求都不发", async () => {
    const calls: Call[] = [];
    renderMenu(calls);

    const friend = screen.getByTestId("share-menu-friend");
    expect(friend).toHaveAttribute("aria-disabled", "true");
    expect(friend.textContent).toBeTruthy();
    expect(friend.textContent).not.toBe("share.menu.friend"); // 取到了词条而非 key 回落

    fireEvent.click(friend);
    expect(calls).toHaveLength(0);
  });

  it("外链项只开入口，NEVER 当场铸一条链接", () => {
    const calls: Call[] = [];
    const onOpenShareLink = vi.fn();
    renderMenu(calls, { onOpenShareLink });

    fireEvent.click(screen.getByTestId("share-menu-share-link"));

    expect(onOpenShareLink).toHaveBeenCalledTimes(1);
    // 点一下菜单就 POST /share-links 等于悄悄铸出一条**公开可读**的链接
    expect(calls).toHaveLength(0);
  });

  it("三项都在，且入台恒为第一项（E1：菜单第一项就是入台）", () => {
    const calls: Call[] = [];
    renderMenu(calls);

    const items = screen.getAllByRole("menuitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveAttribute("data-testid", "share-menu-add-to-workbench");
  });

  it("入台失败不谎报成功：回调不被调用且给出失败态", async () => {
    const onAdded = vi.fn();
    const failing = (async () =>
      new Response("{}", { status: 500 })) as unknown as typeof fetch;
    render(
      <ShareMenu
        workbenchId="wb-1"
        sourceKind="cluster"
        sourceId="c-1"
        fetchImpl={failing}
        onAdded={onAdded}
      />,
    );

    fireEvent.click(screen.getByTestId("share-menu-add-to-workbench"));
    await screen.findByTestId("share-menu-error");

    expect(onAdded).not.toHaveBeenCalled();
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    const source = readFileSync(join(__dirname, "ShareMenu.tsx"), "utf8");
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    expect(code).not.toMatch(/[一-鿿]/);
  });
});
