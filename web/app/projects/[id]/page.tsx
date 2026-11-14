"use client";

import { use, type JSX } from "react";

import { ScreenFetchState } from "../../../lib/ScreenFetchState";
import { toProjectOverviewView } from "../../../lib/screenAdapters";
import { useScreenData } from "../../../lib/useScreenData";
import { ProjectOverview } from "../../../components/project-overview/ProjectOverview";
import { Screen } from "../../../components/shell/Screen";
import { t } from "../../../lib/i18n/t";

// UI-11 / 蓝本 P14：项目总览。
//
// 蓝本 README 把 P14 记成「无专属端点：topics + jobs + deliverables 组合」——
// **那句话已经过时**：BE-01 本轮把 `GET /projects/{id}` 建出来了，一次查齐。
// 但它**没挂进 `flint/api/app.py`**（AUDIT-01 的「未装配」）。
//
// `WIRE-01` 把 `GET /projects/{id}` 挂上了，本屏改为真取数——
// **仍然只发一个请求**。NEVER 退回蓝本那句话去发三个请求拼：
// 三次分别查回来的东西对应的是三个时刻的库，而屏上看起来像同一时刻的快照。
//
// 库里没有这个项目时后端回的是 `404 {"code":"NOT_FOUND"}`——**带 `code`**，
// 与框架的路由未命中（`{"detail":"Not Found"}`）不是一回事，
// 取数件按这一点把两者分开（见 `web/lib/screenClient.ts`）。
export default function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);

  const { state } = useScreenData<unknown>(`/projects/${id}`);

  return (
    <Screen title={t("overview.title")} meta={t("overview.meta", { id })}>
      <ScreenFetchState state={state}>
        {(data) => <ProjectOverview overview={toProjectOverviewView(data)} />}
      </ScreenFetchState>
      {/* NAV-05：项目总览是这一族的枢纽——三条支路都按项目走，而 id 就在手上。
          此前它们各自是孤岛（`/projects/[id]/proposal` 建于 CHAIN-05 之后
          一直没人能点到）。

          受众分叉为什么从这里进、而不是从报告屏：报告屏只有交付物 id，
          **交付物 → 项目没有可读的对应关系**（`GET /deliverables/{id}/blocks`
          回的是 `{deliverable_id, blocks}`）。从那边接就得猜一个项目 id。

          入口放在取数状态外面：总览读失败 NEVER 把三条支路一起带走。 */}
      <p className="data-row" data-project-links>
        <span className="data-row__label">{t("overview.elsewhere")}</span>
        <a
          className="data-row__value"
          data-topics-link
          href={`/projects/${encodeURIComponent(id)}/topics`}
        >
          {t("overview.topics")}
        </a>
        <a
          className="data-row__value"
          data-analysis-link
          href={`/projects/${encodeURIComponent(id)}/analysis`}
        >
          {t("overview.analysis")}
        </a>
        <a
          className="data-row__value"
          data-proposal-link
          href={`/projects/${encodeURIComponent(id)}/proposal`}
        >
          {t("overview.proposal")}
        </a>
      </p>
    </Screen>
  );
}
