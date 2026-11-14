import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EvidencePanel } from "./EvidencePanel";

// FE-004 evidence 动作（项目级 inject）：成功 → 结果；409 重放耗尽 → 冲突提示。
// 离线（mock fetch）。

describe("EvidencePanel", () => {
  it("提交 → injectEvidence → 展示 alignment/fact_added/ledger_version", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("/projects/p1/evidence");
      const b = JSON.parse(init!.body as string);
      expect(b.claim_text).toBe("我的断言");
      expect(b.user_evidence_optin).toBe(true);
      return new Response(JSON.stringify({
        alignment: "full", fact_added: true, ledger_version: 5,
        score_axis: "impact", user_evidence_verdict_optin: true, attempts: 2,
      }), { status: 200 });
    });
    render(<EvidencePanel projectId="p1" expectedVersion={4}
      clientOpts={{ fetchImpl: fetchImpl as unknown as typeof fetch }} />);
    fireEvent.change(screen.getByTestId("ev-content-ref"), { target: { value: "http://x" } });
    fireEvent.change(screen.getByTestId("ev-claim"), { target: { value: "我的断言" } });
    fireEvent.click(screen.getByTestId("ev-optin"));
    fireEvent.click(screen.getByTestId("ev-submit"));
    await waitFor(() => expect(screen.getByTestId("ev-result").textContent).toContain("full"));
    expect(screen.getByTestId("ev-result").textContent).toContain("5");
  });

  it("409 重放耗尽 → LedgerConflict 冲突提示（当前版本）", async () => {
    const fetchImpl = vi.fn(async () => new Response(
      JSON.stringify({ code: "LEDGER_CONFLICT", detail: { current_version: 9 } }),
      { status: 409 }));
    render(<EvidencePanel projectId="p1" expectedVersion={4}
      clientOpts={{ fetchImpl: fetchImpl as unknown as typeof fetch }} />);
    fireEvent.change(screen.getByTestId("ev-claim"), { target: { value: "c" } });
    fireEvent.click(screen.getByTestId("ev-submit"));
    await waitFor(() => expect(screen.getByTestId("ev-conflict").textContent).toContain("9"));
  });
});
