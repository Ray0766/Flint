import type { JSX } from "react";

import { NotProvided } from "../shell/NotProvided";
import { t } from "../../lib/i18n/t";

/**
 * UI-08 / 蓝本 R1：账户屏。
 *
 * 外壳 S0 的「用户位」原先写死 `X-User-Id: self`（蓝本 README 原话）。
 * BE-05 把 `GET /account` 建出来了，这一屏是它的出口。
 *
 * ## 三态照后端逐字转出，NEVER 自己合并
 *
 * BE-05 的响应里，档案与组织各有三态：
 * `not_checked`（没查过）/ `no_record`（查过了、库里没有）/ `known`。
 *
 * 把前两种合并成「无」的话，用户看到的是「你没有档案」——
 * 而真相可能是我们没查过。**这一条在账户屏上格外要紧**：
 * 用户会据此去「补全资料」，而他的资料其实好好地在那儿。
 *
 * ## NEVER 显示任何凭据
 *
 * BE-05 那侧连 import 都够不着凭据来源。前端这侧的责任是：
 * 拿到什么就显示什么，**但 token / 密钥这类键名一个都不渲染**。
 */

export type AccountProfile =
  | { status: "not_checked" }
  | { status: "no_record" }
  | { status: "known"; displayName: string; email: string };

export type AccountScope = { kind: "user" | "org"; id: string; role: string };

export type AccountView = {
  principalId: string;
  profile: AccountProfile;
  /** `null` = 没查过成员关系；`[]` = 查过了、不属于任何组织。 */
  memberships: AccountScope[] | null;
  direct: AccountScope;
};

export function AccountPanel({ account }: { account: AccountView | null }): JSX.Element {
  if (account === null) {
    return (
      <section className="account" data-account-state="not_provided">
        <NotProvided label={t("account.not_provided")} />
      </section>
    );
  }

  return (
    <section className="account" data-account-state="ready">
      <dl className="account__identity">
        <dt>{t("account.principal")}</dt>
        <dd className="account__principal">{account.principalId}</dd>

        <dt>{t("account.profile")}</dt>
        <dd data-account-profile={account.profile.status}>
          {account.profile.status === "known"
            ? `${account.profile.displayName}（${account.profile.email}）`
            : account.profile.status === "no_record"
              ? t("account.profile.no_record")
              : t("account.profile.not_checked")}
        </dd>

        <dt>{t("account.direct_scope")}</dt>
        <dd className="account__direct">{account.direct.id}</dd>
      </dl>

      <div className="account__memberships" data-account-memberships={
        account.memberships === null ? "not_checked" : "checked"
      }>
        {account.memberships === null ? (
          // 没查过。**NEVER 显示成「你不属于任何组织」**——那是一句断言。
          <p>{t("account.memberships.not_checked")}</p>
        ) : account.memberships.length === 0 ? (
          <p>{t("account.memberships.none")}</p>
        ) : (
          <ul>
            {account.memberships.map((scope) => (
              <li key={scope.id} className="account__org">
                {scope.id} · {scope.role}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
