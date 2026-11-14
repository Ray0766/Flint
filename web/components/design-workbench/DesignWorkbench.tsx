"use client";

import type { JSX } from "react";

import { DsStatusMark } from "../shell/DsStatusMark";
import { NotProvided } from "../shell/NotProvided";
import type { ActionOutcome } from "../plaza/cardActions";
import { t } from "../../lib/i18n/t";

/**
 * UI-04 / v2 屏 2.17：AI 设计工作台的**装配层**。
 *
 * DESIGN 组 33 卡把探索渲染、固化管道、模板注册表、导出闸门都做好了
 * （BE-10 又把它们暴露成了端点），但**至今没有一块界面**。本组件只做装配与如实呈现。
 *
 * ## 三处「不知道」与「知道是坏的」分开
 *
 * | 入参 | `null` 的意思 | 非 null 的意思 |
 * |---|---|---|
 * | `preview` | 还没生成过 / 端点读不到 | 有一份产物 |
 * | `registryAvailable` | 见下面那张四态表 | — |
 *
 * 这条在本屏尤其要紧：v2 2.17 写着「模板注册表不可用 → 固化与生产渲染阻断，
 * 按钮置灰并说明原因」。**没查过就把按钮置灰并说「注册表不可用」，是在替后端下结论**——
 * 而真相是我们没问过。没查过时按钮同样不可点，但说的是**另一句话**：接口未提供。
 *
 * ## 预览失败 NEVER 用上一次成功的顶替
 *
 * v2 2.17 原话。顶替之后，用户看到的是一张**上一版**的图，
 * 而他以为那是刚生成的这一版——他会照着那张图去固化。
 * 所以失败时显示的是**原始产物 + 错误本身**。
 *
 * ## 预览零构建
 *
 * `iframe srcdoc`（v2 原话）：不引任何构建链，产物是什么就渲染什么。
 * `sandbox` 关掉脚本——预览的是**设计**，不是让它在我们的页面里执行。
 *
 * ## DESIGN-02 补的两件（改前这一屏共 108 行，两件一件都没有）
 *
 * 1. **自然语言输入区**：一个 textarea + 一个提交键。提交**真发请求**——
 *    「能不能提交」的真相在服务端，前端自己判会与后端各自漂移（详见 `designSession.ts`）。
 * 2. **生成中的流式区**：逐块出现。拼接**不在这里做**，在 `jobClient` 的 `designText` 里——
 *    两处拼法会在某个边界上分叉（丢块、重块都看不出来）。本组件只负责显示。
 *
 * 三件都在真浏览器里量宽高：源码层判得出「有没有」，判不出「是不是 0 像素」
 * ——`F-09` 那个空 span 正是「DOM 里有、用户看不见」。
 */

export type DesignPreview = {
  /** 产物本体（HTML 文本）。 */
  html: string;
  /** 渲染失败时的错误原文；`null` = 这次预览没出错。 */
  error: string | null;
};

/**
 * 模板注册表的四态（`DESIGN-03` 从 `boolean | null` 扩来的）。
 *
 * | 值 | 说的是 | 屏上 | 固化 |
 * |---|---|---|---|
 * | `not_checked` | **还没查过** | 「还没查过模板注册表」 | 阻断 |
 * | `not_provided` | 查过了：**这套部署根本没有 templates 表** | 「接口未提供」 | 阻断 |
 * | `down` | 查过了：**坏了** | 「注册表不可用」 | 阻断 |
 * | `ok` | 查过了：可用 | — | 放开 |
 *
 * **三态版把第四种塞进任一已有值都是谎**（`docs/blocked/
 * UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md` 逐条列过）：
 *
 * - 塞进 `down` → 屏上写「不可用，请稍后重试」，而真相是**重试一万次也不会有**；
 * - 塞进 `not_checked` → 我们明明查过了，那是另一个方向的谎；
 * - 写死一句「接口未提供」→ 话碰巧是对的，但后端哪天真上了 templates 表，这一屏不会知道。
 *
 * 四态里**只有 `ok` 放开固化**。其余三种都阻断，但**各说各的话**——
 * 长得一样的三种阻断等于没分开。
 */
export type RegistryState = "not_checked" | "not_provided" | "down" | "ok";

export type DesignWorkbenchProps = {
  /** `null` = 还没有产物（端点未接通 / 还没生成过）。 */
  preview: DesignPreview | null;
  /** 模板注册表的四态，见上面那张表。 */
  registryAvailable: RegistryState;
  onSolidify?: () => void;
  /** 输入框里的那句话。受控——草稿归调用方，本组件不自己记一份。 */
  prompt?: string;
  onPromptChange?: (next: string) => void;
  onGenerate?: () => void;
  /** 正在生成。`true` 时提交键不可点——重复提交会开出第二个作业。 */
  generating?: boolean;
  /** 已经逐块拼起来的文字（`jobClient` 的 `designText`）。空串 = 还没有块。 */
  streamText?: string;
  /** 上一次提交的答复。`null` = 还没提过——**不是**「提了没反应」。 */
  submitOutcome?: ActionOutcome | null;
};

