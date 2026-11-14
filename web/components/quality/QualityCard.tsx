import type { JSX } from "react";

import { NotProvided } from "../shell/NotProvided";
import { t } from "../../lib/i18n/t";

/**
 * UI-09 / 蓝本 R3：质量卡视图。
 *
 * ## 覆盖率给**两个数**，NEVER 给一个比例
 *
 * 技术约束清单第 1 条：「是否出现可靠度进度条、百分比、星级、雷达图，
 * 或任何把布尔/枚举画成连续量的表达？**后端不返回这类分值**。」
 *
 * BE-03 那侧的原话说得更直白：「6 个块里 1 个有证据引用」前端能列出来；
 * 「引用覆盖率 17%」前端会拿它画进度条——**而那条进度条没有出处**。
 *
 * 所以本组件把分子与分母**分别渲染**，中间那个「/」是排版，不是除法。
 * 组件里一处除法都没有（判据钉着）。
 *
 * ## 「没检查过」与「检查过、是 0」分得开
 *
 * 未解引用数要真去解一遍才知道。BE-03 在解引用器没注入时报
 * `status: "not_checked"` 且**连 `count` 这个键都不给**。
 * 前端照着办：not_checked 时显示「还没查过」，NEVER 显示 0——
 * 0 的意思是「查过了，一个都没有」。
 *
 * ## 阻断与建议两级不混
 *
 * blocking 挡导出、advisory 不挡。两者一眼可辨（技术约束清单第 21 条），
 * 且 `--rust` 只给 blocking 那一档（清单第 5 条：全站仅三处）。
 */

export type QualityView = {
  /** 分子与分母**两个数**，NEVER 一个比例。 */
  blocksWithRefs: number;
  blocksCounted: number;
  blocksExcludedUser: number;
  /** `null` = 没查过未解引用（BE-03 的 `not_checked`）。 */
  unresolved: { count: number; ids: string[] } | null;
  gapHintRefs: string[];
  blockingBlockIds: string[];
  advisoryOpen: number;
  exportable: boolean;
};

export function QualityCard({ quality }: { quality: QualityView | null }): JSX.Element {
  if (quality === null) {
    return (
      <section className="quality" data-quality-state="not_provided">
        <NotProvided label={t("quality.not_provided")} />
      </section>
    );
  }

  return (
    <section className="quality" data-quality-state="ready">
      {/* 分子与分母各是一个数。中间的「/」是排版，不是除法。 */}
      <p className="quality__coverage" data-quality-coverage="counts">
        {t("quality.coverage", {
          withRefs: String(quality.blocksWithRefs),
          counted: String(quality.blocksCounted),
        })}
      </p>
      <p className="quality__excluded">
        {t("quality.excluded", { n: String(quality.blocksExcludedUser) })}
      </p>

      <p className="quality__unresolved" data-unresolved-state={
        quality.unresolved === null ? "not_checked" : "checked"
      }>
        {quality.unresolved === null
          ? t("quality.unresolved.not_checked")
          : t("quality.unresolved.count", {
              n: String(quality.unresolved.count),
            })}
      </p>
      {quality.unresolved !== null && quality.unresolved.ids.length > 0 ? (
        <ul className="quality__unresolved-ids">
          {quality.unresolved.ids.map((id) => <li key={id}>{id}</li>)}
        </ul>
      ) : null}

      <p className="quality__gaps">
        {t("quality.gaps", { n: String(quality.gapHintRefs.length) })}
      </p>

      <div className="quality__review">
        <p className="quality__blocking" data-review-level="blocking">
          {t("quality.blocking", { n: String(quality.blockingBlockIds.length) })}
        </p>
        {quality.blockingBlockIds.length > 0 ? (
          <ul className="quality__blocking-ids">
            {quality.blockingBlockIds.map((id) => <li key={id}>{id}</li>)}
          </ul>
        ) : null}
        <p className="quality__advisory" data-review-level="advisory">
          {t("quality.advisory", { n: String(quality.advisoryOpen) })}
        </p>
      </div>

      <p className="quality__exportable" data-exportable={String(quality.exportable)}>
        {quality.exportable ? t("quality.exportable") : t("quality.blocked")}
      </p>
    </section>
  );
}
