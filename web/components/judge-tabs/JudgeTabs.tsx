import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/**
 * `JUDGE-TAB-01`：判定台五件之间的**屏内互链带**。
 *
 * ## 它是一条导航条，不是一条路由（`DEC-060` 第二条）
 *
 * v4 把这五件做成一屏五个 tab（`主题列表 / Gate① 判定 / 作业进度 / 受众选择 / vibe_pack`）。
 * 本仓这五件是**五条独立路由**，而 `DEC-060` 逐字写着：29 条路由与 7 个导航入口一条不动，
 * v4 的 5 tab **只以互链带的形式吸收**。
 *
 * 所以这里 NEVER 新建 `/judge` 一类的合并屏、NEVER 碰 `NAV_ITEMS`——
 * 它只是把五条既有路由摆在同一条上，让人从其中任何一件走到另一件。
 * 改前这五件彼此之间**一条互链都没有**（只有项目总览各链一次）。
 *
 * ## 五条路由要的 id **不是同一个**
 *
 * | tab | 路由 | 要哪个 id |
 * |---|---|---|
 * | 主题列表 | `/projects/{id}/topics` | project |
 * | Gate① 判定 | `/gate/{id}` | job（判定作业） |
 * | 作业进度 | `/jobs/{id}` | job |
 * | 受众选择 | `/projects/{id}/proposal` | project |
 * | vibe_pack | `/deliverables/{id}/pack` | deliverable |
 *
 * 拿不到某一个 id 时，那一条走**「未就绪」**那条路并**说出它在等什么**——
 * **NEVER 拼一个 id 出来**（`DEC-012` 拒绝猜 verdictJob 是同一条纪律），
 * 也 NEVER 把它静默灰掉：灰掉的那一条与「这个功能没做」在屏上长得一模一样。
 */

export type JudgeTabKey = "topics" | "gate" | "job" | "audience" | "pack";

export type JudgeTabsProps = {
  /** 项目 id：两条 tab 靠它。没有它就没有这条带（调用方自己判）。 */
  projectId: string;
  /** 判定/进度那两条要的作业 id。拿不到就传 `null`。 */
  jobId?: string | null;
  /** vibe_pack 那条要的交付物 id。拿不到就传 `null`。 */
  deliverableId?: string | null;
  /** 当前在哪一件（那一条带 `aria-current`）。 */
  current: JudgeTabKey;
};

/**
 * 一条 tab。**`href` 在 JSX 的 `href={…}` 那一处就地拼**，不在这里存成字符串——
 * 前后端对账那把尺子（`tools/check_fe_be_parity.py`）按 `href={…}` 的形状
 * 把「导航」与「调用」分开；把路径先存进变量再传给 `href`，
 * 它就会把 `/gate/{}` 当成一条前端在调而后端没有的 API（实测：整批全跑时红了两条）。
 * **导航不是调用**——这条区分要写成尺子读得懂的形状。
 */
type Tab = {
  key: JudgeTabKey;
  /** 这一条要的 id。`null` = 还没有 → 走未就绪那条路。 */
  id: string | null;
  /** 这一条为什么还去不了（`id` 为 `null` 时必给）。 */
  waitingFor?: string;
};

export function JudgeTabs({
  projectId,
  jobId,
  deliverableId,
  current,
}: JudgeTabsProps): JSX.Element {
  const tabs: Tab[] = [
    { key: "topics", id: projectId },
    { key: "gate", id: jobId ?? null, waitingFor: t("judge.tabs.waiting.job") },
    { key: "job", id: jobId ?? null, waitingFor: t("judge.tabs.waiting.job") },
    { key: "audience", id: projectId },
    // `PackViewer` 的既有口径：`not_generated` 是「还没生成」，
    // 不是 404，也不是一个空的九章骨架。这里说的是同一件事。
    { key: "pack", id: deliverableId ?? null, waitingFor: t("judge.tabs.waiting.pack") },
  ];

  return (
    <nav className="judge-tabs" data-judge-tabs={current} aria-label={t("judge.tabs.label")}>
      <ol className="judge-tabs__list">
        {tabs.map((tab) => (
          <li
            key={tab.key}
            className="judge-tabs__item"
            data-judge-tab={tab.key}
            data-judge-tab-ready={tab.id ? "true" : "false"}
          >
            {tab.id === null ? (
              <>
                {/* 去不了的那一条**仍然列出来**，并说出它在等什么。
                    藏起来的话，用户不知道这一步存在；灰着不说的话，
                    他不知道自己要做什么才能走过去。 */}
                <span className="judge-tabs__link judge-tabs__link--waiting">
                  {t(`judge.tabs.${tab.key}`)}
                </span>
                <span className="judge-tabs__waiting" data-judge-tab-waiting={tab.key}>
                  {tab.waitingFor}
                </span>
              </>
            ) : (
              <a
                className="judge-tabs__link"
                href={
                  tab.key === "topics"
                    ? `/projects/${encodeURIComponent(tab.id)}/topics`
                    : tab.key === "audience"
                      ? `/projects/${encodeURIComponent(tab.id)}/proposal`
                      : tab.key === "gate"
                        ? `/gate/${encodeURIComponent(tab.id)}`
                        : tab.key === "job"
                          ? `/jobs/${encodeURIComponent(tab.id)}`
                          : `/deliverables/${encodeURIComponent(tab.id)}/pack`
                }
                aria-current={tab.key === current ? "page" : undefined}
              >
                {t(`judge.tabs.${tab.key}`)}
              </a>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
