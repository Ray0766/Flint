// 工作台 / 主题层读端点 · flint/api/views.py + flint/api/combo.py
//   GET  /clusters/{id}/evidence-cards → 证据卡（未知簇 → 空列表，非 404）
//   GET  /topics/{id}                  → 单主题（未知 → 404）
//   GET  /projects/{id}/topics         → 主题列表 + chosen_topic_id（未知 project → 空）
//   POST /projects/combo               → 建项目 + 生成 N 主题（回 degraded 降级位）
//
// v0 本轮无工作台/主题/combo 屏，这几支先按真端点备好，屏一建即可直接接。

import type {
  ComboCreateResponse,
  EvidenceCardsResponse,
  Topic,
  TopicDetailResponse,
  TopicsResponse,
} from "@/lib/types";
import { requestJson, requestJsonOrNull, type RequestOpts } from "./base";

export function fetchEvidenceCards(
  clusterId: string,
  opts: RequestOpts = {},
): Promise<EvidenceCardsResponse> {
  return requestJson<EvidenceCardsResponse>(
    `/clusters/${encodeURIComponent(clusterId)}/evidence-cards`,
    opts,
  );
}

export async function fetchTopic(
  topicId: string,
  opts: RequestOpts = {},
): Promise<Topic | null> {
  const res = await requestJsonOrNull<TopicDetailResponse>(
    `/topics/${encodeURIComponent(topicId)}`,
    opts,
  );
  return res?.topic ?? null;
}

export function fetchProjectTopics(
  projectId: string,
  opts: RequestOpts = {},
): Promise<TopicsResponse> {
  return requestJson<TopicsResponse>(
    `/projects/${encodeURIComponent(projectId)}/topics`,
    opts,
  );
}

/** degraded=true 由后端 orchestrate_combo 给出（部分主题降级生成），前端只据实标注。 */
export function createCombo(
  cardIds: string[],
  hypothesis: string,
  opts: RequestOpts = {},
): Promise<ComboCreateResponse> {
  return requestJson<ComboCreateResponse>("/projects/combo", {
    ...opts,
    method: "POST",
    body: { card_ids: cardIds, hypothesis },
  });
}
