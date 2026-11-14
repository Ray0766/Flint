"use client";

import { use, type JSX } from "react";

import { QualityCard } from "../../../../components/quality/QualityCard";
import { StalenessBanner } from "../../../../components/quality/StalenessBanner";
import { Screen } from "../../../../components/shell/Screen";
import { t } from "../../../../lib/i18n/t";

// UI-09 / 蓝本 R3（质量卡）+ R4（陈旧重核横幅位）。
//
// 蓝本 README 把 R3 记成「端点未建，明示占位」、R4 记成「端点未建，
// 挂交付物各屏顶部」。BE-03 与 BE-04 本轮把两条都建出来了
// （`GET /deliverables/{id}/quality`、`GET /deliverables/{id}/staleness`），
// 但**都没挂进 `flint/api/app.py`**——AUDIT-01 对账表里的「未装配」。
//
// 所以本屏一个请求都不发：质量卡显示「接口未提供」；
// 横幅位**不挂**——常驻位上不该有一条恒久的「未知」噪音（见组件 docstring）。
export default function QualityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);

  return (
    <Screen title={t("quality.title")} meta={t("quality.meta", { id })}>
      <StalenessBanner staleness={null} />
      <QualityCard quality={null} />
    </Screen>
  );
}
