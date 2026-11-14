import type { JSX } from "react";

import { topicKeywords, type Topic } from "../../lib/topicClient";
import { t } from "../../lib/i18n";

// 主题呈现（TS-008，纯呈现）：广场/工作台展示候选 Topic——one_liner + 两维 tag +
// keywords + why_now（speculative 灰标降权，前端只据实展示、NEVER 自判）。
// 选 Topic → onSelectTopic(topic_id)（上层串 chosen_topic_id → 发起 gate 分析）。
export function TopicListView({
  topics,
  chosenTopicId,
  onSelectTopic,
  projectId,
}: {
  topics: Topic[];
  chosenTopicId?: string | null;
  onSelectTopic?: (topicId: string) => void;
  /**
   * NAV-05：给了它，每条主题多一个**查看**入口（→ 主题详情）。
   *
   * 选中与查看是**两件事**（与 `DEC-042` ① 同一条）：
   * 「选为本项目的主题」是一个动作，落盘之后人还在这一屏；
   * 「看看这条主题讲什么」是一个去处。合成一个按钮的话，
   * 用户想看一眼就会顺手把项目的主题改掉。
   *
   * 项目 id 要一路带到详情屏（`?project=`）：主题详情自己**不知道**
   * 它属于哪个项目（`GET /topics/{id}` 回的 `Topic` 里没有 project_id），
   * 而下一跳「发起分析」是按项目发起的。**调用方持有**，与
   * `AnalysisView` 的 `verdictJobId` 同一形态；没有就是没有，NEVER 猜一个。
   */
  projectId?: string | null;
}): JSX.Element {
  return (
    <section className="topic-list" data-topic-list="true">
      <h2 className="topic-list__heading">{t("topic.title")}</h2>
      {topics.length === 0 ? (
        <p className="topic-list__empty" data-topic-empty="true">{t("topic.empty")}</p>
      ) : (
        <ul className="topic-list__grid">
          {topics.map((topic) => {
            const chosen = topic.topic_id === chosenTopicId;
            return (
              <li
                key={topic.topic_id}
                className="topic-card"
                data-topic-id={topic.topic_id}
                data-speculative={topic.why_now.speculative ? "true" : "false"}
                data-chosen={chosen ? "true" : "false"}
              >
                <p className="topic-card__one-liner" data-topic-one-liner>
                  {topic.one_liner}
                </p>
                <div className="topic-card__tags">
                <span className="topic-card__tag" data-topic-target-user>
                  {t("topic.target_user")}: {topic.target_user_tag}
                </span>
                <span className="topic-card__tag" data-topic-form-factor>
                  {t("topic.form_factor")}: {topic.form_factor_tag}
                </span>
                </div>
                <span className="topic-card__meta" data-topic-keywords>
                  {t("topic.keywords")}: {topicKeywords(topic).join(", ")}
                </span>
                <span className="topic-card__why-now" data-topic-why-now>
                  {t("topic.why_now")}: {topic.why_now.claim}
                </span>
                {topic.why_now.speculative && (
                  <span className="topic-card__speculative"
                    data-topic-speculative-mark>{t("topic.speculative")}</span>
                )}
                <button
                  type="button"
                  className="topic-card__choose"
                  data-topic-choose={topic.topic_id}
                  onClick={() => onSelectTopic?.(topic.topic_id)}
                >
                  {chosen ? t("topic.chosen") : t("topic.choose")}
                </button>
                {projectId ? (
                  <a
                    className="topic-card__open"
                    data-topic-open={topic.topic_id}
                    href={`/topics/${encodeURIComponent(topic.topic_id)}?project=${encodeURIComponent(projectId)}`}
                  >
                    {t("topic.open")}
                  </a>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
