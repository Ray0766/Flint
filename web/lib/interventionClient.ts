import type { Block } from "./types";
import { isProtected } from "./types";

// L2 干预客户端。忠实 flint/api/interventions.py 契约（NEVER 凭猜）：
//   lock  POST /interventions/lock (204)
//   regenerate POST /deliverables/{did}/sections/{sid}/regenerate?project_id= -> {job_id}
//   dispute POST /projects/{pid}/disputes -> {ledger_version}（409 确认流）
//   evidence POST /projects/{pid}/evidence -> {alignment,...}（409 重放耗尽）
// 只读消费 + 只发请求；needs_review/stale/Revalidator 语义**只反映后端回值**，
// NEVER 前端自判/重算。

export type InterventionAction =
  | "lock" | "regenerate" | "dispute" | "instruct_regenerate";

// S2-5 硬约束：保护块（locked∨author=='user'∨user_modified）前端强制只读——
// 其上 NEVER 出现任何改写它的干预控件。
export function availableBlockInterventions(block: Block): InterventionAction[] {
  if (isProtected(block)) return [];
  return ["lock", "regenerate", "dispute", "instruct_regenerate"];
}

export class PermissionDenied extends Error {}
export class NotFound extends Error {}
export class LedgerConflict extends Error {
  constructor(public currentVersion: number | null) {
    super("ledger conflict");
  }
}
export class DisputeConfirmationRequired extends Error {
  constructor(public currentVersion: number | null) {
    super("dispute confirmation required");
  }
}

export interface ClientOpts {
  userId: string;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

function headers(userId: string): Record<string, string> {
  return { "content-type": "application/json", "x-user-id": userId };
}

async function currentVersionOf(res: Response): Promise<number | null> {
  try {
    const body = (await res.json()) as { detail?: { current_version?: number | null } };
    return body.detail?.current_version ?? null;
  } catch {
    return null;
  }
}

export interface LockInput {
  target_id: string;
  scope: "block" | "section";
  deliverable_id: string;
  project_id: string;
}

export async function lockTarget(req: LockInput, opts: ClientOpts): Promise<void> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(`${opts.baseUrl ?? ""}/interventions/lock`, {
    method: "POST", headers: headers(opts.userId), body: JSON.stringify(req),
  });
  if (res.status === 204) return;
  if (res.status === 403) throw new PermissionDenied();
  if (res.status === 404) throw new NotFound();
  throw new Error(`lock: HTTP ${res.status}`);
}

export interface RegenerateInput {
  deliverable_id: string;
  section_id: string;
  project_id: string;
}

// 回 job_id——调用方复用 L1 openJobStream 流式挂载重写结果（NEVER 另造 SSE）。
export async function regenerateSection(
  req: RegenerateInput, opts: ClientOpts,
): Promise<string> {
  const f = opts.fetchImpl ?? fetch;
  const url =
    `${opts.baseUrl ?? ""}/deliverables/${encodeURIComponent(req.deliverable_id)}` +
    `/sections/${encodeURIComponent(req.section_id)}/regenerate` +
    `?project_id=${encodeURIComponent(req.project_id)}`;
  const res = await f(url, { method: "POST", headers: headers(opts.userId) });
  if (res.status === 403) throw new PermissionDenied();
  if (!res.ok) throw new Error(`regenerate: HTTP ${res.status}`);
  const body = (await res.json()) as { job_id: string };
  return body.job_id;
}

export interface GuidedRegenerateInput {
  deliverable_id: string;
  section_id: string;
  project_id: string;
  block_id: string;
  guidance: string;
}

// 块级指令式重生成（FE-CORE-007）：带 block_id + 用户 guidance 调 regenerate 端点 →
// job_id（调用方复用 L1 openJobStream 流式挂载重生成块）。guidance 只引导方向，后端
// 通道门保证 NEVER 编造出处（账本外事实拒稿）。
export async function regenerateBlockWithGuidance(
  req: GuidedRegenerateInput, opts: ClientOpts,
): Promise<string> {
  const f = opts.fetchImpl ?? fetch;
  const url =
    `${opts.baseUrl ?? ""}/deliverables/${encodeURIComponent(req.deliverable_id)}` +
    `/sections/${encodeURIComponent(req.section_id)}/regenerate` +
    `?project_id=${encodeURIComponent(req.project_id)}`;
  const res = await f(url, {
    method: "POST", headers: headers(opts.userId),
    body: JSON.stringify({ block_id: req.block_id, guidance: req.guidance }),
  });
  if (res.status === 403) throw new PermissionDenied();
  if (!res.ok) throw new Error(`guided regenerate: HTTP ${res.status}`);
  const body = (await res.json()) as { job_id: string };
  return body.job_id;
}

export interface DisputeInput {
  dispute_id: string;
  deliverable_id: string;
  target_kind: "block" | "fact" | "citation";
  target_id: string;
  reason_text: string;
  expected_version: number;
  confirmed_version?: number;
}

export async function disputeTarget(
  projectId: string, req: DisputeInput, opts: ClientOpts,
): Promise<{ ledger_version: number }> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(
    `${opts.baseUrl ?? ""}/projects/${encodeURIComponent(projectId)}/disputes`,
    { method: "POST", headers: headers(opts.userId), body: JSON.stringify(req) },
  );
  if (res.status === 403) throw new PermissionDenied();
  if (res.status === 409) {
    // 账本前进：须对当前版本确认后带 confirmed_version 重提。
    throw new DisputeConfirmationRequired(await currentVersionOf(res));
  }
  if (!res.ok) throw new Error(`dispute: HTTP ${res.status}`);
  return (await res.json()) as { ledger_version: number };
}

export interface EvidenceInput {
  evidence_kind: "file" | "url" | "text";
  content_ref: string;
  note?: string;
  claim_text: string;
  expected_version: number;
  user_evidence_optin?: boolean;
}

export interface EvidenceResult {
  alignment: string;
  fact_added: boolean;
  ledger_version: number;
  score_axis: string;
  user_evidence_verdict_optin: boolean;
  attempts: number;
}

export async function injectEvidence(
  projectId: string, req: EvidenceInput, opts: ClientOpts,
): Promise<EvidenceResult> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(
    `${opts.baseUrl ?? ""}/projects/${encodeURIComponent(projectId)}/evidence`,
    { method: "POST", headers: headers(opts.userId), body: JSON.stringify(req) },
  );
  if (res.status === 403) throw new PermissionDenied();
  if (res.status === 409) {
    // 自动重放（≤3）耗尽——账本冲突未解。
    throw new LedgerConflict(await currentVersionOf(res));
  }
  if (!res.ok) throw new Error(`evidence: HTTP ${res.status}`);
  return (await res.json()) as EvidenceResult;
}
