// P3 combo 入口 · POST /projects/combo —— 真后端写。
//
// 服务端只负责取选卡来源（广场当日簇 → 各簇证据卡）；提交交互在 client 组件里。
import type { Metadata } from "next";
import { fetchCategories, fetchEvidenceCards, fetchPlazaHot } from "@/lib/api";
import type { Category, EvidenceCard } from "@/lib/types";
import { AppShell } from "@/components/shell/app-shell";
import { ComboComposer, type CardGroup } from "@/components/combo/combo-composer";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "combo 入口 · Flint",
  description: "POST /projects/combo — 跨簇选 2~5 张证据卡 + 一句关联假设，生成候选主题。",
};

const DEFAULT_DAY = "2026-07-04";
// 选卡来源取当日主榜前若干簇：这是**呈现范围**的取舍（一次拉 154 簇的卡过重），
// 不是排序或筛选——簇序仍是后端给的，未取的簇在屏上如实说明。
const SOURCE_CLUSTER_LIMIT = 8;

export default async function ComboNewPage({
  searchParams,
}: {
  searchParams: Promise<{ day?: string }>;
}) {
  const { day: dayParam } = await searchParams;
  const day = dayParam ?? DEFAULT_DAY;

  let groups: CardGroup[] = [];
  let totalClusters = 0;
  let loadError: unknown = null;
  try {
    const plaza = await fetchPlazaHot(day);
    totalClusters = plaza.clusters.length;
    const head = plaza.clusters.slice(0, SOURCE_CLUSTER_LIMIT);
    const loaded = await Promise.all(
      head.map(async (c) => {
        let cards: EvidenceCard[] = [];
        try {
          const res = await fetchEvidenceCards(c.cluster_id);
          cards = res.evidence_cards;
        } catch {
          cards = [];
        }
        return { id: c.cluster_id, name: c.canonical_name, cards };
      }),
    );
    groups = loaded.filter((g) => g.cards.length > 0);
  } catch (err) {
    loadError = err;
  }

  let categories: Category[] | null = null;
  let categoriesError = false;
  try {
    categories = await fetchCategories();
  } catch {
    categoriesError = true;
  }

  return (
    <AppShell
      active="/combo/new"
      endpoint={`POST /projects/combo  ·  选卡来源 GET /plaza/hot?day=${day} + /clusters/{id}/evidence-cards`}
      categories={categories}
      categoriesError={categoriesError}
    >
      <ComboComposer
        groups={groups}
        day={day}
        totalClusters={totalClusters}
        shownClusters={groups.length}
        loadError={loadError !== null}
      />
    </AppShell>
  );
}
