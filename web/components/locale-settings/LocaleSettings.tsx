import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/**
 * UI-07 / v2 屏 2.13：语言与地区设置。
 *
 * ## 两轴正交（`PRINCIPLES#A3`）
 *
 * 「切地区 NEVER 改语言，切语言 NEVER 改热点集合」。所以本组件的
 * `onChange` **一次只交出一根轴**——把两值打包成一个对象交出去的那天，
 * 调用方就会顺手把另一根也写回去（BE-07 那侧 `set_prefs` 的
 * 「只改传进来的那一项」是同一条纪律的后端形态）。
 *
 * ## 无 profile 时显示声明过的默认值，NEVER 猜
 *
 * v2 2.13 原话：「未登录/无 profile → 显示默认值（zh / CN）并标『未保存』，
 * **NEVER 用浏览器 `Accept-Language` 推地区**」。
 *
 * 浏览器语言推地区是**双重猜测**：先从语言猜国家，再把猜出来的国家当成他要看的
 * 热点集合。猜错时用户看到的是另一个国家的热点，而他从没选过。
 * 所以本组件里**一处 `navigator` 都没有**（判据钉着）。
 *
 * ## 保存失败 NEVER 回滚成旧值
 *
 * v2 原话：「保存失败 → 保留用户选择并显示错误，NEVER 回滚成旧值假装成功」。
 * 回滚之后屏上是旧值、没有报错，用户会以为自己没点到——他会再点一次，
 * 然后再失败一次。
 *
 * ## 地区清单只有一份（LOC-01 落地）
 *
 * 真相的源头是 `contracts_v04.Region`，`GET /settings/locale` 的 `options.region`
 * 就是它。本组件**既不抄一份、也不再从别的组件借一份**——由页面从响应里传进来。
 *
 * `regions` 为 `null` 或空 = **没查到**：显示未提供态，
 * NEVER 渲染一个空 `<select>`（空下拉读起来是「没有可选地区」，那是一句结论），
 * 更 NEVER 悄悄退回一份硬编码副本（那是把「端点挂了」显示成「一切正常」）。
 */

export const LANGS = ["zh", "en"] as const;

export type LocaleDraft = { lang: string; region: string };

export type LocaleSettingsProps = {
  /** 服务端存着的那份；`null` = 没查过 / 无 profile。 */
  saved: LocaleDraft | null;
  /** 可选地区清单：来自 `GET /settings/locale` 的 `options.region`。
   *  `null` 或空 = 没查到 → 显示未提供态。 */
  regions: readonly string[] | null;
  /** 用户当前选择。保存失败时**不回滚**成 `saved`。 */
  draft: LocaleDraft;
  status: "idle" | "saving" | "error";
  error?: string | null;
  /** 一次只交出一根轴（A3 正交）。 */
  onChange?: (axis: "lang" | "region", value: string) => void;
  onSave?: () => void;
};

export function LocaleSettings({
  saved,
  regions,
  draft,
  status,
  error = null,
  onChange,
  onSave,
}: LocaleSettingsProps): JSX.Element {
  const saving = status === "saving";

  return (
    <section className="locale" data-locale-saved={saved === null ? "none" : "stored"}>
      <label className="locale__field">
        <span className="locale__label">{t("locale.lang")}</span>
        <select
          className="locale__select"
          data-locale-axis="lang"
          value={draft.lang}
          disabled={saving}
          onChange={(e) => onChange?.("lang", e.target.value)}
        >
          {LANGS.map((code) => (
            <option key={code} value={code}>{t(`locale.lang.${code}`)}</option>
          ))}
        </select>
      </label>

      <label className="locale__field">
        <span className="locale__label">{t("locale.region")}</span>
        {regions === null || regions.length === 0 ? (
          <p className="locale__select" data-locale-axis="region"
            data-screen-state="not_provided">
            {t("shell.not_provided")}
          </p>
        ) : (
          <select
            className="locale__select"
            data-locale-axis="region"
            value={draft.region}
            disabled={saving}
            onChange={(e) => onChange?.("region", e.target.value)}
          >
            {regions.map((code) => (
              <option key={code} value={code}>{code}</option>
            ))}
          </select>
        )}
      </label>

      {saved === null ? (
        // 没存过：显示的是**声明过的默认值**，不是猜出来的。说清楚它还没保存。
        <p className="locale__unsaved" data-locale-unsaved="true">
          {t("locale.unsaved")}
        </p>
      ) : null}

      <button type="button" className="locale__save" disabled={saving} onClick={onSave}>
        {saving ? t("locale.saving") : t("locale.save")}
      </button>

      {status === "error" ? (
        // 保留用户选择 + 说清楚失败了。NEVER 回滚成旧值假装成功。
        <p className="locale__error" data-locale-error="true">
          {error ?? t("locale.save_failed")}
        </p>
      ) : null}
    </section>
  );
}
