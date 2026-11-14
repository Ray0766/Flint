/**
 * UI-11 · 项目总览屏（蓝本 P14）。
 *
 * 两条最要紧的判据：
 *
 * 1. **三个列表恒存在**——空列表是空态，不是错误页、更不是 404；
 * 2. **零计算**——不排序、不合成进度、不数出一个「完成度」。
 */
import { render, screen, waitFor } from "@testing-library/react";
import { Suspense, act } from "react";
import { describe, expect, it, vi } from "vitest";

import zh from "../../messages/zh.json";
import { ProjectOverview, type ProjectOverviewView } from
  "../../components/project-overview/ProjectOverview";
import ProjectPage from "../../app/projects/[id]/page";

const overview = (over: Partial<ProjectOverviewView> = {}): ProjectOverviewView => ({
  projectId: "p-1",
  title: "某项目",
  topics: [{ id: "t-1", label: "主题一" }],
  jobs: [{ id: "j-1", label: "深度分析", state: "done" }],
  deliverables: [{ id: "d-1", label: "报告" }],
  ...over,
});

const section = (c: HTMLElement, name: string) =>
  c.querySelector(`[data-overview-section="${name}"]`);

describe("UI-11 · 三个列表恒存在", () => {
  it("三段都在，各带自己的计数", () => {
    const { container } = render(<ProjectOverview overview={overview()} />);

    for (const name of ["topics", "jobs", "deliverables"]) {
      expect(section(container, name)).toBeTruthy();
      expect(section(container, name)?.getAttribute("data-overview-count")).toBe("1");
    }
  });

  it("空列表画成空态，**不是错误页**", () => {
    const { container } = render(<ProjectOverview overview={overview({
      topics: [], jobs: [], deliverables: [],
    })} />);

    expect(screen.getByText(zh["overview.topics.empty"])).toBeTruthy();
    expect(screen.getByText(zh["overview.jobs.empty"])).toBeTruthy();
    expect(screen.getByText(zh["overview.deliverables.empty"])).toBeTruthy();
    expect(container.querySelector("[data-overview-state]")?.getAttribute(
      "data-overview-state")).toBe("ready");
  });

  it("三段的空态各说各的话（不是同一句「暂无数据」）", () => {
    render(<ProjectOverview overview={overview({
      topics: [], jobs: [], deliverables: [],
    })} />);

    const texts = new Set([
      zh["overview.topics.empty"],
      zh["overview.jobs.empty"],
      zh["overview.deliverables.empty"],
    ]);
    expect(texts.size).toBe(3);
  });

  it("一段空另两段有内容时，只有那一段是空态", () => {
    const { container } = render(<ProjectOverview overview={overview({ jobs: [] })} />);

    expect(section(container, "jobs")?.getAttribute("data-overview-count")).toBe("0");
    expect(section(container, "topics")?.getAttribute("data-overview-count")).toBe("1");
  });
});

