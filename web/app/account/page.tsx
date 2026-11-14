"use client";

import type { JSX } from "react";

import { AccountPanel } from "../../components/account-billing/AccountPanel";
import { Screen } from "../../components/shell/Screen";
import { ScreenFetchState } from "../../lib/ScreenFetchState";
import { t } from "../../lib/i18n/t";
import { toAccountView } from "../../lib/screenAdapters";
import { useScreenData } from "../../lib/useScreenData";

// UI-08 / 蓝本 R1：账户屏。
//
// ## WIRE-03 之前这一屏是什么样
//
// `BE-05` 建了 `GET /account`，但**没挂进 `flint/api/app.py`**，所以这一屏
// 一个请求都不发、如实标「接口未提供」（`DEC-032`）。
//
// ## 现在
//
// `WIRE-01` 把它挂上了，本屏改为真取数。要紧的是**四种结果各有各的显示**：
//
// - **正在查** → 「正在查……」，NEVER 借用「接口未提供」或空态；
// - **200** → 真数据。此刻后端回的是 `profile: {status:"not_checked"}`——
//   迁移里没有 users 表，`load_user` 注的是 `None`。那是一句**诚实**的话：
//   端点在，它说这项它没查过。组件里 `not_checked` / `no_record` / `known`
//   三态本来就分开（`BE-05` 的设计）；
// - **框架的 404** → 「接口未提供」；
// - **503 FAMILY_NOT_CONFIGURED** → 「这一族还没有后端」，**不是**「坏了」。
export default function AccountPage(): JSX.Element {
  const { state } = useScreenData<unknown>("/account");

  return (
    <Screen title={t("account.title")} meta={t("account.meta")}>
      <ScreenFetchState state={state}>
        {(data) => <AccountPanel account={toAccountView(data)} />}
      </ScreenFetchState>
      {/* NAV-04：额度与计费从这里进。
          卡上把它记成「账户屏或顶栏（NAV-04 决定）」——**决定是账户屏**：
          它是账户的一部分（免费额度、已用量、计费事件都挂在这个身份上），
          放进顶栏会让一个二级页面与「热点广场」平级。

          入口放在取数状态**外面**：账户端点回什么都不影响用户去看账单，
          放在里面的话，账户读失败会把账单入口一起带走——
          而那两件事之间没有任何关系。 */}
      <p className="data-row" data-billing-entry>
        <span className="data-row__label">{t("billing.title")}</span>
        <a className="data-row__value" data-billing-link href="/billing">
          {t("account.billing.open")}
        </a>
      </p>
    </Screen>
  );
}
