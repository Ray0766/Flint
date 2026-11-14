// 交付物读端点 · flint/api/deliverables.py（M3-058，demo_server 已挂载）
//   GET /deliverables/{id}         → 元信息（type/version/ledger_version/reproducible）
//   GET /deliverables/{id}/blocks  → 结构化 Block 树（L0 只读渲染器的读契约）
//   GET /deliverables/{id}/render?fmt=markdown|html|pdf|docx|pack
//
// 导出门禁（后端 guarded_render，M3-037）：存在未处理 blocking 复核 → 409 EXPORT_BLOCKED，
// detail.blocking_block_ids 携违规块清单。pdf 引擎缺失 / pack builder 未接线 → 503
// SERVICE_UNAVAILABLE。两者都由**后端**判定，前端 NEVER 自己预判"能不能导"。

import type { BlocksResponse, DeliverableMeta } from "@/lib/types";
import { requestJsonOrNull, requestOk, type RequestOpts } from "./base";

export type RenderFmt = "markdown" | "html" | "pdf" | "docx" | "pack";

/** 未生成 → null（诚实空态，不是错误）。 */
export function fetchDeliverableMeta(
  deliverableId: string,
  opts: RequestOpts = {},
): Promise<DeliverableMeta | null> {
  return requestJsonOrNull<DeliverableMeta>(
    `/deliverables/${encodeURIComponent(deliverableId)}`,
    opts,
  );
}

/** 未生成 → null。NEVER 用 /deliverables/{id}（那只回元信息，不是 Block 树）。 */
export function fetchBlocks(
  deliverableId: string,
  opts: RequestOpts = {},
): Promise<BlocksResponse | null> {
  return requestJsonOrNull<BlocksResponse>(
    `/deliverables/${encodeURIComponent(deliverableId)}/blocks`,
    opts,
  );
}

export function renderUrl(deliverableId: string, fmt: RenderFmt): string {
  return `/deliverables/${encodeURIComponent(deliverableId)}/render?fmt=${fmt}`;
}

/**
 * 真导出：命中门禁则由 requestOk 抛 FlintApiError（409 / 503 / 404），
 * 上层据 code 分支显诚实态。成功则回 Response 供调用方落盘。
 */
export function renderDeliverable(
  deliverableId: string,
  fmt: RenderFmt,
  opts: RequestOpts = {},
): Promise<Response> {
  return requestOk(renderUrl(deliverableId, fmt), opts);
}
