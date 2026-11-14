import type { JSX } from "react";

import { NotProvided } from "../shell/NotProvided";
import { t } from "../../lib/i18n/t";

/**
 * UI-08 / 蓝本 R2：额度与计费屏。
 *
 * ## 「计费未启用」不是「余额 0」
 *
 * BE-06 那侧的纪律（`flint/billing/quota.py` 写死的）：
 * 未配置时**连 `limit` / `remaining` / `currency` 这些键都不给**——
 * 给一个 `limit: 0`，前端就会显示「免费额度 0 次」，而真相是还没定价。
 *
 * 前端这侧照着办：未启用时**不画额度条、不显示任何金额**，只说未启用。
 *
 * ## 金额恒是字符串，前端一处运算都没有
 *
 * 后端把钱当字符串给（`Decimal` 走 JSON 浮点会把 0.1 + 0.2 变成
 * 0.30000000000000004，而这是钱）。所以本组件**原样渲染**，
 * NEVER 转成数字、NEVER 求和——合计也是后端给的那一个。
 *
 * ## 余量是后端给的数
 *
 * 蓝本铁律「零计算」：`remaining` 与 `exhausted` 都由后端算好，
 * 前端 NEVER 拿 `limit - used` 自己减一遍。
 */

export type BillingStatus =
  | { status: "not_enabled"; reason: string }
  | { status: "enabled"; currency: string; pricingVersion: string };

export type QuotaView =
  | { status: "not_checked" }
  | { status: "not_enabled"; used: number }
  | {
      status: "enabled";
      used: number;
      limit: number;
      remaining: number;
      exhausted: boolean;
      shortfall: number;
    };

export type BillingEventView = {
  jobId: string;
  tier: string;
  at: string;
  /** 金额**恒是字符串**，原样渲染。 */
  amount: string;
  currency: string;
  pricingVersion: string;
};

export type BillingView = {
  billing: BillingStatus;
  quota: QuotaView;
  /** `null` = 没查过账；`[]` = 查过了、一条账都没有。 */
  events: BillingEventView[] | null;
  /** 后端算好的合计（字符串）与口径混用标记。 */
  reconciliation: { count: number; total: string; mixedPricing: boolean } | null;
};

export function BillingPanel({ billing }: { billing: BillingView | null }): JSX.Element {
  if (billing === null) {
    return (
      <section className="billing" data-billing-state="not_provided">
        <NotProvided label={t("billing.not_provided")} />
      </section>
    );
  }

  const enabled = billing.billing.status === "enabled";

  return (
    <section className="billing" data-billing-state={enabled ? "enabled" : "not_enabled"}>
      <p className="billing__status">
        {enabled ? t("billing.enabled") : t("billing.not_enabled")}
      </p>
      {/* 判别联合要**按判别式收窄**：写 `!enabled` 的话 TS 收不窄，
          `reason` 只存在于 not_enabled 那一支上。 */}
      {billing.billing.status === "not_enabled" ? (
        <p className="billing__reason">{billing.billing.reason}</p>
      ) : null}

      <div className="billing__quota" data-quota-state={billing.quota.status}>
        {billing.quota.status === "not_checked" ? (
          <p>{t("billing.quota.not_checked")}</p>
        ) : billing.quota.status === "not_enabled" ? (
          // 计数一直在跑（它不需要定价），但**没有上限这回事**——不显示任何额度。
          <p>{t("billing.quota.used_only", { used: String(billing.quota.used) })}</p>
        ) : (
          <p>
            {t("billing.quota.remaining", {
              used: String(billing.quota.used),
              limit: String(billing.quota.limit),
              // 余量是后端给的数，NEVER 前端相减。
              remaining: String(billing.quota.remaining),
            })}
            {billing.quota.exhausted ? (
              <span className="billing__exhausted" data-quota-exhausted="true">
                {t("billing.quota.short_by", {
                  shortfall: String(billing.quota.shortfall),
                })}
              </span>
            ) : null}
          </p>
        )}
      </div>

      <div className="billing__events" data-events-state={
        billing.events === null ? "not_checked" : "checked"
      }>
        {billing.events === null ? (
          <p>{t("billing.events.not_checked")}</p>
        ) : billing.events.length === 0 ? (
          <p>{t("billing.events.none")}</p>
        ) : (
          <ul>
            {billing.events.map((event) => (
              <li key={event.jobId} className="billing__event">
                <span className="billing__job">{event.jobId}</span>
                {/* 金额原样渲染：不转数字、不四舍五入、不求和 */}
                <span className="billing__amount">{event.amount} {event.currency}</span>
                <span className="billing__version">{event.pricingVersion}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {billing.reconciliation !== null ? (
        <p className="billing__total" data-mixed-pricing={
          String(billing.reconciliation.mixedPricing)
        }>
          {t("billing.total", { total: billing.reconciliation.total })}
          {billing.reconciliation.mixedPricing ? (
            // 两个口径的钱加在一起，那个和没有意义——后端报了，前端就得说。
            <span className="billing__mixed">{t("billing.mixed_pricing")}</span>
          ) : null}
        </p>
      ) : null}
    </section>
  );
}
