"use client";

import { use, useState, type JSX } from "react";

import { API_BASE, API_USER_ID } from "../../../../lib/apiBase";
import { Screen } from "../../../../components/shell/Screen";
import { t } from "../../../../lib/i18n/t";
import type { ActionOutcome } from "../../../../components/plaza/cardActions";

// CHAIN-05 / 蓝本 P11：受众分叉。**改前这一屏不存在**——
// 端点 `POST /projects/{id}/proposal` 早就装配了，而没有界面能选受众。
//
// ## 受众**没有默认值**（`flint/compose/audience.py#plan_proposal` 的原话）
//
//     audience is mandatory with no default: human_reader | ai_executor
//
// 所以屏上初值是**没选**，提交键在选之前点不动。
// 给一个默认值等于替用户做了这个决定，而这两条路产出的东西完全不同：
// 五套人类模板是**给人读的散文**，vibe_pack 是**喂给执行者的材料**。
//
// ## `ai_executor` 锁 vibe_pack（服务端规则，前端只呈现）
//
// 后端：`ai_executor` 的 `template_id` 只能是 `vibe_pack` 或不给，混用 → 422。
// 本屏在选了 `ai_executor` 时把模板选择器换成**一个固定值的说明**，
// 而不是把五个选项灰掉——灰掉的五个仍然在屏上，用户会以为「再等等就能选」。
//
// 五套人类模板的清单来自后端 `HUMAN_TEMPLATES`。**前端这份是镜像**，
// 判据钉着两边逐字相等（`test_audience_and_intervention_screens.py`）。
const HUMAN_TEMPLATES = ["generic", "thesis", "startup", "engineering", "grant"] as const;
const AI_TEMPLATE = "vibe_pack";

type Audience = "human_reader" | "ai_executor";

export default function ProposalForkPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const [audience, setAudience] = useState<Audience | null>(null);
  const [templateId, setTemplateId] = useState<string>(HUMAN_TEMPLATES[0]);
  const [reportId, setReportId] = useState("");
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);

  const submit = (): void => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (API_USER_ID) headers["x-user-id"] = API_USER_ID;
    void fetch(`${API_BASE}/projects/${encodeURIComponent(id)}/proposal`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        audience,
        report_id: reportId,
        // `ai_executor` 那条**不带 template_id**：后端自己锁 vibe_pack。
        // 前端替它填上去的话，哪天后端换了名字，这里会开始发一个被拒的值。
        template_id: audience === "ai_executor" ? null : templateId,
      }),
    }).then(async (res) => {
      const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
      if (!res.ok) {
        const detail = payload["detail"];
        const first = Array.isArray(detail) && detail.length > 0
          ? (detail[0] as Record<string, unknown>) : null;
        setOutcome({
          kind: "failed",
          status: res.status,
          // 后端自己的说明原样带出来，NEVER 改写。
          message: String(payload["message"] ?? first?.["msg"] ?? ""),
        });
        return;
      }
      setOutcome({ kind: "ok", detail: payload });
    });
  };

  return (
    <Screen title={t("proposal.title")} meta={t("proposal.meta")}>
      <section className="chain-form" data-proposal-fork="true">
        <p className="chain-form__label">{t("proposal.audience.label")}</p>
        <div className="chain-form__choices" data-audience-choices="true">
          {(["human_reader", "ai_executor"] as const).map((value) => (
            <label key={value} className="chain-form__choice">
              <input
                type="radio"
                name="audience"
                data-audience={value}
                checked={audience === value}
                onChange={() => setAudience(value)}
              />
              <span className="chain-form__choice-name">
                {t(`proposal.audience.${value}`)}
              </span>
              {/* `AUD-PACK-01`：v4 那两句说明**逐字**照抄进词典再显示。
                  选之前看不到两条路各产出什么，「必须选一个」就成了一次盲选——
                  而这两条路产出的东西完全不同（散文 vs 执行包）。 */}
              <span className="chain-form__choice-blurb" data-audience-blurb={value}>
                {t(`proposal.audience.${value}.blurb`)}
              </span>
            </label>
          ))}
        </div>

        {audience === "ai_executor" ? (
          // 不给选：后端锁死 vibe_pack。**说出来**，而不是灰掉五个选项。
          <p className="chain-form__outcome" data-template-locked={AI_TEMPLATE}>
            {t("proposal.template.locked", { template: AI_TEMPLATE })}
          </p>
        ) : (
          <>
            <label className="chain-form__label" htmlFor="proposal-template">
              {t("proposal.template.label")}
            </label>
            <select
              id="proposal-template"
              className="chain-form__input"
              data-testid="proposal-template"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
            >
              {HUMAN_TEMPLATES.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </>
        )}

        <label className="chain-form__label" htmlFor="proposal-report">
          {t("proposal.report.label")}
        </label>
        <input
          id="proposal-report"
          className="chain-form__input"
          data-testid="proposal-report"
          value={reportId}
          onChange={(e) => setReportId(e.target.value)}
        />

        <div className="chain-form__actions">
          <button
            type="button"
            className="chain-form__submit"
            data-testid="proposal-submit"
            // 受众没选就点不动——**它没有默认值**（服务端的原话）。
            disabled={audience === null || reportId.trim() === ""}
            onClick={submit}
          >
            {/* v4：未选时按钮上印「选择受众后才能提交」，选定后随受众换文案。
                **禁用而不说为什么**的按钮，用户只会反复点它。
                （v4 那句人类侧原文带「→ 设计台」——那是它自己那一屏的名字；
                本仓对应的屏 `WB-07` 刚改名叫「模板工具」，照抄会指向一个
                本仓不存在的名字，所以只抄语义那一半，**这一处偏离写进 trace**。） */}
            {audience === null
              ? t("proposal.submit.unpicked")
              : t(`proposal.submit.${audience}`)}
          </button>
        </div>

        {outcome ? (
          <p
            className="chain-form__outcome"
            data-testid="proposal-outcome"
            data-outcome-kind={outcome.kind}
            role="status"
          >
            {outcome.kind === "ok"
              ? t("chain.submitted")
              : outcome.kind === "failed"
                ? outcome.message || t("chain.failed", { status: String(outcome.status) })
                : t("chain.not_provided")}
          </p>
        ) : null}
      </section>
    </Screen>
  );
}
