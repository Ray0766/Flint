/**
 * UI-03 · 热点工作台·图谱上屏（v2 屏 2.16）。
 *
 * 判据里最要紧的一条：**「没查过」不是「空图」**。
 * 「你的工作台是空的」是一句只有查过才有资格说的话。
 *
 * `PERSIST-02` 建了 `GET /workbenches/{id}`，这一屏因此从「一个请求都不发」
 * 变成「去取那张图」。三态没有合并，只是**多了真的能取到的那一态**：
 * 取到有节点 → 画布；取到空图 → 空图引导；取不到 → 接口未提供。
 */
import { render, screen, act } from "@testing-library/react";
import { Suspense } from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { GraphWorkbench, type WorkbenchGraph } from
  "../../components/graph-workbench/GraphWorkbench";
import WorkbenchPage from "../../app/workbenches/[id]/page";
import zh from "../../messages/zh.json";

const READY: WorkbenchGraph = {
  nodes: [
    { nodeId: "n-1", sourceKind: "cluster", nameNative: "某热点", primary: true },
    { nodeId: "n-2", sourceKind: "evidence_card", nameNative: "某证据卡" },
  ],
  edges: [{ edgeId: "e-1", fromNodeId: "n-1", toNodeId: "n-2", hypothesis: "两者相关" }],
  primaryNodeId: "n-1",
};

const EMPTY: WorkbenchGraph = { nodes: [], edges: [], primaryNodeId: null };

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("UI-03 · 三态分得开", () => {
  it("端点未建时说「接口未提供」，NEVER 画一张空图", () => {
    const { container } = render(<GraphWorkbench graph={null} />);

    expect(container.querySelector("[data-workbench-state]")?.getAttribute(
      "data-workbench-state")).toBe("not_provided");
    expect(screen.getByText(zh["workbench.graph.not_provided"])).toBeTruthy();
    expect(screen.queryByText(zh["workbench.graph.empty"])).toBeNull();
  });

  it("查过了、确实是空的 → 引导拖入第一个热点", () => {
    const { container } = render(<GraphWorkbench graph={EMPTY} />);

    expect(container.querySelector("[data-workbench-state]")?.getAttribute(
      "data-workbench-state")).toBe("empty");
    expect(screen.getByText(zh["workbench.graph.empty"])).toBeTruthy();
  });

  it("空图 NEVER 预置示例节点", () => {
    const { container } = render(<GraphWorkbench graph={EMPTY} />);

    expect(container.querySelectorAll(".workbench__node")).toHaveLength(0);
  });

  it("两种「没有节点」用不同的 state 标记（否则界面上分不出来）", () => {
    const notProvided = render(<GraphWorkbench graph={null} />);
    const empty = render(<GraphWorkbench graph={EMPTY} />);

    const read = (r: ReturnType<typeof render>) =>
      r.container.querySelector("[data-workbench-state]")?.getAttribute(
        "data-workbench-state");
    expect(read(notProvided)).not.toBe(read(empty));
  });
});

describe("UI-03 · 画布只装配，不重写交互", () => {
  it("有节点时逐个渲染，顺序照后端给的来（零计算）", () => {
    const { container } = render(<GraphWorkbench graph={READY} />);
    const nodes = [...container.querySelectorAll(".workbench__node")];

    expect(nodes).toHaveLength(2);
    expect(nodes[0]?.textContent).toContain("某热点");
    expect(nodes[1]?.textContent).toContain("某证据卡");
  });

  it("primary 由后端给，前端 NEVER 自己挑一个", () => {
    const noPrimary: WorkbenchGraph = { ...READY, primaryNodeId: null };
    const { container } = render(<GraphWorkbench graph={noPrimary} />);

    expect(container.querySelector("[data-workbench-actions]")).toBeTruthy();
  });

  it("生成闸门拿到的是后端那份边，不是前端拼的", () => {
    const onGenerate = vi.fn();
    render(<GraphWorkbench graph={READY} onGenerate={onGenerate} />);

    expect(screen.getByText(/两者相关|生成|generate/i)).toBeTruthy();
  });
});

describe("UI-03 · 移动端只读（E10）", () => {
  it("只读时增删改控件**不渲染**，不是置灰", () => {
    const { container } = render(<GraphWorkbench graph={READY} readOnly />);

    expect(container.querySelector("[data-workbench-actions]")).toBeNull();
    expect(container.querySelectorAll("button")).toHaveLength(0);
  });

  it("只读仍然看得见节点（可看可缩放）", () => {
    const { container } = render(<GraphWorkbench graph={READY} readOnly />);

    expect(container.querySelectorAll(".workbench__node")).toHaveLength(2);
  });

  it("只读与可写渲染的是同一批节点（只是少了控件）", () => {
    const writable = render(<GraphWorkbench graph={READY} />);
    const readonly = render(<GraphWorkbench graph={READY} readOnly />);

    expect(readonly.container.querySelectorAll(".workbench__node")).toHaveLength(
      writable.container.querySelectorAll(".workbench__node").length);
  });
});

