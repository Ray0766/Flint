"use client";

import { useState, type JSX } from "react";

import {
  checkFavoriteStaleness,
  refreshFavoriteSnapshot,
  removeFavorite,
  type FavWriteResult,
} from "../../lib/favoritesClient";
import { FavoritesLibrary, type FavAction, type FavActionState } from "../../components/favorites-library/FavoritesLibrary";
import { Screen } from "../../components/shell/Screen";
import { ScreenFetchState } from "../../lib/ScreenFetchState";
import { toFavoritesView } from "../../lib/screenAdapters";
import { useScreenData } from "../../lib/useScreenData";
import { t } from "../../lib/i18n/t";

// UI-05 / v2 屏 2.15：收藏图书馆。
//
// 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/
// Flint 批次三 · 交付物.dc.html` 的列表形态。
//
// ## 端点状态
//
// v2 2.15 写的是 `GET/POST/DELETE /favorites`【未建·接口预留】。
// BE-08 本轮把它们**写出来了**（`flint/api/favorites.py`：列/加/删/看陈旧/更新到最新），
// 但**没挂进 `flint/api/app.py`**——AUDIT-01 的对账表把这条列在「未装配」里。
//
// `WIRE-11` 把这一族挂上了，`WIRE-12` 让它在**没有存储面**时照实说
// `{"status":"not_provided"}` 而不是 `{"items":[]}`。
// 所以这一屏现在**真取数**，并把那两种答复翻成两种显示：
//
// - `not_provided` → `favorites={null}` → 屏上「接口未提供」；
// - `{"items":[…]}` → 那个数组（**`[]` 就是「查过了、一条都没有」**）。
//
// 两条路都在组件里备着（`WIRE-03` 建的），切换成本是一行。
// ## FAV-WRITES：三条写操作此前**屏上没有入口**
//
// `favorites` 表由 `PERSIST-01` 建好、库里已有真行，而
// `DELETE /favorites/{id}` · `refresh-snapshot` · `staleness` 三条
// 一处都没被调（对账器的「已装配未调用」）。
//
// **三条各说各的**：失败之后用户该做的事完全不同
// （那一条还在 / 收藏还在但快照没换 / **不知道它旧没旧**）。
// 合成一句「操作失败」的话，第三条会被读成前两条。
export default function FavoritesPage(): JSX.Element {
  const { state, refetch } = useScreenData<unknown>("/favorites");
  const [action, setAction] = useState<FavActionState | null>(null);

  async function run(
    favoriteId: string, kind: FavAction,
    call: () => Promise<FavWriteResult<unknown>>,
  ): Promise<void> {
    setAction({ favoriteId, action: kind, phase: "working" });
    const result = await call();
    if (result.state === "ok") {
      setAction({ favoriteId, action: kind, phase: "done" });
      // 重取列表：**屏上那份要跟着库走**，NEVER 前端自己把那一条抹掉——
      // 抹掉之后如果后端其实没删成，屏上与库里就分叉了
      // （`useScreenData` 文件头写着同一条：refetch 只做「再问一次后端」，
      //   NEVER 接受一个「新值」参数）。
      refetch();
      return;
    }
    setAction({
      favoriteId, action: kind, phase: "error",
      message: t(result.state === "not_found"
        ? "favorites.error.gone"
        : `favorites.error.${kind === "staleness" ? "staleness" : kind}`),
    });
  }

  return (
    <Screen title={t("favorites.title")} meta={t("favorites.meta")}>
      <ScreenFetchState state={state}>
        {(data) => (
          <FavoritesLibrary
            favorites={toFavoritesView(data)}
            actionState={action}
            onRemove={(id) => void run(id, "remove", () => removeFavorite(id))}
            onRefresh={(id) =>
              void run(id, "refresh", () => refreshFavoriteSnapshot(id))}
            onCheckStaleness={(id) =>
              void run(id, "staleness", () => checkFavoriteStaleness(id))}
          />
        )}
      </ScreenFetchState>
    </Screen>
  );
}
