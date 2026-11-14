// 2.6 分析 Job + SSE · GET /jobs/{job_id} 与 /jobs/{job_id}/events
// ⚠ 只读事实源：逐字取自《前端功能说明》2.6 示例数据。
import type { JobView, JobEvent } from "../types";

export const jobSnapshot: JobView = {
  job_id: "job-9d2e",
  kind: "gate1_analysis",
  project_id: "proj-demo7c1",
  state: "judging",
  progress: 0.0,
  partial_output_ref: "snap-job-9d2e-docs",
  budget: 5.0,
  cost_accum: 0.0,
  error: null,
  created_at: "2026-07-04T09:00:00Z",
  updated_at: "2026-07-04T09:01:12Z",
};

/** SSE 事件序列（id = seq，断线用 Last-Event-ID 续订，seq <= lastEventId 幂等忽略） */
export const jobEvents: Array<{ id: number; data: JobEvent }> = [
  { id: 1, data: { kind: "status", state: "retrieving" } },
  { id: 2, data: { kind: "step", step_name: "retrieve", phase: "start", cost: null } },
  { id: 3, data: { kind: "step", step_name: "retrieve", phase: "end", cost: 0.0 } },
  { id: 7, data: { kind: "status", state: "done" } },
];

/** 失败样例：verdict 零猜测失败 → job failed，前端显示「无法判定」，不编档位 */
export const jobFailedEvent: { id: number; data: JobEvent } = {
  id: 4,
  data: { kind: "failed", reason: "verdict 结构化输出重试 2 次后耗尽，判 D 并说明" },
};