describe("UI-11 · 零计算", () => {
  it("顺序照后端给的来，不排序", () => {
    const { container } = render(<ProjectOverview overview={overview({
      topics: [
        { id: "t-z", label: "后来的" },
        { id: "t-a", label: "先来的" },
      ],
    })} />);
    const ids = [...container.querySelectorAll(
      '[data-overview-section="topics"] .overview__row-id')].map((n) => n.textContent);

    expect(ids).toEqual(["t-z", "t-a"]);
  });

  it("屏上没有百分比、没有进度条、没有「完成度」", () => {
    const { container } = render(<ProjectOverview overview={overview()} />);

    expect(container.textContent).not.toContain("%");
    expect(container.querySelector("progress")).toBeNull();
  });

  // DS-03 改了这条的**期望文字**，没改它的语义。
  //
  // 改前：断言屏上出现 `failed` 这个字。那既是「前端不判」的证据，
  // 也顺带把「枚举原值上屏」钉成了正确行为——而 `failed` 是数据库的值，不是人话。
  // 改后：原值仍然钉在 `data-row-state` 上（**「前端不判」由它作证**，
  // 这一行一个字没动），屏上那句改判「等于登记表里的标签」，
  // 并加一条反向断言：原值 NEVER 再出现在可见文字里。
  // 期望值从 `messages/zh.json` 取，NEVER 手抄一句——手抄的话，
  // 标签改了而这条测试仍然绿。
  it("job 的状态直取后端值，前端不判（屏上给人话，原值留在 data-* 上）", () => {
    const { container } = render(<ProjectOverview overview={overview({
      jobs: [{ id: "j-9", label: "运行", state: "failed" }],
    })} />);

    expect(container.querySelector('[data-row-state="failed"]')).toBeTruthy();
    expect(screen.getByText(zh["enum.job_state.failed"])).toBeTruthy();

    const slot = container.querySelector('[data-row-state="failed"]');
    expect(slot?.textContent).not.toBe("failed");
  });

  it("没有状态的行不画状态槽（NEVER 编一个）", () => {
    const { container } = render(<ProjectOverview overview={overview({
      topics: [{ id: "t-1", label: "主题一" }],
    })} />);

    expect(section(container, "topics")?.querySelector("[data-row-state]")).toBeNull();
  });
});

describe("UI-11 · 屏本体", () => {
  it("没查过 → 「接口未提供」", () => {
    const { container } = render(<ProjectOverview overview={null} />);

    expect(container.querySelector("[data-overview-state]")?.getAttribute(
      "data-overview-state")).toBe("not_provided");
    expect(screen.getByText(zh["overview.not_provided"])).toBeTruthy();
  });

  it("发且只发**一个**请求——NEVER 退回蓝本那句话去发三个拼", async () => {
    // WIRE-03：`GET /projects/{id}` 已由 WIRE-01 挂上，本屏改为真取数。
    // 原先判的是「一个请求都不发」（未装配期间的正确行为，`DEC-032`）。
    //
    // **「只发一个」这半条比「发了」更要紧**：三次分别查回来的东西对应的是
    // 三个时刻的库，而屏上看起来像同一时刻的快照。
    const fetchMock = vi.fn((_url: RequestInfo | URL) =>
      new Promise<Response>(() => {}));
    vi.stubGlobal("fetch", fetchMock);

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <ProjectPage params={Promise.resolve({ id: "p-1" })} />
        </Suspense>,
      );
    });

    expect(screen.getByText(zh["overview.title"])).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0]![0])).toContain("/projects/p-1");
  });

  it("库里没有这个项目 → 后端的 404 带 code → not_found，NEVER 读成「接口未提供」或「出错了」", async () => {
    // 框架的路由未命中回 `{"detail":"Not Found"}`；应用自己发的 404 带 `code`。
    // 两者意思相反：前者是「这条路由不在」，后者是「挂上了，它说这东西不存在」。
    //
    // ## 期望值改过一次（`FIX-11`）
    //
    // 改前这里断言的是 `failed`——**那正是本条要防的毛病的另一半**：
    // 当时取数层没有 `not_found` 态，带 `code` 的 404 掉进 `failed`，
    // 屏上写「取数出错 · 后端回了一个错误状态」。
    // 「这一条不存在」被说成「系统出错了」，而两者要用户做的事完全不同：
    // 前者换一个 id 或回上一层，后者等一会儿再试。
    //
    // 这条判据的**意图从来没变**（别把应用的 404 读成路由未命中），
    // 变的是它当时只能钉住一个不够好的现状。
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ code: "NOT_FOUND", message: "unknown project: p-1" }),
      { status: 404, headers: { "Content-Type": "application/json" } })));

    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <Suspense fallback={null}>
          <ProjectPage params={Promise.resolve({ id: "p-1" })} />
        </Suspense>,
      ));
    });

    await waitFor(() => expect(container.querySelector(
      "[data-screen-state]")?.getAttribute("data-screen-state")).toBe("not_found"));
  });

  it("用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of Object.keys(zh).filter((k) => k.startsWith("overview."))) {
      expect(en[key]).toBeTruthy();
    }
  });
});
