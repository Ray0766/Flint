import type { JSX } from "react";

import { NotProvided } from "../shell/NotProvided";
import { enumLabel } from "../../lib/i18n/enumLabel";
import { t } from "../../lib/i18n/t";

/**
 * UI-11 / 蓝本 P14：项目总览。
 *
 * ## 蓝本那句「无专属端点」已经过时
 *
 * README 路由表把 P14 记成「无专属端点：topics + jobs + deliverables 组合」。
 * BE-01 本轮把 `GET /projects/{id}` 建出来了——**一次查齐**。
 *
 * 一次查齐不只是省几个请求：三次分别查回来的东西对应的是**三个时刻的库**，
 * 而屏上看起来像同一时刻的快照（BE-01 的 `DeliverableStaleness` docstring
 * 记的是同一条理由）。
 *
 * ## 三个列表**恒存在**
 *
 * BE-01：「没有内容时是空数组，不是缺这个键、更不是 404」。
 * 前端照办：空列表画成空态（「还没有主题」），**NEVER 把整屏画成错误页**。
 *
 * ## 零计算
 *
 * 不排序（后端给什么序渲染什么序）、不合成进度、不数出一个「完成度」。
 * 屏上每个数都是**计数**，且都由后端给。
 */

export type OverviewRow = { id: string; label: string; state?: string | null };

export type ProjectOverviewView = {
  projectId: string;
  title: string;
  topics: OverviewRow[];
  jobs: OverviewRow[];
  deliverables: OverviewRow[];
};

function Section({ name, rows, emptyKey }: {
  name: string;
  rows: OverviewRow[];
  emptyKey: string;
}): JSX.Element {
  return (
    <section className="overview__section" data-overview-section={name}
      data-overview-count={String(rows.length)}>
      <h3 className="overview__section-title">{t(`overview.${name}`)}</h3>
      {rows.length === 0 ? (
        // 空列表是空态，不是错误页。
        <p className="overview__empty">{t(emptyKey)}</p>
      ) : (
        <ul className="overview__list">
          {rows.map((row) => (
            <li key={row.id} className="overview__row">
              <span className="overview__row-id">{row.id}</span>
              <span className="overview__row-label">{row.label}</span>
              {row.state ? (
                <span className="overview__row-state" data-row-state={row.state}>
                  {/* DS-03：屏上给人话，`data-row-state` 上留原值——
                      取证与判据认的是原值，人看的是标签，两者各归各的。 */}
                  {enumLabel("job_state", row.state)}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ProjectOverview(
  { overview }: { overview: ProjectOverviewView | null },
): JSX.Element {
  if (overview === null) {
    return (
      <section className="overview" data-overview-state="not_provided">
        <NotProvided label={t("overview.not_provided")} />
      </section>
    );
  }

  return (
    <section className="overview" data-overview-state="ready">
      <h2 className="overview__title">{overview.title}</h2>
      <Section name="topics" rows={overview.topics} emptyKey="overview.topics.empty" />
      <Section name="jobs" rows={overview.jobs} emptyKey="overview.jobs.empty" />
      <Section name="deliverables" rows={overview.deliverables}
        emptyKey="overview.deliverables.empty" />
    </section>
  );
}
