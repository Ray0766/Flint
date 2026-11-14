/**
 * CHAIN-UI-01-a · 屏上补齐 ②→③：分析跑完 → 生成报告 → 作业页 → 回总览找到产物。
 *
 * ## 改前这条路在屏上是断的
 *
 * - 成文端点要一个来源。`REPORT-SRC-01`（`DEC-061`）之后它收**分析作业号**，由服务端换算；
 *   而屏上没有任何一处会带着作业号去提交——工作台那一屏的注释还写着「今天走不了」。
 * - 提交之后产物是哪一份？`OVERVIEW-01`（`DEC-063`）之后项目总览只有一份清单，
 *   带 `version` / `supersedes`；而屏上那份清单既不显示版本，也点不进去。
 *
 * ## 这里守的四段
 *
 * 1. 总览里**跑完的分析作业**旁边有「生成报告」；没跑完的、不是分析的没有；
 * 2. 点了发的是 `POST /projects/{id}/report`，体里**只有** `analysis_job_id`——
 *    NEVER 由前端换算产物 id，也 NEVER 顺手填一个模板；
 * 3. 被拒时服务端那句话原样上屏，不跳走；
 * 4. 作业页跑完后给回总览的入口（项目号从地址栏带过去，**不带就不给，NEVER 猜**），
 *    总览的交付物清单点得进去、看得出哪一份取代了哪一份。
 *
 * 「缺口块显示内容」与「受众版互链」不在这里——它们要 `DEC-064` 的新字段，归 `CHAIN-UI-01-b`。
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Suspense, act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import zh from "../../messages/zh.json";
import { ProjectOverview, type ProjectOverviewView } from
  "../../components/project-overview/ProjectOverview";
import { toProjectOverviewView } from "../../lib/screenAdapters";
import ProjectPage from "../../app/projects/[id]/page";
import JobPage from "../../app/jobs/[id]/page";

const stream = {
  status: "done" as string | null, connection: "open", access: "unknown",
  steps: [], arrivedBlockIds: [], failedReason: null, designText: "",
  lastEventId: 3, done: true,
};
vi.mock("../../lib/useJobStream", () => ({ useJobStream: () => stream }));

// 后端 `GET /projects/{id}` 的真实形状（`flint/api/project_overview.py`）：
// 作业的状态在 `state`，交付物带 `type` / `version` / `supersedes`。
const PAYLOAD = {
  project_id: "p-1",
  topics: [],
  jobs: [
    { job_id: "j-done", kind: "gate1_analysis", state: "done" },
    { job_id: "j-running", kind: "gate1_analysis", state: "retrieving" },
    { job_id: "j-report", kind: "report", state: "done" },
  ],
  deliverables: [
    { deliverable_id: "d-1", type: "report", version: 1, supersedes: null },
    { deliverable_id: "d-1-r-j9", type: "report", version: 2, supersedes: "d-1" },
  ],
};

const view = (): ProjectOverviewView => toProjectOverviewView(PAYLOAD);

let went: string[] = [];

beforeEach(() => {
  went = [];
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, search: "", assign: (u: string) => went.push(u) },
  });
  stream.status = "done";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const json = (status: number, body: unknown): Response =>
  new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json" },
  });

/** 总览取数回 `PAYLOAD`；成文提交回 `reportReply`。记下每一次请求。 */
function stubBackend(reportReply: () => Response): Array<{ url: string; init?: RequestInit }> {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    if (init?.method === "POST") return reportReply();
    return json(200, PAYLOAD);
  }));
  return calls;
}

async function openProject(): Promise<HTMLElement> {
  let container!: HTMLElement;
  await act(async () => {
    container = render(
      <Suspense fallback={null}>
        <ProjectPage params={Promise.resolve({ id: "p-1" })} />
      </Suspense>,
    ).container;
  });
  await waitFor(() =>
    expect(container.querySelector('[data-overview-state="ready"]')).toBeTruthy());
  return container;
}

describe("CHAIN-UI-01-a · 适配：后端给的那几格原样到屏", () => {
  it("作业的状态读的是 `state`——改前读的是 `status`，作业那一列恒为空", () => {
    expect(view().jobs.map((j) => j.state)).toEqual(["done", "retrieving", "done"]);
  });

  it("作业带着 kind，交付物带着版本与它取代的那一份", () => {
    expect(view().jobs.map((j) => j.kind)).toEqual(
      ["gate1_analysis", "gate1_analysis", "report"]);
    expect(view().deliverables.map((d) => [d.version, d.supersedes])).toEqual(
      [[1, null], [2, "d-1"]]);
  });
});

describe("CHAIN-UI-01-a · 「生成报告」只出现在跑完的分析旁边", () => {
  it("跑完的分析有；没跑完的分析、跑完的成文作业都没有", () => {
    const { container } = render(<ProjectOverview overview={view()} report={{
      busyJobId: null, outcome: null, onStart: () => {},
    }} />);
    const offered = [...container.querySelectorAll("[data-report-from-job]")]
      .map((n) => n.getAttribute("data-report-from-job"));

    expect(offered).toEqual(["j-done"]);
  });

  it("没给动作时一个按钮都不画（只读场合，NEVER 画一个点了没反应的键）", () => {
    const { container } = render(<ProjectOverview overview={view()} />);

    expect(container.querySelector("[data-report-from-job]")).toBeNull();
  });
});

