import type { JSX, ReactNode } from "react";

import { NotProvided } from "../shell/NotProvided";
import type { ActionOutcome } from "../plaza/cardActions";
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
 *
 * ## ②→③ 从这里走（`CHAIN-UI-01-a`）
 *
 * - **跑完的分析作业**旁边有「生成报告」。它带着那条作业的号去提交，换算成产物 id 是服务端的事
 *   （`DEC-061`）。只在 `gate1_analysis` 且 `done` 时出现：别的作业没有可成文的来源，
 *   没跑完的提交了也只会被服务端拒——那句拒绝服务端照样会说，这里少画一个必然被拒的键。
 * - **交付物清单点得进去**，并显示后端给的版本号与「取代哪一份」（`DEC-063`：这份清单是唯一的真相）。
 *   提交了成文或重写之后，产物就是从这里找到的。
 */

export type OverviewRow = {
  id: string;
  label: string;
  state?: string | null;
  /** 作业的 kind（后端原值）。 */
  kind?: string | null;
  /** 交付物的版本号（后端原值；没有就是 `null`，NEVER 补一个 1）。 */
  version?: number | null;
  /** 这一份取代的那一份的 id。 */
  supersedes?: string | null;
};

/**
 * 「生成报告」那个动作。**不给就一个键都不画**——只读场合不出现点了没反应的键。
 * 状态由调用方持有：本组件只画，不发请求。
 */
export type ReportAction = {
  /** 提交在飞的那条分析作业；在飞时所有键都不可点（NEVER 开出第二个作业）。 */
  busyJobId: string | null;
  outcome: ActionOutcome | null;
  onStart: (analysisJobId: string) => void;
};

/** 成文的来源只能是一条跑完的 Gate① 分析——与服务端核的那两件同一口径。 */
const REPORT_SOURCE_KIND = "gate1_analysis";
const REPORT_SOURCE_STATE = "done";

export type ProjectOverviewView = {
  projectId: string;
  title: string;
  topics: OverviewRow[];
  jobs: OverviewRow[];
  deliverables: OverviewRow[];
};

function Section({ name, rows, emptyKey, idCell, trailing, footer }: {
  name: string;
  rows: OverviewRow[];
  emptyKey: string;
  /** id 那一格怎么画（缺省是纯文字）。 */
  idCell?: (row: OverviewRow) => ReactNode;
  /** 行尾多出来的东西（按钮、版本号）。 */
  trailing?: (row: OverviewRow) => ReactNode;
  footer?: ReactNode;
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
              <span className="overview__row-id">{idCell ? idCell(row) : row.id}</span>
              <span className="overview__row-label">{row.label}</span>
              {row.state ? (
                <span className="overview__row-state" data-row-state={row.state}>
                  {/* DS-03：屏上给人话，`data-row-state` 上留原值——
                      取证与判据认的是原值，人看的是标签，两者各归各的。 */}
                  {enumLabel("job_state", row.state)}
                </span>
              ) : null}
              {trailing ? trailing(row) : null}
            </li>
          ))}
        </ul>
      )}
      {footer}
    </section>
  );
}

function outcomeText(outcome: ActionOutcome): string {
  if (outcome.kind === "not_provided") return t("chain.not_provided");
  if (outcome.kind === "unsupported") {
    return t("card.action.unsupported", { allowed: outcome.allowed.join(" / ") });
  }
  if (outcome.kind === "failed") {
    // 服务端自己的那句话**原样带出来**（哪条作业、卡在哪个状态都在里面），
    // NEVER 改写成一句通用的「提交失败」。
    return outcome.message || t("chain.failed", { status: String(outcome.status) });
  }
  return t("chain.submitted");
}

export function ProjectOverview(
  { overview, report }: { overview: ProjectOverviewView | null; report?: ReportAction },
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
      <Section
        name="jobs" rows={overview.jobs} emptyKey="overview.jobs.empty"
        trailing={(row) => (
          report && row.kind === REPORT_SOURCE_KIND && row.state === REPORT_SOURCE_STATE ? (
            <button
              type="button"
              className="chain-form__submit"
              data-report-from-job={row.id}
              disabled={report.busyJobId !== null}
              onClick={() => report.onStart(row.id)}
            >
              {report.busyJobId === row.id
                ? t("overview.report.submitting") : t("overview.report.start")}
            </button>
          ) : null
        )}
        footer={report?.outcome ? (
          <p className="chain-form__outcome" data-report-outcome={report.outcome.kind}
            role="status">
            {outcomeText(report.outcome)}
          </p>
        ) : null}
      />
      <Section
        name="deliverables" rows={overview.deliverables}
        emptyKey="overview.deliverables.empty"
        idCell={(row) => (
          <a data-deliverable-link href={`/deliverables/${encodeURIComponent(row.id)}`}>
            {row.id}
          </a>
        )}
        trailing={(row) => (
          <>
            {typeof row.version === "number" ? (
              <span className="overview__row-state"
                data-deliverable-version={String(row.version)}>
                {t("overview.deliverable.version", { version: String(row.version) })}
              </span>
            ) : null}
            {row.supersedes ? (
              <span className="overview__row-state"
                data-deliverable-supersedes={row.supersedes}>
                {t("overview.deliverable.supersedes", { id: row.supersedes })}
              </span>
            ) : null}
          </>
        )}
      />
    </section>
  );
}
