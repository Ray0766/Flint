// S1 通用件③：错误态（交付包 S1 契约点名的五件之一）。
//
// ## 「出错了」与「没有内容」NEVER 共用一个渲染
//
// `tools/check_design_constraints.mjs` 的 A6 规则专门盯着这一处：
// 把两个状态赋成同一个组件、或用「或」把两个判断并起来，一出现就判红。
// （**本段有意不写那两个模式的字面写法**：A6 不剥注释，
//  写出来会把这段说明本身判成一次违规——本卡实测被它绊过一次。
//  已登记在 docs/blocked/SCANNERS-DO-NOT-STRIP-COMMENTS.md。）
// 理由很直接——**空态是正常状态，错误态是故障**。
// 把故障画成空态，用户会安心地以为「这里本来就没东西」。
//
// ## 后端自己的说明**原样带出来**
//
// `detail` 是后端给的那句话（`{"code": …, "message": …}` 里的 message）。
// 改写成一句通用的「操作失败，请重试」，等于把唯一有用的线索丢掉。
//
// **它也 NEVER 由本组件编**：拿不到说明就不画那一块，
// 而不是填一句「未知错误」——那句话既不真也没用。
//
// ## 重试要有真去处
//
// `onRetry` 不给就不画按钮。画一个点了没反应的重试键，
// 比不画更糟：用户会反复点，然后以为是自己的网络问题。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export function ErrorState({
  title,
  detail,
  status,
  onRetry,
}: {
  /** 这一屏出错时该说的那句话。不给就用通用的。 */
  title?: string;
  /** **后端自己的说明，原样渲染**。拿不到就不画，NEVER 编一句「未知错误」。 */
  detail?: string;
  /** HTTP 状态码。带出来是为了让人能对着日志查。 */
  status?: number;
  /** 重试。**没有真去处就别给**——点了没反应比没有按钮更糟。 */
  onRetry?: () => void;
}): JSX.Element {
  return (
    <div
      className="state state--error"
      data-screen-state="failed"
      data-status={status === undefined ? undefined : String(status)}
      // 故障要让读屏软件立刻念出来，不能等用户自己发现。
      role="alert"
    >
      <p className="state__title">{title ?? t("state.error")}</p>
      {detail ? <pre className="state__detail">{detail}</pre> : null}
      {onRetry ? (
        <button type="button" className="state__retry" onClick={onRetry}>
          {t("state.retry")}
        </button>
      ) : null}
    </div>
  );
}