describe("UI-03 · 屏本体", () => {
  it("渲染出屏头与画布区，且**去取那张图**（PERSIST-02-b 之后）", async () => {
    // 这条判据原来断言的是「**一个请求都不发**」，理由是
    // 「端点未建就去问，问到的必然是 404，而那条红说的不是真问题」。
    //
    // 那个理由**在当时是对的**：仓里与工作台有关的后端只有
    // `POST /workbenches/{id}/edges`，没有任何一条能把一张图读出来。
    // `PERSIST-02` 建了 `GET /workbenches/{id}`，前提没了，
    // 断言跟着翻面——**NEVER 保留一条量的是「这一屏不要数据」的判据**，
    // 那正是这一屏此前空着的原因。
    const fetchMock: ReturnType<typeof vi.fn> = vi.fn(() => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({
        graph_id: "wb-1", seed_cluster_id: "c-1", created_at: "2026-08-09T12:00:00Z",
        project_id: null, nodes: [], edges: [],
      }),
    } as unknown as Response));
    vi.stubGlobal("fetch", fetchMock);

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <WorkbenchPage params={Promise.resolve({ id: "wb-1" })} />
        </Suspense>,
      );
    });

    expect(screen.getByText(zh["workbench.title"])).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    // 打的是那张图自己的路径，NEVER 是别人的。
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/workbenches/wb-1");
  });

  it("取到一张空图时画的是**空图引导**，不是「接口未提供」", async () => {
    // 三态的分界线（`workbenchClient` 文件头那张表）：
    // 取到了、图是空的 → 空图引导；取不到 → 接口未提供。
    // 合并的话，用户分不出「我的工作台是空的」与「我们没查过」。
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({
        graph_id: "wb-1", seed_cluster_id: "c-1", created_at: "2026-08-09T12:00:00Z",
        project_id: null, nodes: [], edges: [],
      }),
    } as unknown as Response)));

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <WorkbenchPage params={Promise.resolve({ id: "wb-1" })} />
        </Suspense>,
      );
    });

    expect(screen.getByText(zh["workbench.graph.empty"])).toBeTruthy();
    expect(screen.queryByText(zh["workbench.graph.not_provided"])).toBeNull();
  });

  it("取不到时屏上是「接口未提供」而不是空图引导", async () => {
    // PERSIST-02-b 之前这条判据不用 stub：那时这一屏一个请求都不发，
    // `graph` 恒为 `null`。现在它会去取，所以**取不到这件事要真的发生一次**——
    // 不 stub 的话量到的是 jsdom 里 fetch 恰好是什么，那不由本判据决定。
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("网络不通"))));

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <WorkbenchPage params={Promise.resolve({ id: "wb-1" })} />
        </Suspense>,
      );
    });

    expect(screen.getByText(zh["workbench.graph.not_provided"])).toBeTruthy();
    expect(screen.queryByText(zh["workbench.graph.empty"])).toBeNull();
  });

  it("副标不写端点路径，也不写内部 id 以外的东西（FB-10 A 类）", async () => {
    await act(async () => {
      render(
        <Suspense fallback={null}>
          <WorkbenchPage params={Promise.resolve({ id: "wb-1" })} />
        </Suspense>,
      );
    });

    const meta = document.querySelector(".screen__meta")?.textContent ?? "";
    expect(meta).not.toContain("/workbenches");
    expect(meta).not.toContain("GET");
  });
});

describe("UI-03 · 文案全部走 i18n key", () => {
  // 「组件源码里没有裸中文」那一条判据放在 pytest 那边
  // （`tests/v041/test_ui03.py#test_every_string_shown_to_the_user_goes_through_i18n`）：
  // 在这里做要靠 `?raw` 导入，而 `?raw` 过不了 `tsc --noEmit`。
  // 同一件事判两遍不会更硬，只会多一处会漂的地方。

  it("本屏用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of [
      "workbench.title", "workbench.meta", "workbench.graph.canvas",
      "workbench.graph.not_provided", "workbench.graph.not_provided_hint",
      "workbench.graph.empty",
    ]) {
      expect(zh[key as keyof typeof zh]).toBeTruthy();
      expect(en[key]).toBeTruthy();
    }
  });
});
