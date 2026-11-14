// 2.1 热点广场 · GET /plaza/hot?day=2026-07-04
// ⚠ 只读事实源：逐字取自《前端功能说明》2.1 示例 JSON。禁止修改、禁止增字段。
import type { PlazaHotResponse } from "../types";

export const plazaHot: PlazaHotResponse = {
  day: "2026-07-04",
  clusters: [
    {
      cluster_id: "c-20260704-000",
      canonical_name: "固态电池量产突破",
      category_id: "cat-energy",
      status: "active",
      by_source: { arxiv: 88.0, ghtrend: 41.2, gtrends: 30.5, weibo: 22.0 },
      total_heat: 159.7,
      hotness: 87.75,
      hotness_components: {
        velocity: 12.3, accel: 4.1, cross_count: 3,
        multi_boost: 1.2, novelty_factor: 0.8, decay: 1.0,
      },
    },
  ],
  weak_signals: [
    {
      cluster_id: "c-20260629-134",
      canonical_name: "solid-state battery",
      category_id: "cat-energy",
      status: "active",
      weak_score: 20.0,
      agg: 6.4,
      velocity: 20.0,
      drift: 0.03,
      burst_weight: 1.0,
    },
  ],
};

/** 空态样例：clusters 与 weak_signals 均空 → 渲染「该日无热点」，不报错 */
export const plazaHotEmpty: PlazaHotResponse = {
  day: "2026-07-05",
  clusters: [],
  weak_signals: [],
};
