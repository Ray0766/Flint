// FAV-03：收藏图书馆（卡片墙 + 四维排序）。
//
// 卡片**复用 HOTSPOT-01 的 HotspotCard**，NEVER 复制——
// 同一个热点在广场与图书馆里必须长成同一个样子。
//
// 四维排序都基于**收藏时点的快照字段**（FAV-01 内嵌快照），
// 而不是去回查当前源：回查会让「我收藏时它是什么样」这个问题失去答案。

import type { JSX } from "react";

import { HotspotCard, type HotspotCardProps } from "../../components/hotspot-card/HotspotCard";

export const SORT_KEYS = ["created_at", "region", "verdict_at_save", "in_workbench"] as const;
export type SortKey = (typeof SORT_KEYS)[number];

export type LibraryItem = HotspotCardProps & {
  favoriteId: string;
  /** 收藏时刻（ISO） */
  createdAt: string;
  /** 收藏当时的判定；与卡上 verdict 分开——后者可能已被后续分析改写 */
  verdictAtSave?: string | null;
  /** 是否已入图谱工作台 */
  inWorkbench?: boolean;
};

/** 稳定排序：主键相等时按 favoriteId 兜底，避免同分项每次刷新换位置。 */
export function sortItems(items: LibraryItem[], key: SortKey): LibraryItem[] {
  const rank = (item: LibraryItem): string => {
    switch (key) {
      case "created_at":
        return item.createdAt;
      case "region":
        return item.region ?? "\uffff";          // 未归区排最后，NEVER 猜一个区
      case "verdict_at_save":
        return item.verdictAtSave ?? "\uffff";   // 收藏时未判定排最后
      case "in_workbench":
        return item.inWorkbench ? "0" : "1";     // 已入台在前
    }
  };
  return [...items].sort((a, b) => {
    const cmp = rank(a).localeCompare(rank(b));
    return cmp !== 0 ? cmp : a.favoriteId.localeCompare(b.favoriteId);
  });
}

export type LibraryProps = { items: LibraryItem[]; sortKey?: SortKey };

export function Library({ items, sortKey = "created_at" }: LibraryProps): JSX.Element {
  const ordered = sortItems(items, sortKey);
  if (ordered.length === 0) {
    // 空态是明确状态，不是加载失败
    return <div data-testid="library-empty" />;
  }
  return (
    <ul className="library" data-testid="library" data-sort={sortKey}>
      {ordered.map(({ favoriteId, createdAt, verdictAtSave, inWorkbench, ...card }) => (
        <li key={favoriteId} data-testid="library-item" data-favorite-id={favoriteId}>
          <HotspotCard {...card} />
        </li>
      ))}
    </ul>
  );
}
