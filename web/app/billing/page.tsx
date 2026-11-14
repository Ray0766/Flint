"use client";

import type { JSX } from "react";

import { BillingPanel } from "../../components/account-billing/BillingPanel";
import { ScreenFetchState } from "../../lib/ScreenFetchState";
import { toBillingView } from "../../lib/screenAdapters";
import { useScreenData } from "../../lib/useScreenData";
import { Screen } from "../../components/shell/Screen";
import { t } from "../../lib/i18n/t";

// UI-08 / 蓝本 R2：额度与计费屏。
//
// 蓝本 README 把 R2 记成「端点未建 · billing_enabled: false」。
// BE-06 本轮把 `GET /billing` 建出来了，但**没挂进 `app.py`**（AUDIT-01）。
//
// `WIRE-01` 把它挂上了，本屏改为真取数。
//
// **`billing_enabled: false` 与「没查过」始终不是一回事**——这是本屏从建起来
// 那天起就钉住的一条。现在两者都真的会出现：
//
// - 取数中 → 「正在查」；
// - 200 且 `billing.status === "not_enabled"` → 「计费未启用」**并带后端给的理由**
//   （此刻实测理由是「计费未配置（免费额度/单价/币种/口径版本任缺其一）」）；
// - 框架 404 → 「接口未提供」。
export default function BillingPage(): JSX.Element {
  const { state } = useScreenData<unknown>("/billing");

  return (
    <Screen title={t("billing.title")} meta={t("billing.meta")}>
      <ScreenFetchState state={state}>
        {(data) => <BillingPanel billing={toBillingView(data)} />}
      </ScreenFetchState>
    </Screen>
  );
}
