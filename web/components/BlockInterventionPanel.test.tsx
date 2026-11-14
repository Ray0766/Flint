import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { BlockInterventionPanel } from "./BlockInterventionPanel";
import type { Block, BlockContent } from "../lib/types";
import type { JobEventPayload } from "../lib/jobClient";

// FE-004 (L2 干预 UI) 验收：S2-5 门控（保护块无可用控件）+ lock + regenerate 复用
// L1 Job/SSE + dispute 409 确认流。全程离线（mock fetch + FakeEventSource，S2-7）。

function mkBlock(p: Partial<Block> = {}): Block {
  const content: BlockContent = { kind: "paragraph", spans: [{ kind: "text", text: "正文" }] };
  return {
    block_id: "b1", deliverable_id: "d1", section_id: "s1", order: 0,
    type: content.kind, content, claim_ids: [], fact_ids: [],
    author: "system", revision: 1, locked: false, user_modified: false,
    needs_review: false, review_reason: null, review_severity: null, ...p,
  };
}

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onmessage: ((e: { data: string; lastEventId: string }) => void) | null = null;
  onerror: ((e: unknown) => void) | null = null;
  closed = false;
  constructor(public url: string) { FakeEventSource.instances.push(this); }
  emit(id: string, payload: JobEventPayload): void {
    this.onmessage?.({ data: JSON.stringify(payload), lastEventId: id });
  }
  close(): void { this.closed = true; }
}

const ES = FakeEventSource as unknown as typeof EventSource;

describe("S2-5：保护块无可用干预控件", () => {
  it("locked / author==user / user_modified 任一 → 无任何 button，标只读", () => {
    for (const p of [{ locked: true }, { author: "user" as const }, { user_modified: true }]) {
      const { container, unmount } = render(
        <BlockInterventionPanel block={mkBlock(p)} projectId="p1" ledgerVersion={3} />,
      );
      expect(container.querySelector("[data-intervention-protected]")).not.toBeNull();
      expect(container.querySelectorAll("button")).toHaveLength(0);
      unmount();
    }
  });
  it("非保护块 → lock/regenerate/dispute 三控件在场", () => {
    const { container } = render(
      <BlockInterventionPanel block={mkBlock()} projectId="p1" ledgerVersion={3} />,
    );
    for (const a of ["lock", "regenerate", "dispute"]) {
      expect(container.querySelector(`[data-action="${a}"]`)).not.toBeNull();
    }
  });
});

describe("lock", () => {
  it("点击 → POST /interventions/lock → onLocked 回调", async () => {
    const fetchImpl = vi.fn(async () => new Response(null, { status: 204 }));
    const onLocked = vi.fn();
    render(
      <BlockInterventionPanel block={mkBlock()} projectId="p1" ledgerVersion={3}
        onLocked={onLocked} clientOpts={{ fetchImpl: fetchImpl as unknown as typeof fetch }} />,
    );
    fireEvent.click(screen.getByTestId("lock"));
    await waitFor(() => expect(onLocked).toHaveBeenCalledOnce());
    expect(fetchImpl).toHaveBeenCalledOnce();
  });
});

describe("regenerate 复用 L1 Job/SSE", () => {
  it("点击 → 拿 job_id → 订阅 /jobs/{id}/events → 状态流式反映", async () => {
    FakeEventSource.instances = [];
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ job_id: "job-5" }), { status: 200 }));
    render(
      <BlockInterventionPanel block={mkBlock()} projectId="p1" ledgerVersion={3}
        clientOpts={{ fetchImpl: fetchImpl as unknown as typeof fetch }} eventSourceImpl={ES} />,
    );
    fireEvent.click(screen.getByTestId("regenerate"));
    await waitFor(() => expect(FakeEventSource.instances[0]?.url).toBe("/jobs/job-5/events"));
    const es = FakeEventSource.instances[0];
    act(() => es.emit("1", { kind: "status", state: "drafting" }));
    await waitFor(() => expect(screen.getByTestId("regenerate-status").textContent).toBe("drafting"));
    act(() => es.emit("2", { kind: "status", state: "done" }));
    await waitFor(() => expect(es.closed).toBe(true));
  });
});

describe("dispute 409 确认流", () => {
  it("首发 409 → 确认 UI → 带 confirmed_version 重提成功", async () => {
    const calls: RequestInit[] = [];
    const fetchImpl = vi.fn(async (_i: RequestInfo | URL, init?: RequestInit) => {
      calls.push(init!);
      if (calls.length === 1) {
        return new Response(JSON.stringify({ code: "LEDGER_CONFLICT", detail: { current_version: 7 } }), { status: 409 });
      }
      return new Response(JSON.stringify({ ledger_version: 8 }), { status: 200 });
    });
    render(
      <BlockInterventionPanel block={mkBlock()} projectId="p1" ledgerVersion={3}
        clientOpts={{ fetchImpl: fetchImpl as unknown as typeof fetch }} />,
    );
    fireEvent.change(screen.getByTestId("dispute-reason"), { target: { value: "站不住" } });
    fireEvent.click(screen.getByTestId("dispute"));
    // 首发 409 → 确认 UI 出现（携当前版本）
    await waitFor(() => expect(screen.getByTestId("dispute-confirm")).not.toBeNull());
    expect(screen.getByTestId("dispute-confirm").textContent).toContain("7");
    fireEvent.click(screen.getByTestId("dispute-confirm"));
    await waitFor(() => expect(screen.getByTestId("dispute-done").textContent).toContain("8"));
    // 第二次请求带 confirmed_version=7
    expect(JSON.parse(calls[1].body as string).confirmed_version).toBe(7);
  });
});
