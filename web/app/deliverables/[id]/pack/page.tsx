"use client";

import { use, type JSX } from "react";

import { PackViewer } from "../../../../components/pack-viewer/PackViewer";
import { Screen } from "../../../../components/shell/Screen";
import { t } from "../../../../lib/i18n/t";

// UI-10 / 蓝本 P12：vibe_pack 查看器。
//
// 蓝本 README 路由表把 P12 记成「内容端点未接（pack 装配仅离线）」。
// BE-02 本轮把 `GET /deliverables/{id}/pack` 建出来了（`flint/api/pack.py`），
// 但**没挂进 `flint/api/app.py`**——AUDIT-01 对账表里的「未装配」。
//
// 所以本屏一个请求都不发，如实标「接口未提供」。
// **注意它与「尚未生成」不是一回事**：后者是查过了、后端说 `not_generated`。
export default function PackPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);

  return (
    <Screen title={t("pack.title")} meta={t("pack.meta", { id })}>
      <PackViewer pack={null} />
    </Screen>
  );
}
