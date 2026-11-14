import { describe, it, expect, vi } from "vitest";
import {
  initialJobStreamState,
  applyEvent,
  TERMINAL_STATES,
  submitJob,
  fetchJobSnapshot,
  openJobStream,
  type JobEventPayload,
} from "./jobClient";

// L1 验收：发起 Job（POST）+ SSE 事件流（4 类 payload）+ 按 partial_block 增量
// 挂载 + seq 去重（Last-Event-ID 断线续订不重复挂载）+ 终态收束 + 状态快照。
// 全程离线：fetch 与 EventSource 均 mock，NEVER 联网（S2-7）。

function apply(events: [string, JobEventPayload][]) {
  return events.reduce((s, [id, p]) => applyEvent(s, id, p), initialJobStreamState);
}

describe("L1 事件归约器", () => {
  it("status / step / partial_block / failed 各自归约", () => {
    const s = apply([
      ["1", { kind: "status", state: "retrieving" }],
      ["2", { kind: "step", step_name: "retrieve", phase: "start", cost: null }],
      ["3", { kind: "partial_block", block_id: "b1" }],
      ["4", { kind: "partial_block", block_id: "b2" }],
      ["5", { kind: "status", state: "drafting" }],
    ]);
    expect(s.status).toBe("drafting");
    expect(s.steps).toHaveLength(1);
    expect(s.arrivedBlockIds).toEqual(["b1", "b2"]);
    expect(s.lastEventId).toBe(5);
    expect(s.done).toBe(false);
  });

  it("partial_block 按到达序增量挂载、block_id 去重", () => {
    const s = apply([
      ["1", { kind: "partial_block", block_id: "b1" }],
      ["2", { kind: "partial_block", block_id: "b2" }],
      ["3", { kind: "partial_block", block_id: "b1" }],
    ]);
    expect(s.arrivedBlockIds).toEqual(["b1", "b2"]);
  });

  it("seq 去重：断线续订重放已见 seq 不重复挂载", () => {
    const first = apply([
      ["1", { kind: "partial_block", block_id: "b1" }],
      ["2", { kind: "partial_block", block_id: "b2" }],
    ]);
    // 模拟断线后重放 seq=1,2（<= lastEventId）+ 新 seq=3
    const resumed = [
      ["1", { kind: "partial_block", block_id: "b1" }],
      ["2", { kind: "partial_block", block_id: "b2" }],
      ["3", { kind: "partial_block", block_id: "b3" }],
    ].reduce((s, [id, p]) => applyEvent(s, id as string, p as JobEventPayload), first);
    expect(resumed.arrivedBlockIds).toEqual(["b1", "b2", "b3"]);
    expect(resumed.lastEventId).toBe(3);
  });

  it("status 终态 → done；failed 事件记原因且 done", () => {
    const done = apply([["1", { kind: "status", state: "done" }]]);
    expect(done.done).toBe(true);
    const failed = apply([["2", { kind: "failed", reason: "boom" }]]);
    expect(failed.failedReason).toBe("boom");
    expect(failed.done).toBe(true);
  });

  // `UIR-02`：失败事件到了，**状态那一格也要是 failed**。
  //
  // 归约器收到 `failed` 就置 `done`，流随即关掉——后面那条 `status/failed` 读不到了。
  // 改前这里只记原因、不动状态：真栈上见到的屏是「状态 drafting」底下印着一句「作业失败」，
  // 两句话互相打架。失败事件自己就说明了状态，NEVER 指望后面还有一条来补。
  it("failed 事件到了，状态跟着是 failed（NEVER 停在上一个中间态）", () => {
    const failed = apply([
      ["1", { kind: "status", state: "drafting" }],
      ["2", { kind: "failed", reason: "boom" }],
    ]);
    expect(failed.status).toBe("failed");
    expect(failed.failedReason).toBe("boom");
    expect(TERMINAL_STATES.has("done")).toBe(true);
    expect(TERMINAL_STATES.has("cancelled")).toBe(true);
  });
});

describe("L1 submitJob", () => {
  it("POST /projects/{id}/analysis 带 x-user-id + body，回 job_id", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("/projects/p1/analysis");
      expect((init!.headers as Record<string, string>)["x-user-id"]).toBe("u1");
      expect(JSON.parse(init!.body as string).keywords).toEqual(["k"]);
      return new Response(JSON.stringify({ job_id: "job-9" }), { status: 200 });
    });
    const jobId = await submitJob(
      "p1", "analysis",
      { keywords: ["k"], locale: "zh-CN", budget_cny: 1 },
      { userId: "u1", fetchImpl },
    );
    expect(jobId).toBe("job-9");
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  it("report / proposal 映射到对应路径", async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      seen.push(String(input));
      return new Response(JSON.stringify({ job_id: "j" }), { status: 200 });
    });
    await submitJob("p1", "report", {}, { userId: "u1", fetchImpl });
    await submitJob("p1", "proposal", {}, { userId: "u1", fetchImpl });
    expect(seen).toEqual(["/projects/p1/report", "/projects/p1/proposal"]);
  });
});

describe("L1 fetchJobSnapshot", () => {
  it("GET /jobs/{id} 回 state", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("/jobs/job-9");
      return new Response(JSON.stringify({ state: "drafting" }), { status: 200 });
    });
    const snap = await fetchJobSnapshot("job-9", { userId: "u1", fetchImpl });
    expect(snap.state).toBe("drafting");
  });
});

// 最小 fake EventSource（浏览器原生自动管理 Last-Event-ID 与重连；此处只验
// onmessage 归约 + 终态 close）。
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  emit(id: string, payload: JobEventPayload): void {
    this.onmessage?.({ data: JSON.stringify(payload), lastEventId: id });
  }
  close(): void {
    this.closed = true;
  }
}

describe("L1 openJobStream", () => {
  it("订阅 /jobs/{id}/events，归约到 onState，终态 close", () => {
    FakeEventSource.instances = [];
    const states: number[] = [];
    const close = openJobStream(
      "job-9",
      (s) => states.push(s.arrivedBlockIds.length),
      { EventSourceImpl: FakeEventSource as unknown as typeof EventSource, baseUrl: "" },
    );
    const es = FakeEventSource.instances[0];
    expect(es.url).toBe("/jobs/job-9/events");
    es.emit("1", { kind: "partial_block", block_id: "b1" });
    es.emit("2", { kind: "partial_block", block_id: "b2" });
    es.emit("3", { kind: "status", state: "done" });
    expect(states.at(-1)).toBe(2);
    expect(es.closed).toBe(true); // 终态自动 close
    close();
  });
});
