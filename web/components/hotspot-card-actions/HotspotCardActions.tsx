"use client";

// HOTSPOT-02：卡片三独立动作（收藏 / 入台 / 分享）+ 点击排除区。
// **PLAZA-04 把它接上了真端点，并给了它三张嘴。**
//
// ## 改前：三个**空**按钮
//
// `<button type="button" data-testid="action-favorite" onClick={onFavorite} />`
// ——没有文字、没有 `aria-label`、没有样式。读屏软件念不出来，屏上量出来是 0 像素。
// 这与 `F-09` 那个占 0 像素的争议记号是同一形状：DOM 里有、用户看不见。
//
// ## 点击排除区为什么必须在最外层
//
// 卡片本身是个跳转入口（点卡面进工作台）。动作区在卡上，
// 不挡住冒泡的话，点「收藏」会**既收藏又跳走**——用户按了一下，屏没了。
// 所以 `stopPropagation` 挂在动作区的容器上，而不是逐个按钮挂：
// 逐个挂的话，将来多一个按钮而有人忘了挂，那一个就会漏。
//
// ## 三条结果各说各的话
//
// 「还没接」「这类目标不支持」「失败」是三件不同的事（见 `../plaza/cardActions.ts` 的表）。
// 本组件**只负责把调用方给的结果说出来**，NEVER 自己判定、NEVER 把三种揉成「暂不可用」。

import type { JSX } from "react";

import type { ActionOutcome } from "../plaza/cardActions";
import { FROZEN } from "../../lib/frozen";
import { t } from "../../lib/i18n/t";

export type HotspotCardActionsProps = {
  onFavorite: () => void;
  onAddToWorkbench: () => void;
  onShare: () => void;
  /** 上一次动作的结果。`null` = 还没点过——**不是**「点了没反应」。 */
  outcome?: ActionOutcome | null;
  /** 哪一个动作产生了那个结果。三个动作各自独立，结果 NEVER 挂到别人身上。 */
  outcomeOf?: "favorite" | "workbench" | "share" | null;
  /**
   * NAV-03：一句**补充**，不是结果本身。
   *
   * 今天只有一处用它：入台成了、而服务端没说是哪一个工作台。
   * 那时结果确实是「已完成」（用户的东西存下了），**同时**我们带不了他过去——
   * 两句都要说。把它塞进 `outcome` 会让「成了」变成「没成」，那是一句假话。
   */
  note?: string | null;
};

function outcomeLine(outcome: ActionOutcome): string {
  if (outcome.kind === "not_provided") return t("card.action.not_provided");
  if (outcome.kind === "unsupported") {
    return t("card.action.unsupported", { allowed: outcome.allowed.join(" / ") });
  }
  if (outcome.kind === "failed") {
    // 后端自己的说明原样带出来；它没给说明就只报状态码，NEVER 编一句。
    return outcome.message || t("card.action.failed", { status: String(outcome.status) });
  }
  return t("card.action.done");
}

export function HotspotCardActions({
  onFavorite,
  onAddToWorkbench,
  onShare,
  outcome = null,
  outcomeOf = null,
  note = null,
}: HotspotCardActionsProps): JSX.Element | null {
  // Nothing to press and nothing to report: no empty row on the card.
  if (FROZEN.favorites && FROZEN.graphWorkbench && FROZEN.share && !outcome && !note) {
    return null;
  }
  return (
    <div
      className="hotspot-card__actions"
      data-testid="card-actions"
      // 点击排除区：动作区内的点击不冒泡到卡片
      onClick={(e) => e.stopPropagation()}
    >
      {/* NARROW-05: all three buttons lead into `DEC-066` frozen items (收藏,
          图谱工作台 via `/workbenches/{id}`, 分享). Each one reads its own switch. */}
      {FROZEN.favorites ? null : (
        <button
          type="button"
          className="hotspot-card__action"
          data-testid="action-favorite"
          onClick={onFavorite}
        >
          {t("card.action.favorite")}
        </button>
      )}
      {FROZEN.graphWorkbench ? null : (
        <button
          type="button"
          className="hotspot-card__action"
          data-testid="action-workbench"
          onClick={onAddToWorkbench}
        >
          {t("card.action.workbench")}
        </button>
      )}
      {FROZEN.share ? null : (
        <button
          type="button"
          className="hotspot-card__action"
          data-testid="action-share"
          onClick={onShare}
        >
          {t("card.action.share")}
        </button>
      )}
      {outcome ? (
        <p
          className="hotspot-card__action-outcome"
          data-testid="action-outcome"
          data-outcome-kind={outcome.kind}
          data-outcome-of={outcomeOf ?? ""}
          role="status"
        >
          {outcomeLine(outcome)}
        </p>
      ) : null}
      {note ? (
        <p
          className="hotspot-card__action-note"
          data-testid="action-note"
          role="status"
        >
          {note}
        </p>
      ) : null}
    </div>
  );
}
