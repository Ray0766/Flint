import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/**
 * UI-09 / 蓝本 R4：陈旧与重核横幅位（**非路由**，挂交付物各屏顶部）。
 *
 * ## 陈旧不隐藏内容，只加标记（DESIGN-12）
 *
 * BE-04 那侧的形态是「陈旧的交付物与新鲜的交付物，响应形状逐字相同」。
 * 前端这侧对应的是：**这条横幅只是加在内容上面的一条**，
 * 它 NEVER 挡住、折叠、或替换下面的正文。
 * 组件不接收也不渲染正文——它够不着正文，也就藏不了。
 *
 * ## 「没判过」不显示成「最新」
 *
 * BE-04：快照没记账本版本时报 `status: "not_checked"`，
 * **连 `stale` 这个键都不给**——给一个 false 等于告诉用户「这份是最新的」。
 * 前端照办：not_checked 时说「还没判过」。
 *
 * ## 不可重核要说**为什么**
 *
 * 只给一个「不能重核」的灰按钮，用户不知道该怎么办。
 * BE-04 的 `revalidatable.reason` 原样转出。
 */

export type StalenessView =
  | { status: "not_checked"; reason: string; revalidatable: false; whyNot: string }
  | {
      status: "checked";
      stale: boolean;
      severity: string | null;
      factIds: string[];
      revalidatable: boolean;
      whyNot: string | null;
    };

export function StalenessBanner(
  { staleness }: { staleness: StalenessView | null },
): JSX.Element | null {
  // 没查过陈旧态时**不挂横幅**：挂一条「未知」的横幅只会占着位置，
  // 而它什么也没说。（与「接口未提供」不同——那是用户点开质量卡时该看到的，
  // 横幅位是常驻的，常驻位上不该有一条恒久的噪音。）
  if (staleness === null) return null;

  const stale = staleness.status === "checked" && staleness.stale;

  return (
    <aside
      className="staleness"
      data-staleness-state={staleness.status}
      data-staleness-stale={staleness.status === "checked" ? String(staleness.stale) : "unknown"}
    >
      <p className="staleness__message">
        {staleness.status === "not_checked"
          ? t("staleness.not_checked")
          : stale
            ? t("staleness.stale")
            : t("staleness.fresh")}
      </p>

      {staleness.status === "checked" && stale && staleness.factIds.length > 0 ? (
        <ul className="staleness__facts">
          {staleness.factIds.map((id) => <li key={id}>{id}</li>)}
        </ul>
      ) : null}

      {staleness.revalidatable ? (
        <button type="button" className="staleness__revalidate">
          {t("staleness.revalidate")}
        </button>
      ) : (
        // 不可重核要说为什么——只给一个灰按钮，用户不知道该怎么办。
        <p className="staleness__why-not" data-revalidatable="false">
          {staleness.whyNot ?? t("staleness.cannot_revalidate")}
        </p>
      )}
    </aside>
  );
}
