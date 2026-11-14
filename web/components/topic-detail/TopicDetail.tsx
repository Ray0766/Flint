"use client";

// CHAIN-03：主题详情（蓝本 P5）。实仓此前**只有列表那一个组件**，详情连组件都没有。
//
// ## 它显示的是 `Topic` 真有的那些字段
//
// 冻结件 `contracts/models.py#Topic` 的字段就这些：
// `topic_id` / `seed_id` / `one_liner` / `target_user_tag` / `form_factor_tag` /
// `why_now` / `keyword_mapping` / `embedding`。
//
// **没有名称三元组**（`name_native` / 机翻译名）——规格 `#2.4` 要求主题屏上名称三元组，
// 而冻结件里没有那两个字段。本组件因此**不画那两槽**，NEVER 拿 `one_liner` 冒充
// `name_native`：那是「借一个已经有主的字段说另一件事」（`DEC-034` 刚立下的同一条）。
// 缺口已立单：`docs/blocked/TOPIC-HAS-NO-NAME-TRIPLE.md`。
//
// ## `speculative` 是**后端定的**，前端只据实降权
//
// `why_now.evidences` 为空 → 后端置 `speculative=true`（冻结件 `[C2]`）。
// 屏上给它一个可见的记号，**NEVER 因为它就把 why_now 藏起来**：
// 藏起来的话，用户看不出这条主题的「为什么是现在」是没有证据支撑的推测。
//
// ## 证据逐条列出，NEVER 合成一句
//
// 每条证据带自己的 `citation_id`——那是「结论必有引用」在这一屏上的形状。
// 合成一句「多项证据表明…」就把每一条的出处都丢了。

import type { JSX } from "react";

import { DsStatusMark } from "../shell/DsStatusMark";
import { t } from "../../lib/i18n/t";
import { topicKeywords, type Topic } from "../../lib/topicClient";

export function TopicDetail({
  topic,
  chosen = false,
}: {
  topic: Topic;
  /** 它是不是这个 project 选中的那条。**由后端的 `chosen_topic_id` 决定**。 */
  chosen?: boolean;
}): JSX.Element {
  const evidences = topic.why_now.evidences;

  return (
    <article
      className="topic-detail"
      data-topic-detail="true"
      data-topic-id={topic.topic_id}
      data-chosen={chosen ? "true" : "false"}
      data-speculative={topic.why_now.speculative ? "true" : "false"}
    >
      <header className="topic-detail__head">
        <h2 className="topic-detail__one-liner" data-topic-one-liner>
          {topic.one_liner}
        </h2>
        {chosen ? (
          <DsStatusMark status="verified" label={t("topic.chosen")} />
        ) : null}
      </header>

      <div className="topic-detail__tags">
        <span className="topic-card__tag" data-topic-target-user>
          {t("topic.target_user")}: {topic.target_user_tag}
        </span>
        <span className="topic-card__tag" data-topic-form-factor>
          {t("topic.form_factor")}: {topic.form_factor_tag}
        </span>
      </div>

      <section className="topic-detail__why-now" data-topic-why-now-block>
        <h3 className="topic-detail__section-title">{t("topic.why_now")}</h3>
        <p data-topic-why-now>{topic.why_now.claim}</p>
        {topic.why_now.speculative ? (
          // 后端定的推测标。**NEVER 因为它就把上面那句藏起来**——
          // 藏起来的话，用户看不出这条「为什么是现在」是没有证据支撑的。
          <DsStatusMark status="speculative" label={t("topic.speculative")} />
        ) : null}
        {evidences.length === 0 ? (
          // 「一条证据都没有」是**实况**，不是错误。说出来，NEVER 留空。
          <p className="topic-detail__no-evidence" data-topic-evidence-empty="true">
            {t("topic.evidence.none")}
          </p>
        ) : (
          <ul className="topic-detail__evidences" data-topic-evidences="true">
            {evidences.map((evidence) => (
              <li
                key={evidence.citation_id}
                className="topic-detail__evidence"
                data-citation-id={evidence.citation_id}
              >
                <span data-evidence-event>{evidence.event}</span>
                {/* 日期后端给，前端不解析、不换算（零计算）。 */}
                <time className="topic-detail__date" dateTime={evidence.event_date}>
                  {evidence.event_date}
                </time>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="topic-detail__keywords">
        <h3 className="topic-detail__section-title">{t("topic.keywords")}</h3>
        <p data-topic-keywords>{topicKeywords(topic).join(" · ")}</p>
      </section>
    </article>
  );
}
