import type { JSX } from "react";

import { NotProvided } from "../shell/NotProvided";
import { HotspotCard } from "../hotspot-card/HotspotCard";
import { t } from "../../lib/i18n/t";

/**
 * UI-05 / v2 屏 2.15：收藏图书馆。
 *
 * ## stale 只由后端说了算
 *
 * v2 2.15 原话：「stale 判定来自后端 `Revalidator` 统一口径，
 * **前端 NEVER 自行按时间戳推断**」。冻结件 `Favorite.snapshot_stale` 的注释同源。
 *
 * 按时间戳推断看起来总是对的：三个月前的收藏「显然」旧了。可事实一个字没变时，
 * 那个标记只让用户白重跑一次；而昨天的收藏也可能因一次事实移除而彻底失效。
 * 所以本组件里**一处日期运算都没有**（判据钉着）。
 *
 * 而且 `snapshot_stale` 有三种值：`true` / `false` / **没判过**。
 * 没判过时 NEVER 显示「最新」——那是一句我们没有资格说的话。
 *
 * ## 列表 NEVER 出现空壳
 *
 * v2 2.15 原话：被收藏对象的 snapshot 受冻结保护（E2-P1），
 * 列表 NEVER 出现「已收藏但内容已被清理」的空壳。
 *
 * 后端那侧靠**内嵌**保证（`flint/fav/store.py`：收藏时把内容抄一份带走）。
 * 前端这侧的责任是：万一真拿到一条没有内容的，**把它标出来**，
 * 而不是渲染成一张什么都没有的卡片——空卡片看起来像「这条收藏没内容」，
 * 而真相是内容丢了。
 */

/**
 * 收藏那一刻存下的**卡面**（`FAV-CARD-01`）。
 *
 * 与广场那张卡是同一组槽——收藏屏因此能用**同一个** `HotspotCard`。
 * `null` = 这份快照里没有卡面（旧快照），屏上走诚实态。
 */
export type FavoriteFace = {
  nameNative: string;
  firstSeen: string | null;
  region: string | null;
  heat: number | null;
};

export type FavoriteItem = {
  favoriteId: string;
  targetKind: "cluster" | "topic" | "deliverable" | "card";
  targetId: string;
  /** 收藏时点的证据快照。空 = 内容不在了（后端本不该给出这种，给了就标出来）。 */
  hasSnapshot: boolean;
  /** 后端 Revalidator 的判定；`null` = **没判过**（NEVER 显示成「最新」）。 */
  stale: boolean | null;
  /** 收藏那一刻的卡面。`null` = 这份快照里没有它——屏上走诚实态。 */
  face?: FavoriteFace | null;
};

/** `FAV-WRITES`：三条写操作各自的结果。
 *
 * **三条各说各的，NEVER 合成一句「操作失败」**——失败之后用户该做的事不同：
 * 取消失败 = 那条还在；更新失败 = 收藏还在但快照没换；
 * 看陈旧失败 = **不知道它旧没旧**（NEVER 显示成「最新」）。 */
export type FavAction = "remove" | "refresh" | "staleness";

export type FavActionState = {
  favoriteId: string;
  action: FavAction;
  /** 进行中 / 成功 / 各自的失败措辞。 */
  phase: "working" | "done" | "error";
  message?: string;
};

export type FavoritesLibraryProps = {
  /** `null` = 没查过（端点未接通）。`[]` = 查过了、确实一条都没有。 */
  favorites: FavoriteItem[] | null;
  /** 三条写操作。**不传就不渲染那三个入口**——
   *  渲染一个按不动的按钮，与「这个能力没有」在屏上长得一样，
   *  而用户会以为自己没点到（`LOCALE-SAVE` 治的正是那种形状）。 */
  onRemove?: (favoriteId: string) => void;
  onRefresh?: (favoriteId: string) => void;
  onCheckStaleness?: (favoriteId: string) => void;
  /** 最近一次操作的结果，按 `favoriteId` 显示在那一条上。 */
  actionState?: FavActionState | null;
};

/** 这一条正在跑某个写操作吗——跑着的时候三个入口都禁用。 */
function busy(state: FavActionState | null | undefined, favoriteId: string): boolean {
  return state?.favoriteId === favoriteId && state.phase === "working";
}

function staleLabel(stale: boolean | null): string {
  if (stale === null) return t("favorites.stale.not_checked");
  return stale ? t("favorites.stale.yes") : t("favorites.stale.no");
}

