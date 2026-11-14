import type { Block, BlocksResponse, QualityReport } from "./types";

// L0 读契约客户端：GET /deliverables/{id}/blocks（FE-000）——结构化 Block 树 JSON。
// NEVER 用 /deliverables/{id}（那只回元信息）。只读、NEVER 回写（Block 树唯一真相 D3）。

export class DeliverableNotFound extends Error {}

export async function fetchBlocks(
  deliverableId: string,
  baseUrl = "",
  fetchImpl: typeof fetch = fetch,
): Promise<Block[]> {
  const res = await fetchImpl(
    `${baseUrl}/deliverables/${encodeURIComponent(deliverableId)}/blocks`,
  );
  if (res.status === 404) {
    throw new DeliverableNotFound(deliverableId);
  }
  if (!res.ok) {
    throw new Error(`fetchBlocks ${deliverableId}: HTTP ${res.status}`);
  }
  const body = (await res.json()) as BlocksResponse;
  return body.blocks;
}

/**
 * 质量卡（`WB-05` 用它去问逐章判定的出处）。
 *
 * **拿不到就回 `null`**，NEVER 抛：那一族今天没配后端（503），
 * 而「没配后端」在屏上要显示成「还没有判定」，不是一条报错。
 * 两者的分界在这里定一次，调用方不再各判一遍。
 */
export async function fetchQuality(
  deliverableId: string,
  baseUrl = "",
  fetchImpl: typeof fetch = fetch,
): Promise<QualityReport | null> {
  const res = await fetchImpl(
    `${baseUrl}/deliverables/${encodeURIComponent(deliverableId)}/quality`,
  ).catch(() => null);
  if (res === null || !res.ok) return null;
  return (await res.json()) as QualityReport;
}
