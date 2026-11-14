"use client";

// DESIGN-02：设计台的两条取数——提交生成、取回已产出的块。
//
// ## 提交那条现在通了（`ENTRY-01`）
//
// 改前：`POST /projects/{id}/design_generate` **不存在**，而本模块**照样发请求**——
// 因为「能不能提交」的真相在服务端。前端自己判「我知道它没有」，
// 那份判断会与后端各自漂移：端点哪天挂上了，屏上仍然显示「没有」。
// **那次的写法是对的**，所以端点建好之后这里一行都不用改：
// 它本来就是「发一次、按答复说话」（`DEC-032` 的诚实态）。
//
// v0.4.1 第 6 批的 `ENTRY-01` 把端点建了出来（`flint/api/analysis.py`），
// 单据 `docs/blocked/DESIGN-GENERATE-HAS-NO-SUBMIT-ENDPOINT.md` 已 closed。
// 四种拒绝各说各的：缺头 401 · 身份查不到 401（另一个 code）· 无角色 403 ·
// 项目不存在 404——本模块把它们**原样交给屏**，NEVER 合成一句「提交失败」。
//
// ## 结果形状与卡片三动作**共用一份**
//
// `ActionOutcome` 从 `../plaza/cardActions` 取。同一个仓里对「还没接 / 这类目标不支持 /
// 失败」这三件事 NEVER 有两套形状——两套形状就是两种话术，而它们说的是同一件事。

import { API_BASE, API_USER_ID } from "../../lib/apiBase";
import type { ActionOutcome } from "../plaza/cardActions";

/** 设计台默认挂在哪个 project 下。真项目由调用方给——这里只是端点要一个位置。 */
export const DESIGN_PROJECT_FALLBACK = "design";

export type DesignReplay = {
  /** 已经产出的全部文字（快照 + 续流，由服务端拼好）。 */
  text: string;
  /** 拼到哪个 seq——续订 SSE 时的 Last-Event-ID 依据。 */
  seq: number;
};

function headers(): Record<string, string> {
  // 身份头从配置来，没配就不发（`FB-10` 的 A 类：`X-User-Id` 逐字点名）。
  const out: Record<string, string> = { "Content-Type": "application/json" };
  if (API_USER_ID) out["x-user-id"] = API_USER_ID;
  return out;
}

/**
 * 提交一次「说一句话出一个设计」。
 *
 * 空提示**不发请求**：一句话都没有的生成只会让模型自由发挥，
 * 而产出的东西没有任何人要求过（与作业消费者那边的判断同一句）。
 */
export async function submitDesign(
  prompt: string,
  opts: { baseUrl?: string; projectId?: string } = {},
): Promise<ActionOutcome> {
  const base = opts.baseUrl ?? API_BASE;
  const project = opts.projectId ?? DESIGN_PROJECT_FALLBACK;
  let res: Response;
  try {
    res = await fetch(
      `${base}/projects/${encodeURIComponent(project)}/design_generate`,
      { method: "POST", headers: headers(), body: JSON.stringify({ prompt }) },
    );
  } catch (err: unknown) {
    return { kind: "failed", status: 0, message: String(err) };
  }
  const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;

  if (payload["status"] === "not_provided") {
    return { kind: "not_provided", reason: String(payload["reason"] ?? "") };
  }
  // 框架的路由未命中回 `{"detail":"Not Found"}`——**没有 `code`**。
  // 带 `code` 的 404 是「这一条不存在」，没有 `code` 的是「这个能力还没挂」。
  if (res.status === 404 && payload["code"] === undefined) {
    return { kind: "not_provided", reason: String(payload["detail"] ?? "") };
  }
  if (!res.ok) {
    return {
      kind: "failed",
      status: res.status,
      message: String(payload["message"] ?? payload["detail"] ?? ""),
    };
  }
  return { kind: "ok", detail: payload };
}

/**
 * 取回一个设计会话已经产出的块（`GET /design/sessions/{job_id}/replay`）。
 *
 * 这是「中断可续」的那一半：进屏先问一次，**NEVER 从头重跑**。
 * 404 = 没有这个会话（还没产出过任何块）→ 回 `null`，
 * 与「有会话但文字是空的」是两件事，NEVER 拿空串冒充。
 */
export async function fetchDesignReplay(
  jobId: string,
  opts: { baseUrl?: string } = {},
): Promise<DesignReplay | null> {
  const base = opts.baseUrl ?? API_BASE;
  let res: Response;
  try {
    res = await fetch(
      `${base}/design/sessions/${encodeURIComponent(jobId)}/replay`,
      { headers: headers() },
    );
  } catch {
    return null;
  }
  if (!res.ok) return null;
  const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  return {
    text: String(payload["text"] ?? ""),
    seq: Number(payload["seq"] ?? 0),
  };
}


/**
 * 固化一份样板为模板（`POST /design/templates`，`BE-10` 已装配）。
 *
 * 规格 `#2.17` 第二条：**注册表不可用时固化与生产渲染阻断，探索期不阻断**。
 * 阻断在屏那侧（按钮置灰 + 说明原因），这里只负责把请求打出去并把答复带回来——
 * 前端**不预判**能不能固化：预判会与后端各自漂移。
 */
export async function solidifyTemplate(
  mockHtml: string,
  opts: { baseUrl?: string; templateId?: string; name?: string } = {},
): Promise<ActionOutcome> {
  const base = opts.baseUrl ?? API_BASE;
  let res: Response;
  try {
    res = await fetch(`${base}/design/templates`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        mock_html: mockHtml,
        template_id: opts.templateId ?? "",
        name: opts.name ?? "",
        source_deliverable_id: null,
      }),
    });
  } catch (err: unknown) {
    return { kind: "failed", status: 0, message: String(err) };
  }
  const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (payload["status"] === "not_provided") {
    return { kind: "not_provided", reason: String(payload["reason"] ?? "") };
  }
  if (!res.ok) {
    return {
      kind: "failed",
      status: res.status,
      message: String(payload["message"] ?? payload["detail"] ?? ""),
    };
  }
  return { kind: "ok", detail: payload };
}

/**
 * 查一次模板注册表，回四态之一。
 *
 * `{"status":"not_provided"}` 是**查过了、这套部署没有那张表**——
 * 与「还没查过」是两件事，NEVER 共用一个值（那张问题单逐条列过）。
 */
export async function probeRegistry(
  opts: { baseUrl?: string } = {},
): Promise<"not_provided" | "down" | "ok"> {
  const base = opts.baseUrl ?? API_BASE;
  let res: Response;
  try {
    res = await fetch(`${base}/design/templates`, { headers: headers() });
  } catch {
    // 连不上 = 查过了、坏了。**NEVER 回 not_checked**：我们确实查过。
    return "down";
  }
  const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (payload["status"] === "not_provided") return "not_provided";
  return res.ok ? "ok" : "down";
}
