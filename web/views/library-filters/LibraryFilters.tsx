// FAV-04：图书馆筛选与搜索（region / 判定 / 日期区间，三者可组合）。
//
// 过滤是**合取**：三个都设就三个都要满足。任何一个未设 = 该维不过滤，
// NEVER 用「全部」当成一个可选值混进枚举——那会让「没筛」和「筛了全部」
// 在状态里长得一样，回读时无从区分。
//
// 空结果态**有引导文案且 key 化**：一个空列表什么都不说，用户不知道是
// 没有数据、还是筛过头了。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";
import type { LibraryItem } from "../library/Library";

export type Filters = {
  /** 未设 = 不按地区过滤 */
  region?: string | null;
  /** 未设 = 不按判定过滤；按**收藏当时**的判定筛 */
  verdictAtSave?: string | null;
  /** 闭区间；任一端未设即该端不设限 */
  from?: string | null;
  to?: string | null;
};

export function applyFilters(items: LibraryItem[], filters: Filters): LibraryItem[] {
  return items.filter((item) => {
    if (filters.region && item.region !== filters.region) return false;
    if (filters.verdictAtSave && item.verdictAtSave !== filters.verdictAtSave) return false;
    if (filters.from && item.createdAt < filters.from) return false;
    if (filters.to && item.createdAt > filters.to) return false;
    return true;
  });
}

export type LibraryFiltersProps = { items: LibraryItem[]; filters: Filters };

export function LibraryFilters({ items, filters }: LibraryFiltersProps): JSX.Element {
  const kept = applyFilters(items, filters);
  if (kept.length === 0) {
    return (
      <div data-testid="library-filtered-empty">
        <span data-testid="library-filtered-empty-hint">{t("library.filtered.empty")}</span>
      </div>
    );
  }
  return (
    <ul data-testid="library-filtered" data-count={kept.length}>
      {kept.map((item) => (
        <li key={item.favoriteId} data-testid="filtered-item" data-favorite-id={item.favoriteId} />
      ))}
    </ul>
  );
}
