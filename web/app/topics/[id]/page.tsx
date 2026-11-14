"use client";

import { use, useEffect, useState, type JSX } from "react";

import { ScreenFetchState } from "../../../lib/ScreenFetchState";
import { Screen } from "../../../components/shell/Screen";
import { TopicDetail } from "../../../components/topic-detail/TopicDetail";
import { t } from "../../../lib/i18n/t";
import { useScreenData } from "../../../lib/useScreenData";
import type { Topic } from "../../../lib/topicClient";

// CHAIN-03 / 蓝本 P5：主题详情。
//
// ## 改前：这一屏与它的组件**都不存在**
//
// 端点 `GET /topics/{id}` 早就装配了（`TYPE-02` 也把类型建好了），
// 而实仓既没有路由也没有组件——用户点开一条主题，无处可去。
//
// ## 未知 id 回的是**带 `code` 的 404**
//
// `flint/api/views.py` 的说明逐字写着「未知 → 404」。
// 那与框架的路由未命中（`{"detail":"Not Found"}`，**没有 `code`**）不是一回事：
// 前者是「这一条不存在」，后者是「这个能力还没挂」。
// 两者由 `web/lib/screenClient.ts` 分开，屏上因此显示两句不同的话。
//
// ## 响应是**带信封的**：`{"topic": {...}}`（`SEED-01` 修）
//
// 改前这里写的是 `useScreenData<Topic>`，把整个响应体当成 `Topic`——
// 于是 `topic.why_now` 是 `undefined`，屏上抛
// `Cannot read properties of undefined (reading 'evidences')`。
//
// **这个错在库里没有主题时看不见**：那时端点恒回 404，这一屏走的是诚实态分支，
// 从来没有真正渲染过一次。`SEED-01` 种下第一条主题、取证样例换过来之后，
// 探针第一次跑到 `ready` 分支，它当场就现形了——
// **一条被 404 挡着的红**。
//
// `fetchScreen` 把响应体原样当 `T` 返回（它**不该**去猜信封长什么样），
// 所以拆信封是这一屏的事。
type TopicEnvelope = { topic: Topic };

export default function TopicDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const { state } = useScreenData<TopicEnvelope>(`/topics/${id}`);
  // NAV-05：下一跳「发起分析」是**按项目**发起的，而这一屏不知道自己属于哪个项目
  // ——`GET /topics/{id}` 回的 `Topic` 里没有 project_id（冻结件里也没有）。
  // 所以项目 id 由**调用方**带过来（主题列表那条链接上的 `?project=`），
  // 与 `AnalysisView` 的 `verdictJobId` 同一形态。
  //
  // `undefined` = 还没读 URL；`null` = 读过了、调用方没给。两者 NEVER 共用一个值：
  // 前者时把「没有项目」那句话说出去会先闪一下假话再改口。
  const [projectId, setProjectId] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    setProjectId(new URLSearchParams(window.location.search).get("project"));
  }, []);

  return (
    <Screen title={t("topic.detail.title")} meta={t("topic.detail.meta")}>
      <ScreenFetchState state={state}>
        {(data) => <TopicDetail topic={data.topic} />}
      </ScreenFetchState>
      {projectId === undefined ? null : (
        <p className="data-row" data-analysis-entry>
          <span className="data-row__label">{t("topic.detail.next")}</span>
          {projectId ? (
            <a
              className="data-row__value"
              data-analysis-link
              href={`/projects/${encodeURIComponent(projectId)}/analysis?topic=${encodeURIComponent(id)}`}
            >
              {t("topic.detail.start_analysis")}
            </a>
          ) : (
            // 没带项目就**说出来**，NEVER 拿 topic_id 拼一个项目去试：
            // 猜错时用户会把这条主题的分析发起到**别人的项目**上，而那要花钱。
            <span className="data-row__value" data-analysis-no-project>
              {t("topic.detail.no_project")}
            </span>
          )}
        </p>
      )}
    </Screen>
  );
}
