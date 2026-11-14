// Gate① 判定与 Job 读端点
//   GET /jobs/{id}/verdict  · flint/api/views.py#gate_verdict（无鉴权，读快照）
//   GET /jobs/{id}          · flint/api/analysis.py#snapshot（鉴权：initiated_by / owner_scope）
//   GET /jobs/{id}/events   · flint/api/analysis.py#stream（SSE）
//
// verdict 未就绪 → 404 NOT_FOUND（判定还没跑出来，不是错误）→ 本层回 null。
// job 快照越权 → 403 PERMISSION_DENIED → 照抛，屏上如实显"无权查看"，NEVER 静默当无数据。

import type { JobView, VerdictResponse } from "@/lib/types";
import { API_BASE, requestJson, requestJsonOrNull, type RequestOpts } from "./base";

/** 判定尚未就绪（快照不存在）→ null。 */
export function fetchVerdict(
  jobId: string,
  opts: RequestOpts = {},
): Promise<VerdictResponse | null> {
  return requestJsonOrNull<VerdictResponse>(
    `/jobs/${encodeURIComponent(jobId)}/verdict`,
    opts,
  );
}

/** job 不存在 → null；越权 403 / 其余错误 → 抛。 */
export function fetchJobSnapshot(
  jobId: string,
  opts: RequestOpts = {},
): Promise<JobView | null> {
  return requestJsonOrNull<JobView>(`/jobs/${encodeURIComponent(jobId)}`, opts);
}

/** SSE 订阅地址。EventSource 不能带自定义头 → 依赖 demo 后端的 X-User-Id 注入中间件。 */
export function jobEventsUrl(jobId: string): string {
  return `${API_BASE}/jobs/${encodeURIComponent(jobId)}/events`;
}

/** 发起 Gate① 分析（POST /projects/{id}/analysis）。v0 暂无发起屏，客户端先备好。 */
export function submitAnalysis(
  projectId: string,
  body: { topic_id?: string; keywords?: string[]; locale?: string; budget_cny: number },
  opts: RequestOpts & { idempotencyKey?: string } = {},
): Promise<{ job_id: string }> {
  const { idempotencyKey, ...rest } = opts;
  return requestJson<{ job_id: string }>(
    `/projects/${encodeURIComponent(projectId)}/analysis`,
    {
      ...rest,
      method: "POST",
      body,
      headers: idempotencyKey ? { "idempotency-key": idempotencyKey } : undefined,
    },
  );
}
