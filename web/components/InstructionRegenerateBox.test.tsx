import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { InstructionRegenerateBox } from "./InstructionRegenerateBox";
import { t } from "../lib/i18n";
import type { Block, BlockContent } from "../lib/types";
import type { JobEventPayload } from "../lib/jobClient";

// FE-CORE-007：块级指令框 — S2-5 门控（保护块无框）+ 提交调块级 guided-regenerate +
// 复用 L1 openJobStream 流式状态 + i18n key。全离线（mock fetch + FakeEventSource，S2-7）。

function mkBlock(p: Partial<Block> = {}): Block {
  const content: BlockContent = { kind: "paragraph", spans: [{ kind: "text", text: "x" }] };
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

describe("S2-5：保护块无指令框", () => {
  it("locked / author==user / user_modified 任一 → 渲染 null（无框、无 textarea）", () => {
    for (const p of [{ locked: true }, { author: "user" as const }, { user_modified: true }]) {
      const { container, unmount } = render(
        <InstructionRegenerateBox block={mkBlock(p)} projectId="p1" />,
      );
      expect(container.querySelector("[data-instruct-box]")).toBeNull();
      expect(container.querySelector("textarea")).toBeNull();
      unmount();
    }
  });
  it("非保护块 → 指令框在场，文案走 i18n key", () => {
    render(<InstructionRegenerateBox block={mkBlock()} projectId="p1" />);
    const input = screen.getByTestId("instruct-input");
    expect(input).not.toBeNull();
    expect(input.getAttribute("placeholder")).toBe(t("instruct.placeholder"));
    expect(screen.getByTestId("instruct-submit").textContent).toBe(t("instruct.submit"));
  });
});

describe("提交 → 块级 guided-regenerate → 复用 L1 流式", () => {
  it("带 block_id + guidance 调端点 → job_id → openJobStream 状态流式", async () => {
    FakeEventSource.instances = [];
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toContain("/deliverables/d1/sections/s1/regenerate");
      const body = JSON.parse(init!.body as string);
      expect(body.block_id).toBe("b1");
      expect(body.guidance).toBe("更简洁一点");
      return new Response(JSON.stringify({ job_id: "job-3" }), { status: 200 });
    });
    render(
      <InstructionRegenerateBox block={mkBlock()} projectId="p1"
        clientOpts={{ fetchImpl: fetchImpl as unknown as typeof fetch }} eventSourceImpl={ES} />,
    );
    fireEvent.change(screen.getByTestId("instruct-input"), { target: { value: "更简洁一点" } });
    fireEvent.click(screen.getByTestId("instruct-submit"));
    await waitFor(() => expect(FakeEventSource.instances[0]?.url).toBe("/jobs/job-3/events"));
    const es = FakeEventSource.instances[0];
    act(() => es.emit("1", { kind: "status", state: "drafting" }));
    await waitFor(() =>
      expect(screen.getByTestId("instruct-status").textContent).toBe(t("instruct.streaming")));
    act(() => es.emit("2", { kind: "partial_block", block_id: "b1" }));
    act(() => es.emit("3", { kind: "status", state: "done" }));
    await waitFor(() =>
      expect(screen.getByTestId("instruct-status").textContent).toBe(t("instruct.done")));
    expect(es.closed).toBe(true);
  });
});

describe("i18n 地基", () => {
  it("t(key) 取 zh-CN 串；未知 key 回落 key 本身", () => {
    expect(t("instruct.submit")).toBe("按指令重生成");
    expect(t("nope.key")).toBe("nope.key");
  });
});
