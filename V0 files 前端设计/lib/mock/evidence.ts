// 2.2 工作台 · GET /clusters/{cluster_id}/evidence-cards
// ⚠ 只读事实源：逐字取自《前端功能说明》2.2 示例 JSON。
import type { EvidenceCardsResponse } from "../types";

export const evidenceCards: EvidenceCardsResponse = {
  cluster_id: "c-20260704-000",
  evidence_cards: [
    {
      card_id: "card-20260704-c-20260704-000",
      cluster_id: "c-20260704-000",
      keyword_ids: ["kw-solid-electrolyte", "kw-anode-free"],
      flags: ["novelty", "momentum"],
      top_links: [
        "https://arxiv.org/abs/2507.01234",
        "https://github.com/acme/solid-cell",
      ],
    },
  ],
};

/** 未知簇 → 空列表（非 404） */
export const evidenceCardsEmpty: EvidenceCardsResponse = {
  cluster_id: "c-unknown",
  evidence_cards: [],
};