function outcomeLine(outcome: ActionOutcome): string {
  if (outcome.kind === "not_provided") return t("design.submit.not_provided");
  if (outcome.kind === "unsupported") {
    return t("card.action.unsupported", { allowed: outcome.allowed.join(" / ") });
  }
  if (outcome.kind === "failed") {
    // 后端自己的说明原样带出来；没给说明就只报状态码，NEVER 编一句。
    return outcome.message || t("card.action.failed", { status: String(outcome.status) });
  }
  return t("design.submit.queued");
}

export function DesignWorkbench({
  preview,
  registryAvailable,
  onSolidify,
  prompt = "",
  onPromptChange,
  onGenerate,
  generating = false,
  streamText = "",
  submitOutcome = null,
}: DesignWorkbenchProps): JSX.Element {
  // **只有 `ok` 放开**。其余三种都阻断，而三种阻断各说各的话。
  const solidifyBlocked = registryAvailable !== "ok";
  const blockedReason = {
    not_checked: t("design.solidify.not_checked"),
    not_provided: t("design.solidify.not_provided"),
    down: t("design.solidify.registry_down"),
    ok: "",
  }[registryAvailable];

  return (
    <section className="design" data-design-state={preview === null ? "no_artifact" : "artifact"}>
      {/* ── 一、自然语言输入区 ───────────────────────────────── */}
      <div className="design__compose" data-design-compose="true">
        <label className="design__label" htmlFor="design-prompt">
          {t("design.prompt.label")}
        </label>
        <textarea
          id="design-prompt"
          className="design__prompt"
          data-testid="design-prompt"
          rows={3}
          value={prompt}
          placeholder={t("design.prompt.placeholder")}
          onChange={(e) => onPromptChange?.(e.target.value)}
        />
        <div className="design__compose-actions">
          <button
            type="button"
            className="design__generate"
            data-testid="design-generate"
            // 空提示不可提交：一句话都没有的生成只会让模型自由发挥，
            // 而产出的东西没有任何人要求过（与作业消费者那边的判断同一句）。
            disabled={generating || prompt.trim() === ""}
            onClick={onGenerate}
          >
            {t("design.generate.label")}
          </button>
          {generating ? (
            <DsStatusMark status="review" label={t("design.generate.running")} />
          ) : null}
        </div>
        {submitOutcome ? (
          <p
            className="design__submit-outcome"
            data-testid="design-submit-outcome"
            data-outcome-kind={submitOutcome.kind}
            role="status"
          >
            {outcomeLine(submitOutcome)}
          </p>
        ) : null}
      </div>

      {/* ── 二、生成中的流式区（逐块出现） ─────────────────────── */}
      <div
        className="design__stream"
        data-testid="design-stream"
        data-design-stream={streamText === "" ? "empty" : "streaming"}
        aria-live="polite"
      >
        {streamText === "" ? (
          // 「还没有块」不是「生成失败」，也不是「产物是空的」——如实说这一句。
          <p className="design__stream-empty">{t("design.stream.empty")}</p>
        ) : (
          <pre className="design__stream-text">{streamText}</pre>
        )}
      </div>

      {/* ── 三、iframe.srcdoc 零构建预览区 ─────────────────────── */}
      <div className="design__preview" data-design-preview="true">
        {preview === null ? (
          <NotProvided label={t("design.preview.not_provided")} />
        ) : preview.error !== null ? (
          // 失败时给**原始产物 + 错误本身**。NEVER 拿上一次成功的预览顶替：
          // 顶替之后用户看到的是上一版，而他以为那是刚生成的这一版。
          <div className="design__failed" data-design-preview-failed="true">
            <p className="design__error">{t("design.preview.failed")}</p>
            <pre className="design__raw">{preview.html}</pre>
            <pre className="design__error-detail">{preview.error}</pre>
          </div>
        ) : (
          // 零构建预览：产物是什么就渲染什么；脚本关掉——预览的是设计，不是让它执行。
          <iframe
            className="design__frame"
            title={t("design.preview.title")}
            sandbox=""
            srcDoc={preview.html}
          />
        )}
      </div>

      <div className="design__actions">
        <button
          type="button"
          className="design__solidify"
          disabled={solidifyBlocked}
          onClick={onSolidify}
        >
          {t("design.solidify.label")}
        </button>
        {solidifyBlocked ? (
          // E6：阻断要**说明原因**（v2 2.17 原话「按钮置灰并说明原因」）。
          // 两种阻断说的是两句不同的话——见组件 docstring 那张表。
          // 判别位就是那四态本身：取证认原值，人看那句话。
          // 共用一个判别位的话，三种阻断在取证里长得一模一样。
          <p className="design__blocked-reason" data-design-blocked={registryAvailable}>
            {blockedReason}
          </p>
        ) : null}
      </div>

      <p className="design__explore-note">{t("design.explore.still_open")}</p>
    </section>
  );
}
