"use client";

// CHAIN-04：发起分析与 combo 两条**写**端点的取数件。
//
// ## 与前面几张卡不同：这两条端点都是真的
//
// `PLAZA-02` / `PLAZA-04` / `DESIGN-02` 都卡在「端点不存在」。
// 本卡两条都在 openapi 里：`POST /projects/{id}/analysis` 与 `POST /projects/combo`。
//
// ## 前端**不写自己的那句拒绝话术**
//
// 卡面 acceptance② 要求「前端本地预检话术与服务端逐字一致」。
// 实测两条端点对空假设的答复**并不是同一句**：
//
//     POST /projects/combo  空 hypothesis → 400 {"code":"VALIDATION_FAILED",
//                                                "message":"hypothesis required (non-empty str)"}
//     规格 #2.3 与 flint/api/graph_edges.py 用的却是 422 EMPTY_HYPOTHESIS
//
// 前端要「与服务端逐字一致」，就不能自己存一句——存了就要挑一句，
// 而挑哪一句都会与另一条端点对不上。所以这里的做法是：
// **前端一句拒绝话都不写**，把服务端的 `message` 原样带回屏上。
// 提交键的禁用只做「还不能提交」的物理约束（空假设、卡数越界），**不解释为什么被拒**。
// 两码不一致这件事已立单：`docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md`。

import { API_BASE, API_USER_ID } from "../../lib/apiBase";
import type { ActionOutcome } from "../plaza/cardActions";

function headers(): Record<string, string> {
  const out: Record<string, string> = { "Content-Type": "application/json" };
  if (API_USER_ID) out["x-user-id"] = API_USER_ID;
  return out;
}

/**
 * 把答复读成四种之一。**403 与 404 分开**（`AUTH-03` 口径）：
 *
 * - `403` = 这个东西在，你没权限 → 用户该去要权限；
 * - 带 `code` 的 `404` = 这一条不存在 → 用户该换一个 id；
 * - 没有 `code` 的 `404` = 这个能力还没挂 → 我们该去挂路由。
 *
 * 三者混成一句，用户会拿一个正确的 id 反复试，或者去要一个他本来就有的权限。
 */
async function read(res: Response): Promise<ActionOutcome> {
  const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;

  if (payload["status"] === "not_provided") {
    return { kind: "not_provided", reason: String(payload["reason"] ?? "") };
  }
  if (res.status === 404 && payload["code"] === undefined) {
    return { kind: "not_provided", reason: String(payload["detail"] ?? "") };
  }
  if (!res.ok) {
    // 后端自己的说明**原样带出来**。FastAPI 的 422 把说明放在 `detail` 的数组里，
    // 那时取第一条的 `msg`——改写成一句通用的「参数不对」等于把唯一有用的线索丢掉。
    const detail = payload["detail"];
    const first = Array.isArray(detail) && detail.length > 0
      ? (detail[0] as Record<string, unknown>)
      : null;
    return {
      kind: "failed",
      status: res.status,
      message: String(
        payload["message"] ?? first?.["msg"] ?? (typeof detail === "string" ? detail : ""),
      ),
    };
  }
  return { kind: "ok", detail: payload };
}

export type AnalysisDraft = {
  keywords: string[];
  budgetCny: number;
  /** 由 chosen Topic 派生 keywords（`TS-006`）。不带就走 `keywords`。 */
  topicId?: string | null;
  locale?: string;
};

/** 发起分析（P6）。成功回 `{job_id}`——调用方据此进 Job 进度屏。 */
export async function submitAnalysis(
  projectId: string, draft: AnalysisDraft, opts: { baseUrl?: string } = {},
): Promise<ActionOutcome> {
  const base = opts.baseUrl ?? API_BASE;
  let res: Response;
  try {
    res = await fetch(`${base}/projects/${encodeURIComponent(projectId)}/analysis`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        keywords: draft.keywords,
        budget_cny: draft.budgetCny,
        locale: draft.locale ?? "zh-CN",
        topic_id: draft.topicId ?? null,
      }),
    });
  } catch (err: unknown) {
    return { kind: "failed", status: 0, message: String(err) };
  }
  return read(res);
}

/**
 * 成文（`CHAIN-UI-01-a`）。成功回 `{job_id}`——调用方据此进 Job 进度屏。
 *
 * 体里**只有** `analysis_job_id`：屏上手里有的就是分析作业号，换算成产物 id 是服务端的事
 * （`REPORT-SRC-01` / `DEC-061`）。NEVER 在前端拼一个产物 id，也不带 `template_id`——
 * 不带时服务端用它自己的默认，前端填一个就多出一处要跟着改的默认值。
 */
export async function submitReport(
  projectId: string, analysisJobId: string, opts: { baseUrl?: string } = {},
): Promise<ActionOutcome> {
  const base = opts.baseUrl ?? API_BASE;
  let res: Response;
  try {
    res = await fetch(`${base}/projects/${encodeURIComponent(projectId)}/report`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ analysis_job_id: analysisJobId }),
    });
  } catch (err: unknown) {
    return { kind: "failed", status: 0, message: String(err) };
  }
  return read(res);
}

/** combo 建项（P3）。成功回 `{project_id, topic_ids, degraded}`。 */
export async function submitCombo(
  cardIds: string[], hypothesis: string, opts: { baseUrl?: string } = {},
): Promise<ActionOutcome> {
  const base = opts.baseUrl ?? API_BASE;
  let res: Response;
  try {
    res = await fetch(`${base}/projects/combo`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ card_ids: cardIds, hypothesis }),
    });
  } catch (err: unknown) {
    return { kind: "failed", status: 0, message: String(err) };
  }
  return read(res);
}
