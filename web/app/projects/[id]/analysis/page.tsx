"use client";

import { use, useState, type JSX } from "react";

import { API_BASE } from "../../../../lib/apiBase";
import { DsStatusMark } from "../../../../components/shell/DsStatusMark";
import { Screen } from "../../../../components/shell/Screen";
import { submitAnalysis } from "../../../../components/chain/chainClient";
import { t } from "../../../../lib/i18n/t";
import type { ActionOutcome } from "../../../../components/plaza/cardActions";

// CHAIN-04 / 蓝本 P6：发起分析。**改前这一屏不存在**——
// 端点 `POST /projects/{id}/analysis` 第 4 批就装配了，而没有任何界面能触发它。
//
// ## 提交之后进 Job 进度屏，**NEVER 在本屏轮询**
//
// 端点回 `{job_id}`，本屏据此跳到 `/jobs/{job_id}`——那一屏已经接了 SSE
// （`web/lib/jobClient.ts#openJobStream`）。在本屏轮询的话，同一个作业会有两处在看，
// 而两处的进度**永远差一拍**，用户不知道该信哪一个。
//
// ## 前端**不写自己的那句拒绝话术**
//
// 卡面 acceptance② 要「前端本地预检话术与服务端逐字一致」。实测两条端点对空假设的
// 答复并不是同一句（见 `chainClient.ts` 的说明与
// `docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md`）。所以本屏一句拒绝话都不写：
// 提交键的禁用只做物理约束（预算没填），**被拒的理由恒由服务端说**。
export default function StartAnalysisPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const [keywords, setKeywords] = useState("");
  const [budget, setBudget] = useState("");
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  const [busy, setBusy] = useState(false);

  const budgetOk = budget.trim() !== "" && Number.isFinite(Number(budget));

  const start = (): void => {
    setBusy(true);
    void submitAnalysis(
      id,
      {
        // 逗号分隔是**输入方式**，不是数据形状：切完就交给后端。
        keywords: keywords.split(",").map((k) => k.trim()).filter((k) => k !== ""),
        budgetCny: Number(budget),
      },
      { baseUrl: API_BASE },
    ).then((result) => {
      setOutcome(result);
      setBusy(false);
      const jobId = result.kind === "ok" ? result.detail["job_id"] : null;
      if (typeof jobId === "string" && jobId !== "") {
        // 进 Job 进度屏。**NEVER 在本屏轮询**。
        window.location.assign(`/jobs/${encodeURIComponent(jobId)}`);
      }
    });
  };

  return (
    <Screen title={t("analysis.title")} meta={t("analysis.meta")}>
      <section className="chain-form" data-analysis-form="true">
        <label className="chain-form__label" htmlFor="analysis-keywords">
          {t("analysis.keywords.label")}
        </label>
        <input
          id="analysis-keywords"
          className="chain-form__input"
          data-testid="analysis-keywords"
          value={keywords}
          placeholder={t("analysis.keywords.placeholder")}
          onChange={(e) => setKeywords(e.target.value)}
        />

        <label className="chain-form__label" htmlFor="analysis-budget">
          {t("analysis.budget.label")}
        </label>
        <input
          id="analysis-budget"
          className="chain-form__input"
          data-testid="analysis-budget"
          inputMode="decimal"
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
        />

        <div className="chain-form__actions">
          <button
            type="button"
            className="chain-form__submit"
            data-testid="analysis-submit"
            // 只做物理约束：预算是端点的必填项。**不解释「为什么会被拒」**——
            // 那句话恒由服务端说。
            disabled={busy || !budgetOk}
            onClick={start}
          >
            {t("analysis.submit")}
          </button>
          {busy ? (
            // 提交在飞。改前这里什么都不说——用户按下去之后无从知道有没有发生什么，
            // 于是会再按一次（而那会开出第二个作业）。
            <DsStatusMark status="review" label={t("analysis.submitting")} />
          ) : null}
        </div>

        {outcome ? (
          <p
            className="chain-form__outcome"
            data-testid="analysis-outcome"
            data-outcome-kind={outcome.kind}
            role="status"
          >
            {outcome.kind === "not_provided"
              ? t("chain.not_provided")
              : outcome.kind === "unsupported"
                ? t("card.action.unsupported", { allowed: outcome.allowed.join(" / ") })
                : outcome.kind === "failed"
                  // 后端自己的说明原样带出来，NEVER 改写成一句通用的「参数不对」。
                  ? outcome.message
                    || t("chain.failed", { status: String(outcome.status) })
                  : t("chain.submitted")}
          </p>
        ) : null}
      </section>
    </Screen>
  );
}
