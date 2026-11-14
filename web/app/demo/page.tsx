"use client";

import type { JSX } from "react";
import { DemoFlow } from "../../components/DemoFlow";
import { API_BASE } from "../../lib/apiBase";
import { Screen } from "../../components/shell/Screen";
import { t } from "../../lib/i18n/t";

// TS-012：可点击 demo 路由 /demo——端到端串广场→点簇→工作台→combo→主题→选主题→Gate。
// day 取查询参数（默认 2026-07-04：最佳演示日，154 热点主榜 + 弱信号轨有货）；
// 数据取数走 API_BASE（一键 demo=uvicorn :8000）。报告步路由到既有 /jobs/{id} 进度页。
export default function DemoPage(): JSX.Element {
  const day =
    typeof window !== "undefined"
      ? new URLSearchParams(window.location.search).get("day") ?? "2026-07-04"
      : "2026-07-04";
  // UI-01 重做的是样式面：套上屏头。副标写**这一屏是什么**，
  // NEVER 把 day 参数或端点名印上去（FB-10 的 A 类）。
  // DemoFlow 内部一行没动——它是端到端串屏的既有逻辑。
  return (
    <Screen title={t("demo.screen.title")} meta={t("demo.screen.meta")}>
      <DemoFlow day={day} opts={{ baseUrl: API_BASE }} />
    </Screen>
  );
}