export function FavoritesLibrary({
  favorites,
  onRemove,
  onRefresh,
  onCheckStaleness,
  actionState = null,
}: FavoritesLibraryProps): JSX.Element {
  if (favorites === null) {
    return (
      <section className="favorites" data-favorites-state="not_provided">
        <NotProvided label={t("favorites.not_provided")} />
      </section>
    );
  }

  if (favorites.length === 0) {
    // 查过了、确实一条都没有 → 引导去广场（v2 2.15 原话）。
    return (
      <section className="favorites" data-favorites-state="empty">
        <p className="favorites__empty">{t("favorites.empty")}</p>
        <a className="favorites__to-plaza" href="/plaza">{t("favorites.to_plaza")}</a>
      </section>
    );
  }

  return (
    <section className="favorites" data-favorites-state="ready">
      <ul className="favorites__list">
        {favorites.map((item) => (
          <li key={item.favoriteId} className="favorites__item" data-favorite-kind={
            item.targetKind
          }>
            {/* `FAV-CARD-01`：与广场**同一个** `HotspotCard`。
                NEVER 另写一个卡片组件——两个卡片会各自漂移，
                而它们呈现的是同一种东西。

                `stale` 这一槽终于有产出方了：`HotspotCard` 的文件头
                早写着恢复条件「或 `favorites` 落库后在**收藏屏**上说
                『你收藏的那份快照旧了』——让那一处的产出方开始传 `stale`，
                这一槽自己就会亮；**改那一处即可，本文件不用动**」。
                本卡就是那一处，而 `HotspotCard.tsx` 一个字没改。 */}
            {/* 陈旧那一格**留在卡旁边**。
                `UI-05` 那一族判的是三件事：三种文案、三种机器可读记号
                （`data-favorite-stale`）、以及按 `targetId` 认得出是哪一条。
                我第一版把这一格换成了卡上的 `stale` 槽，八条判据当场红——
                **它们守的口径一个字没变，是我把承载它们的那一格拿走了**。

                卡上那一槽与这一格说的是同一件事而**受众不同**：
                槽是给看屏的人的（`HotspotCard` 自己的呈现），
                这一格是给判据与读屏软件的（文案 + 记号 + 目标 id）。 */}
            <span
              className="favorites__stale"
              data-favorite-stale={
                item.stale === null ? "not_checked" : String(item.stale)
              }
              data-favorite-target={item.targetId}
            >
              {staleLabel(item.stale)}
            </span>
            {/* `UI-05` 按 `.favorites__target` 认「屏上第几条是哪一条」
                （那一族判的是「顺序照后端给的来，不排序」）。
                改前它是**标题位**上那个裸簇 id；现在标题由卡渲染，
                这一格退成**只给判据与读屏用的目标标识**——
                `sr-only` 藏起来，屏上看不见它。

                **NEVER 把这个钩子删掉**：删了之后那条判据会因为
                找不到元素而红，而红的原因与「有没有排序」无关。 */}
            <span className="favorites__target sr-only">{item.targetId}</span>
            {item.face ? (
              <HotspotCard
                nameNative={item.face.nameNative}
                firstSeen={item.face.firstSeen}
                region={item.face.region}
                heat={item.face.heat}
                stale={item.stale}
              />
            ) : (
              // **没有卡面就不渲染卡**，NEVER 拿 `targetId` 顶上去当标题——
              // 那正是这一屏改前的样子，而一个 `c-20260810-002`
              // 看起来像「有内容」。
              //
              // 这一支**不自己说话**：那句「内容不在了」由下面既有的
              // `no-content` 那一支说，**一处**。
              // 第一版两处都说了同一句，`UI-05` 当场红在
              // 「Found multiple elements with the text」——
              // 屏上也真的印了两遍。
              <span
                className="favorites__no-face"
                data-favorite-no-face="true"
                data-favorite-target={item.targetId}
              />
            )}
            {onRemove || onRefresh || onCheckStaleness ? (
              <span className="favorites__actions" data-favorite-actions="true">
                {onCheckStaleness ? (
                  <button
                    type="button"
                    className="favorites__action"
                    data-favorite-action="staleness"
                    disabled={busy(actionState, item.favoriteId)}
                    onClick={() => onCheckStaleness(item.favoriteId)}
                  >
                    {t("favorites.action.staleness")}
                  </button>
                ) : null}
                {onRefresh ? (
                  <button
                    type="button"
                    className="favorites__action"
                    data-favorite-action="refresh"
                    disabled={busy(actionState, item.favoriteId)}
                    onClick={() => onRefresh(item.favoriteId)}
                  >
                    {t("favorites.action.refresh")}
                  </button>
                ) : null}
                {onRemove ? (
                  <button
                    type="button"
                    className="favorites__action favorites__action--remove"
                    data-favorite-action="remove"
                    disabled={busy(actionState, item.favoriteId)}
                    onClick={() => onRemove(item.favoriteId)}
                  >
                    {t("favorites.action.remove")}
                  </button>
                ) : null}
              </span>
            ) : null}
            {actionState && actionState.favoriteId === item.favoriteId
              && actionState.phase === "error" ? (
              // **那一条自己的措辞**，不是一句通用的「操作失败」。
              <span
                className="favorites__action-error"
                data-favorite-action-error={actionState.action}
              >
                {actionState.message}
              </span>
            ) : null}
            {item.hasSnapshot && item.face !== null ? null : (
              // 内容不在了就说内容不在了。渲染成一张空卡片，看起来像
              // 「这条收藏没内容」——而真相是内容丢了。
              <span className="favorites__no-content" data-favorite-no-content="true">
                {t("favorites.content_gone")}
              </span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
