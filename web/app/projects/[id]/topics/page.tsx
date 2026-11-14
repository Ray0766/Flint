"use client";

import { use, type JSX } from "react";

import { ScreenFetchState } from "../../../../lib/ScreenFetchState";
import { API_BASE, API_USER_ID } from "../../../../lib/apiBase";
import { JudgeTabs } from "../../../../components/judge-tabs/JudgeTabs";
import { Screen } from "../../../../components/shell/Screen";
import { TopicListView } from "../../../../components/views/TopicListView";
import { t } from "../../../../lib/i18n/t";
import { useScreenData } from "../../../../lib/useScreenData";
import type { ProjectTopics } from "../../../../lib/topicClient";

// CHAIN-03 / 蓝本 P4：主题列表 + 选主题。
//
// ## 改前：这一屏**不存在**
//
// `web/app/` 下没有 `topics` 那一层。组件（`TopicListView`）建好了，
// 但只有 `DemoFlow` 那个演示串屏在用——**用户从广场走不到主题**。
// 「实仓 16 屏 vs 蓝本 P1~P14，缺六屏」里的第一屏就是它。
//
// ## 选主题现在落得了地（`ENTRY-02`）
//
// 改前：`GET /projects/{id}/topics` 回的 `chosen_topic_id` 是**读**的那一半，
// 写的那一半没有端点，所以点「选它」时这一屏只能如实说这条还没接。
//
// v0.4.1 第 6 批建了 `POST /projects/{id}/chosen-topic`（`flint/api/topics.py`）。
// 接上之后**那条纪律一个字没松**：选中态**恒由后端回的 `chosen_topic_id` 决定**，
// 这一屏 NEVER 自己记一份——本地先改一下会让它「看起来快」，
// 而那份影子状态刷新一次就没了，用户却以为自己已经选过。
// 所以这里的做法是：POST → **重新取一次**，屏上显示的永远是库里的那个值。
//
// ## 空表是空态，不是错误
//
// 演示库当日没有主题，`topics: []`。那是**查过了、确实没有**，
// 与「没查过」「查坏了」各是一件事——三者由 `ScreenFetchState` 分开。
export default function ProjectTopicsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const { state, refetch } = useScreenData<ProjectTopics>(`/projects/${id}/topics`);

  const chooseTopic = (topicId: string): void => {
    const headers: Record<string, string> = { "content-type": "application/json" };
    if (API_USER_ID) headers["x-user-id"] = API_USER_ID;
    void fetch(`${API_BASE}/projects/${encodeURIComponent(id)}/chosen-topic`, {
      method: "POST",
      headers,
      body: JSON.stringify({ topic_id: topicId }),
      // **不看返回体**：拿它去更新本地状态就等于在前端记了一份（见上面那段）。
    }).then((res) => {
      if (!res.ok) return;              // 失败时屏上原样不动——后端说了算
      // 成功之后**重读这一条端点**（`UIX-05`）。
      //
      // 改前这里是 `window.location.reload()`：那时 `useScreenData` 只收一个
      // `path`、**没有 refetch 句柄**，而给它加一个是 `web/lib/` 的改动，
      // 超出了 `ENTRY-02` 的 outputs——**它当时是唯一诚实的选择**。
      // `UIX-05` 把句柄加上了，所以整屏重读退役
      // （它会丢掉滚动位置与屏内其它状态）。
      //
      // 仍然**不读返回体**：拿它去更新本地状态就等于在前端记了一份，
      // 而那**刷新一次就没了**，用户却以为自己已经选过。
      // 也仍然 NEVER 拿一个变化的假 query 去骗重取——`DEC-035` 判死的形状。
      // **屏上显示的恒是库里那个值。**
      refetch();
    });
  };

  return (
    <Screen title={t("topic.screen.title")} meta={t("topic.screen.meta")}>
      {/* `JUDGE-TAB-01`：判定台五件之间的屏内互链带。**它不是路由**——
          `DEC-060` 第二条：29 条路由与 7 个导航入口一条不动，
          v4 的「5 tab」只以这条带的形式吸收。
          作业 id 与交付物 id 这一屏手上没有，所以那三条走「未就绪」并说出在等什么，
          **NEVER 拼一个 id 出来**（`DEC-012` 同一条纪律）。 */}
      <JudgeTabs projectId={id} current="topics" />
      <ScreenFetchState state={state}>
        {(data) => (
          <TopicListView
            topics={data.topics}
            // 选中态**恒取后端的值**。前端不记一份（见上）。
            chosenTopicId={data.chosen_topic_id}
            onSelectTopic={chooseTopic}
            // NAV-05：项目 id 一路带到主题详情（`?project=`）。
            // 主题详情自己不知道它属于哪个项目，而下一跳按项目发起。
            projectId={id}
          />
        )}
      </ScreenFetchState>
      {/* NAV-05：这一屏此前是条**死路**——进来之后无处可去。
          项目总览与发起分析都按项目走，而项目 id 正好在手上。

          入口放在取数状态**外面**：主题列表读失败 NEVER 把这两条路一起带走，
          它们与主题读没读到没有关系。 */}
      <p className="data-row" data-project-entries>
        <span className="data-row__label">{t("topic.screen.elsewhere")}</span>
        <a
          className="data-row__value"
          data-project-overview-link
          href={`/projects/${encodeURIComponent(id)}`}
        >
          {t("topic.screen.overview")}
        </a>
        <a
          className="data-row__value"
          data-project-analysis-link
          href={`/projects/${encodeURIComponent(id)}/analysis`}
        >
          {t("topic.screen.analysis")}
        </a>
      </p>
    </Screen>
  );
}
