import { describe, it, expect, vi } from "vitest";
import {
  availableBlockInterventions,
  lockTarget,
  regenerateSection,
  disputeTarget,
  injectEvidence,
  PermissionDenied,
  NotFound,
  LedgerConflict,
  DisputeConfirmationRequired,
} from "./interventionClient";
import type { Block, BlockContent } from "./types";

// FE-003 (L2 干预客户端) 验收：4 动作忠实后端契约 + 类型化边界（403/404/409-confirm/
// 409-replay）+ S2-5 门控。全程离线（mock fetch，NEVER 联网 S2-7）。

function mkBlock(p: Partial<Block> & { content?: BlockContent } = {}): Block {
  const content: BlockContent = p.content ?? { kind: "heading", level: 1, text: "t" };
  return {
    block_id: "b", deliverable_id: "d", section_id: "s-1", order: 0,
    type: content.kind, content, claim_ids: [], fact_ids: [],
    author: "system", revision: 1, locked: false, user_modified: false,
    needs_review: false, review_reason: null, review_severity: null, ...p,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

const OPTS = { userId: "u1", baseUrl: "" };

describe("S2-5 门控 availableBlockInterventions", () => {
  it("保护块（locked / author==user / user_modified 任一）→ 无可用改写干预 []", () => {
    for (const p of [{ locked: true }, { author: "user" as const }, { user_modified: true }]) {
      expect(availableBlockInterventions(mkBlock(p))).toEqual([]);
    }
  });
  it("非保护块 → lock/regenerate/dispute/instruct_regenerate 可用", () => {
    expect(availableBlockInterventions(mkBlock())).toEqual([
      "lock", "regenerate", "dispute", "instruct_regenerate",
    ]);
  });
});

describe("lock", () => {
  it("204 → 成功；发对 body + x-user-id", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe("/interventions/lock");
      const b = JSON.parse(init!.body as string);
      expect(b).toEqual({ target_id: "b1", scope: "block", deliverable_id: "d1", project_id: "p1" });
      expect((init!.headers as Record<string, string>)["x-user-id"]).toBe("u1");
      return new Response(null, { status: 204 });
    });
    await expect(lockTarget(
      { target_id: "b1", scope: "block", deliverable_id: "d1", project_id: "p1" },
      { ...OPTS, fetchImpl },
    )).resolves.toBeUndefined();
  });
  it("403 → PermissionDenied；404 → NotFound", async () => {
    const f403 = async () => jsonResponse({ code: "PERMISSION_DENIED" }, 403);
    await expect(lockTarget(
      { target_id: "b1", scope: "block", deliverable_id: "d1", project_id: "p1" },
      { ...OPTS, fetchImpl: f403 as unknown as typeof fetch },
    )).rejects.toBeInstanceOf(PermissionDenied);
    const f404 = async () => jsonResponse({ code: "NOT_FOUND" }, 404);
    await expect(lockTarget(
      { target_id: "b1", scope: "block", deliverable_id: "d1", project_id: "p1" },
      { ...OPTS, fetchImpl: f404 as unknown as typeof fetch },
    )).rejects.toBeInstanceOf(NotFound);
  });
});

describe("regenerate", () => {
  it("→ job_id（section 级，project_id 查询串）", async () => {
    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      expect(String(input)).toBe("/deliverables/d1/sections/s1/regenerate?project_id=p1");
      return jsonResponse({ job_id: "job-7" });
    });
    const jobId = await regenerateSection(
      { deliverable_id: "d1", section_id: "s1", project_id: "p1" },
      { ...OPTS, fetchImpl },
    );
    expect(jobId).toBe("job-7");
  });
  it("403 → PermissionDenied", async () => {
    const f = async () => jsonResponse({ code: "PERMISSION_DENIED" }, 403);
    await expect(regenerateSection(
      { deliverable_id: "d1", section_id: "s1", project_id: "p1" },
      { ...OPTS, fetchImpl: f as unknown as typeof fetch },
    )).rejects.toBeInstanceOf(PermissionDenied);
  });
});

describe("dispute（409 确认流）", () => {
  const base = {
    dispute_id: "dp1", deliverable_id: "d1", target_kind: "block" as const,
    target_id: "b1", reason_text: "r", expected_version: 3,
  };
  it("成功 → {ledger_version}", async () => {
    const f = async () => jsonResponse({ ledger_version: 4 });
    const out = await disputeTarget("p1", base, { ...OPTS, fetchImpl: f as unknown as typeof fetch });
    expect(out.ledger_version).toBe(4);
  });
  it("409 无 confirmed_version → DisputeConfirmationRequired(current_version)；带 confirmed_version 重提成功", async () => {
    const f409 = async () => jsonResponse(
      { code: "LEDGER_CONFLICT", detail: { current_version: 5 } }, 409);
    let thrown: unknown;
    try {
      await disputeTarget("p1", base, { ...OPTS, fetchImpl: f409 as unknown as typeof fetch });
    } catch (e) { thrown = e; }
    expect(thrown).toBeInstanceOf(DisputeConfirmationRequired);
    expect((thrown as DisputeConfirmationRequired).currentVersion).toBe(5);
    // 带 confirmed_version 重提
    const fOk = vi.fn(async (_i: RequestInfo | URL, init?: RequestInit) => {
      expect(JSON.parse(init!.body as string).confirmed_version).toBe(5);
      return jsonResponse({ ledger_version: 6 });
    });
    const out = await disputeTarget("p1", { ...base, confirmed_version: 5 },
      { ...OPTS, fetchImpl: fOk as unknown as typeof fetch });
    expect(out.ledger_version).toBe(6);
  });
});

describe("evidence（409 重放耗尽）", () => {
  const ev = {
    evidence_kind: "text" as const, content_ref: "c", note: "n",
    claim_text: "ct", expected_version: 3, user_evidence_optin: true,
  };
  it("成功 → EvidenceResult 全字段", async () => {
    const f = async () => jsonResponse({
      alignment: "full", fact_added: true, ledger_version: 4,
      score_axis: "x", user_evidence_verdict_optin: true, attempts: 1,
    });
    const out = await injectEvidence("p1", ev, { ...OPTS, fetchImpl: f as unknown as typeof fetch });
    expect(out.fact_added).toBe(true);
    expect(out.attempts).toBe(1);
  });
  it("409 → LedgerConflict(current_version)", async () => {
    const f = async () => jsonResponse(
      { code: "LEDGER_CONFLICT", detail: { current_version: 9 } }, 409);
    let thrown: unknown;
    try {
      await injectEvidence("p1", ev, { ...OPTS, fetchImpl: f as unknown as typeof fetch });
    } catch (e) { thrown = e; }
    expect(thrown).toBeInstanceOf(LedgerConflict);
    expect((thrown as LedgerConflict).currentVersion).toBe(9);
  });
});
