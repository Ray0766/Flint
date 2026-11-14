// 干预层客户端 · flint/api/interventions.py（四端点）
//   POST /interventions/lock                                   204 无响应体
//   POST /deliverables/{id}/sections/{sid}/regenerate           → {job_id}
//   POST /projects/{id}/evidence                                → 对齐结果
//   POST /projects/{id}/disputes                                → 争议登记
//
// 乐观锁（清单第 26 条）：dispute / evidence 带 expected_version；
// 409 LEDGER_CONFLICT 的 detail.current_version 由 FlintApiError.detail 带出，
// **NEVER 静默重试**——由屏上提示用户确认后带 confirmed_version 重提。

import type { Alignment } from "@/lib/types";
import { requestJson, requestOk, type RequestOpts } from "./base";

export interface LockBody {
  target_id: string;
  scope: "block" | "section";
  deliverable_id: string;
  project_id: string;
}

/** 204 无响应体；成功即「该块已转保护」，屏上据此撤掉控件。 */
export function lockTarget(body: LockBody, opts: RequestOpts = {}): Promise<Response> {
  return requestOk("/interventions/lock", { ...opts, method: "POST", body });
}

export interface RegenerateBody {
  project_id: string;
  block_id?: string;
  guidance?: string;
}

export function regenerateSection(
  deliverableId: string,
  sectionId: string,
  body: RegenerateBody,
  opts: RequestOpts = {},
): Promise<{ job_id: string }> {
  return requestJson<{ job_id: string }>(
    `/deliverables/${encodeURIComponent(deliverableId)}/sections/${encodeURIComponent(sectionId)}/regenerate`,
    { ...opts, method: "POST", body },
  );
}

export interface InjectBody {
  evidence_kind: "file" | "url" | "text";
  content_ref: string;
  note?: string;
  claim_text: string;
  expected_version: number;
  user_evidence_optin?: boolean;
}

export interface InjectResult {
  alignment: Alignment;
  fact_added: boolean;
  ledger_version: number;
  score_axis: string;
  user_evidence_verdict_optin: boolean;
  attempts: number;
}

/** 结果一律直显后端回值（清单 27）：alignment / fact_added 都不在前端重算。 */
export function injectEvidence(
  projectId: string,
  body: InjectBody,
  opts: RequestOpts = {},
): Promise<InjectResult> {
  return requestJson<InjectResult>(
    `/projects/${encodeURIComponent(projectId)}/evidence`,
    { ...opts, method: "POST", body },
  );
}

export interface DisputeBody {
  dispute_id: string;
  deliverable_id: string;
  target_kind: "block" | "fact" | "citation";
  target_id: string;
  reason_text: string;
  expected_version: number;
  /** 409 后二次提交才带；首次提交 MUST 不带（否则等于绕过乐观锁）。 */
  confirmed_version?: number;
}

export function fileDispute(
  projectId: string,
  body: DisputeBody,
  opts: RequestOpts = {},
): Promise<unknown> {
  return requestJson<unknown>(
    `/projects/${encodeURIComponent(projectId)}/disputes`,
    { ...opts, method: "POST", body },
  );
}
