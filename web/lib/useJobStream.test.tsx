import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useJobStream } from "./useJobStream";
import type { JobEventPayload } from "./jobClient";

// L1 hook：订阅 → 实时状态；模拟 SSE 事件 + 断线续订（seq 去重）。离线（fake ES）。

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  emit(id: string, payload: JobEventPayload): void {
    this.onmessage?.({ data: JSON.stringify(payload), lastEventId: id });
  }
  close(): void {
    this.closed = true;
  }
}

describe("useJobStream", () => {
  it("实时归约 SSE 事件到状态，终态收束", () => {
    FakeEventSource.instances = [];
    const { result } = renderHook(() =>
      useJobStream("job-1", {
        EventSourceImpl: FakeEventSource as unknown as typeof EventSource,
      }),
    );
    const es = FakeEventSource.instances[0];
    expect(es.url).toBe("/jobs/job-1/events");
    act(() => es.emit("1", { kind: "status", state: "drafting" }));
    act(() => es.emit("2", { kind: "partial_block", block_id: "b1" }));
    expect(result.current.status).toBe("drafting");
    expect(result.current.arrivedBlockIds).toEqual(["b1"]);
    // 断线重放 seq=2（已见）不重复挂载
    act(() => es.emit("2", { kind: "partial_block", block_id: "b1" }));
    expect(result.current.arrivedBlockIds).toEqual(["b1"]);
    act(() => es.emit("3", { kind: "status", state: "done" }));
    expect(result.current.done).toBe(true);
    expect(es.closed).toBe(true);
  });
});