describe("CHAIN-UI-01-a · 点了发什么、之后去哪", () => {
  it("POST /projects/{id}/report，体里只有 analysis_job_id；随后进作业页并带着项目号", async () => {
    const calls = stubBackend(() => json(200, { job_id: "job-new" }));
    const container = await openProject();

    await act(async () => {
      fireEvent.click(container.querySelector('[data-report-from-job="j-done"]')!);
    });
    await waitFor(() => expect(went.length).toBe(1));
    const post = calls.find((c) => c.init?.method === "POST")!;

    expect(post.url).toMatch(/\/projects\/p-1\/report$/);
    expect(JSON.parse(String(post.init?.body))).toEqual({ analysis_job_id: "j-done" });
    expect(went[0]).toBe("/jobs/job-new?project=p-1");
  });

  it("被拒：服务端那句话原样上屏，不跳走", async () => {
    const refusal = "analysis job j-done is retrieving; only a done analysis has claims";
    stubBackend(() => json(422, { code: "VALIDATION_FAILED", message: refusal }));
    const container = await openProject();

    await act(async () => {
      fireEvent.click(container.querySelector('[data-report-from-job="j-done"]')!);
    });
    await waitFor(() => expect(container.querySelector("[data-report-outcome]")).toBeTruthy());

    expect(container.querySelector("[data-report-outcome]")?.textContent).toBe(refusal);
    expect(container.querySelector("[data-report-outcome]")?.getAttribute(
      "data-report-outcome")).toBe("failed");
    expect(went).toEqual([]);
  });

  it("提交在飞时再点一次，不开第二个作业", async () => {
    let release!: (r: Response) => void;
    const calls: Array<RequestInit | undefined> = [];
    vi.stubGlobal("fetch", vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method !== "POST") return Promise.resolve(json(200, PAYLOAD));
      calls.push(init);
      return new Promise<Response>((resolve) => { release = resolve; });
    }));
    const container = await openProject();
    const button = container.querySelector('[data-report-from-job="j-done"]') as HTMLButtonElement;

    await act(async () => { fireEvent.click(button); });
    await act(async () => { fireEvent.click(button); });

    expect(calls.length).toBe(1);
    expect(button.disabled).toBe(true);
    await act(async () => { release(json(200, { job_id: "job-new" })); });
  });
});

describe("CHAIN-UI-01-a · 产物从总览那份清单里找到", () => {
  it("每一份点得进去；版本号与「取代哪一份」是后端给的原值", () => {
    const { container } = render(<ProjectOverview overview={view()} />);
    const rows = [...container.querySelectorAll(
      '[data-overview-section="deliverables"] [data-deliverable-link]')];

    expect(rows.map((a) => a.getAttribute("href"))).toEqual(
      ["/deliverables/d-1", "/deliverables/d-1-r-j9"]);
    expect([...container.querySelectorAll("[data-deliverable-version]")]
      .map((n) => n.getAttribute("data-deliverable-version"))).toEqual(["1", "2"]);
    expect([...container.querySelectorAll("[data-deliverable-supersedes]")]
      .map((n) => n.getAttribute("data-deliverable-supersedes"))).toEqual(["d-1"]);
  });

  it("没有取代任何一份的那一行不画那一格（NEVER 画一个空的「取代」）", () => {
    const { container } = render(<ProjectOverview overview={view()} />);
    const first = container.querySelectorAll(
      '[data-overview-section="deliverables"] .overview__row')[0];

    expect(first.querySelector("[data-deliverable-supersedes]")).toBeNull();
  });
});

describe("CHAIN-UI-01-a · 作业页跑完后回得去总览", () => {
  const openJob = async (search: string): Promise<HTMLElement> => {
    Object.defineProperty(window, "location", {
      configurable: true, value: { ...window.location, search, assign: () => {} },
    });
    let container!: HTMLElement;
    await act(async () => {
      container = render(
        <Suspense fallback={null}>
          <JobPage params={Promise.resolve({ id: "job-new" })} />
        </Suspense>,
      ).container;
    });
    return container;
  };

  it("地址栏带了项目号且作业跑完 → 给入口，指向那个项目的总览", async () => {
    const container = await openJob("?project=p-1");

    await waitFor(() => expect(container.querySelector("[data-project-link]")).toBeTruthy());
    expect(container.querySelector("[data-project-link]")?.getAttribute("href"))
      .toBe("/projects/p-1");
    expect(screen.getByText(zh["job.project_entry.open"])).toBeTruthy();
  });

  it("没带项目号 → 不给入口。作业快照不回项目号，NEVER 猜一个", async () => {
    const container = await openJob("");

    await waitFor(() => expect(container.querySelector("[data-job-status]")).toBeTruthy());
    expect(container.querySelector("[data-project-link]")).toBeNull();
  });

  it("还没跑完 → 不给入口（去了也找不到产物）", async () => {
    stream.status = "drafting";
    const container = await openJob("?project=p-1");

    await waitFor(() => expect(container.querySelector("[data-job-status]")).toBeTruthy());
    expect(container.querySelector("[data-project-link]")).toBeNull();
  });
});
