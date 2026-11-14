/**
 * UI-01：三个现有屏套上外壳与屏头之后，**功能面一行没变**。
 *
 * 风格来源见各页头注；本组判据守的是重做样式时最容易出的那种错——
 * **顺手改掉断言面**。`data-job-status` / `data-arrived-count` / `data-not-found`
 * 这些属性是既有测试与 EYE-03 取证的抓手（蓝本 README 原话「保留其零计算注释与
 * `data-*` 断言属性」）。样式卡把它们改掉，界面看起来更好了，而下游全瞎。
 *
 * 另一条：**NEVER 上进度条**。蓝本原话「无可靠度分值 → 全站无进度条/百分比/
 * 星级/雷达图」。已到达块数是个真数字，除以一个不存在的总数就成了假进度。
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import zh from "../../messages/zh.json";

const messages = zh as Record<string, string>;

const stream = {
  status: "running" as string | null,
  // UIX-04 加的第五态。桩里给它 `unknown` 是**如实**的：这几条判据测的是
  // 「能看的时候屏上有什么」，而不是拒绝态。
  // 不给的话它是 `undefined`——那一屏 NEVER 因此走拒绝分支
  // （条件是正向枚举 denied/unauthenticated），但桩里空着会让
  // 下一个读的人以为这一屏没有这个态。
  access: "unknown" as string,
  arrivedBlockIds: ["b-1", "b-2"] as string[],
  failedReason: null as string | null,
  steps: [{ step_name: "retrieve", phase: "done" }] as { step_name: string; phase: string }[],
};

vi.mock("../../lib/useJobStream", () => ({ useJobStream: () => stream }));
vi.mock("next/navigation", () => ({ usePathname: () => "/jobs/job-1" }));

// `vi.mock` 的工厂被提升到文件顶部，工厂里 NEVER 引用模块级变量——
// 上面那些 `const` 在工厂跑的时候还没初始化。异常类跟着 `vi.hoisted` 一起造。
const mocked = vi.hoisted(() => {
  class DeliverableNotFound extends Error {}
  return { blocks: { value: [] as unknown[] | null }, DeliverableNotFound };
});
vi.mock("../../lib/deliverableClient", () => ({
  fetchBlocks: async () => {
    if (mocked.blocks.value === null) throw new mocked.DeliverableNotFound();
    return mocked.blocks.value;
  },
  DeliverableNotFound: mocked.DeliverableNotFound,
}));

import DeliverablePage from "../../app/deliverables/[id]/page";
import JobPage from "../../app/jobs/[id]/page";

beforeEach(() => {
  stream.status = "running";
  stream.arrivedBlockIds = ["b-1", "b-2"];
  stream.failedReason = null;
  stream.steps = [{ step_name: "retrieve", phase: "done" }];
  mocked.blocks.value = [];
});

/** `use(params)` 会挂起：不包 Suspense 的话首帧什么都没渲染出来，
 *  断言看到的是 undefined，而那与「属性被删了」长得一模一样。 */
async function renderJob() {
  const params = Promise.resolve({ id: "job-1" });
  let r!: ReturnType<typeof render>;
  await act(async () => {
    r = render(
      <Suspense fallback={null}>
        <JobPage params={params} />
      </Suspense>,
    );
  });
  await waitFor(() => {
    expect(document.querySelector("[data-job-id]")).not.toBeNull();
  });
  return r;
}

describe("分析进度屏", () => {
  it("套了屏头，标题取自词条", async () => {
    const { container } = await renderJob();

    expect(container.querySelector(".screen__title")?.textContent).toBe(
      messages["job.screen.title"],
    );
  });

  it("既有取证属性一个不少，值也没变", async () => {
    await renderJob();

    expect(document.querySelector("[data-job-id]")?.getAttribute("data-job-id")).toBe("job-1");
    expect(document.querySelector("[data-job-status]")?.textContent).toBe("running");
    expect(document.querySelector("[data-arrived-count]")?.textContent).toBe("2");
    expect(document.querySelector("[data-job-steps]")).not.toBeNull();
  });

  it("失败时把原因说出来，且走阻塞级那一档颜色的类", async () => {
    stream.failedReason = "retrieval timed out";
    await renderJob();
    const failed = document.querySelector("[data-job-failed]");

    expect(failed?.textContent).toBe("retrieval timed out");
    expect(failed?.className).toContain("job-failed");
  });

  it("没失败时不留一个空的失败位", async () => {
    await renderJob();

    expect(document.querySelector("[data-job-failed]")).toBeNull();
  });

  it("NEVER 上进度条：没有 progress、没有百分比", async () => {
    const { container } = await renderJob();

    expect(container.querySelector("progress")).toBeNull();
    expect(container.querySelector('[role="progressbar"]')).toBeNull();
    expect(container.textContent).not.toMatch(/\d+\s*%/);
  });

  it("屏上不出现端点路径或内部 id 字段名（FB-10 的 A 类）", async () => {
    const { container } = await renderJob();

    expect(container.textContent).not.toContain("/jobs/");
    expect(container.textContent).not.toContain("block_id");
  });
});

describe("报告屏", () => {
  it("套了屏头，正文仍是 BlockTree 那一棵", async () => {
    const ui = await DeliverablePage({ params: Promise.resolve({ id: "del-1" }) });
    const { container } = render(ui);

    expect(container.querySelector(".screen__title")?.textContent).toBe(
      messages["deliverable.screen.title"],
    );
    expect(container.querySelector(".screen__body")).not.toBeNull();
  });

  it("未找到态照样有屏头，且 data-not-found 原样保留", async () => {
    mocked.blocks.value = null;
    const ui = await DeliverablePage({ params: Promise.resolve({ id: "missing" }) });
    render(ui);

    await waitFor(() => {
      expect(document.querySelector("[data-not-found]")).not.toBeNull();
    });
    expect(screen.getByText(/missing/)).toBeInTheDocument();
    expect(document.querySelector(".screen__title")).not.toBeNull();
  });
});
