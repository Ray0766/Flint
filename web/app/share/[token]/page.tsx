"use client";

import { use, type JSX } from "react";

import { ShareViewer, type ShareOutcome } from
  "../../../components/share-viewer/ShareViewer";
import { Screen } from "../../../components/shell/Screen";
import { t } from "../../../lib/i18n/t";

// UI-06 / v2 屏 2.18：外链只读查看页。
//
// 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/
// Flint 批次三 · 交付物.dc.html` 的报告阅读形态（外链看的就是交付物本身）。
//
// ## 端点状态
//
// v2 2.18 写的是 `GET /share/{token}`【未建·接口预留】。
// BE-09 本轮把它写出来了（`flint/api/share.py`：`GET /public/shares/{token}`，
// 含 404/410/401/403 四种分法），但**没挂进 `flint/api/app.py`**——
// AUDIT-01 对账表里的「未装配」。
//
// 所以这一屏此刻拿不到真数据：一个请求都不发，如实标「接口未提供」。
// **注意它与「没有这个链接」不是一回事**——后者是查过了、后端说 404。
// 端点挂上之后，这里把 `outcome` 换成按状态码译出来的那一个即可：
// 404 → unknown · 410 → gone · 401 → password_required · 200 → ready。
export default function SharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}): JSX.Element {
  const { token } = use(params);
  void token;   // 端点未接通前不拿它去问任何东西
  const outcome: ShareOutcome = { kind: "not_provided" };

  return (
    <Screen title={t("share.title")} meta={t("share.meta")}>
      <ShareViewer outcome={outcome} />
    </Screen>
  );
}
