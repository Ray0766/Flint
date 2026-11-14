import type { JSX } from "react";

import { NotProvided } from "../shell/NotProvided";
import { t } from "../../lib/i18n/t";

/**
 * UI-06 / v2 屏 2.18：外链只读查看页。
 *
 * ## 「没这个链接」与「这个链接失效了」是两句话
 *
 * v2 2.18 原话：「token 失效/过期 → 明确区分『链接已过期』与『无此链接』，
 * **NEVER 一律报 404 含糊过去**」。后端那侧（`flint/share/links.py`）把理由写死了：
 *
 * > 全报 404 看起来「更安全」，实际是把三种完全不同的处境糊成一句「没有」，
 * > 让持链人无从判断下一步。
 *
 * 对持链人来说这决定他**下一步做什么**：
 *
 * | 后端 | 屏上 | 他该做什么 |
 * |---|---|---|
 * | 404 | 没有这个链接 | 检查自己是不是拿错了地址 |
 * | 410 | 曾经有效、现在不是 | 去找分享的人要一条新的 |
 * | 401 | 需要口令 | 输口令 |
 *
 * ## 410 里的「过期」与「撤销」分不出来时 NEVER 猜一个
 *
 * 后端两种都回 410（`resolve_share`），只有错误文案不同。
 * 拿不到理由时屏上说的是**中性那句**（「曾经有效、现在不是」）——
 * 说成「已过期」而其实是被撤销的，持链人会去等一个永远不会来的续期。
 *
 * ## 只读：干预控件**不渲染**
 *
 * v2 2.18 原话「只读：不显示任何干预控件」。与保护块同一条纪律：
 * 置灰仍然告诉用户「这里本来能点」，而在外链上它永远不能点。
 */

export type ShareOutcome =
  /** 端点未接通：**没查过**，不是「没有这个链接」。 */
  | { kind: "not_provided" }
  /** 404：这个 token 不存在。 */
  | { kind: "unknown" }
  /** 410：曾经有效、现在不是。`reason` 拿不到时 NEVER 猜。 */
  | { kind: "gone"; reason: "expired" | "revoked" | null }
  /** 401：要口令。 */
  | { kind: "password_required" }
  /** 200。 */
  | { kind: "ready"; title: string; body: string };

function goneLabel(reason: "expired" | "revoked" | null): string {
  if (reason === "expired") return t("share.gone.expired");
  if (reason === "revoked") return t("share.gone.revoked");
  return t("share.gone.unspecified");
}

export function ShareViewer({ outcome }: { outcome: ShareOutcome }): JSX.Element {
  if (outcome.kind === "not_provided") {
    return (
      <section className="share" data-share-state="not_provided">
        <NotProvided label={t("share.not_provided")} />
      </section>
    );
  }

  if (outcome.kind === "unknown") {
    return (
      <section className="share" data-share-state="unknown">
        <p className="share__message">{t("share.unknown")}</p>
      </section>
    );
  }

  if (outcome.kind === "gone") {
    return (
      <section className="share" data-share-state="gone" data-share-gone-reason={
        outcome.reason ?? "unspecified"
      }>
        <p className="share__message">{goneLabel(outcome.reason)}</p>
        <p className="share__hint">{t("share.gone.hint")}</p>
      </section>
    );
  }

  if (outcome.kind === "password_required") {
    return (
      <section className="share" data-share-state="password_required">
        <p className="share__message">{t("share.password_required")}</p>
      </section>
    );
  }

  return (
    <article className="share" data-share-state="ready">
      <h2 className="share__title">{outcome.title}</h2>
      <div className="share__body">{outcome.body}</div>
      {/* 只读：干预控件一个都不渲染（v2 2.18）。这里没有按钮，也不该有。 */}
      <p className="share__readonly-note">{t("share.readonly")}</p>
    </article>
  );
}
