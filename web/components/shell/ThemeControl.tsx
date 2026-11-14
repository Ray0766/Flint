"use client";

import { useEffect, useState, type JSX } from "react";

import { t } from "../../lib/i18n/t";
import { useScreenData } from "../../lib/useScreenData";
import { putLocaleAxis, type LocaleResponse } from "./localeClient";
import { THEME_COOKIE, applyTheme, rememberThemeHint } from "./themeFirstPaint";

/**
 * SHELL-02 / `DEC-047` / `DEC-050`：右上角的白天/夜间切换。
 *
 * ## 三态，而「跟随系统」是**显式**的那一个
 *
 * `跟随系统 / 白天 / 夜间`。**两态会把「我没选过」和「我选了白天」混成一个**——
 * 前者在系统切暗时该跟着变暗，后者 NEVER 变。合并之后这两种人只能有一种被满足，
 * 而**屏上看不出自己是哪一种**。
 *
 * ## 板早就建好了，缺的一直是控件
 *
 * `DARK-01` 建了暗色板与**双通道**：`prefers-color-scheme`（跟随系统）与
 * `[data-theme]`（手动切），而且 `[data-theme]` 写在 media 块**之后**——
 * 所以显式选择压得过系统偏好。本组件只做一件事：**把 `data-theme` 放上去或拿下来**。
 *
 * | 选择 | `<html data-theme>` | 谁在决定颜色 |
 * |---|---|---|
 * | 跟随系统 | **不设**（属性移除） | `prefers-color-scheme` |
 * | 白天 | `light` | `[data-theme="light"]` |
 * | 夜间 | `dark` | `[data-theme="dark"]` |
 *
 * 「跟随系统」**必须是移除属性而不是写一个值**：写 `data-theme="system"` 的话，
 * 那两条 CSS 规则一条都不匹配——看起来像亮色，而系统切暗时它不会变。
 *
 * ## 存得住：`prefs.theme`（`DEC-050`）
 *
 * 与语言/地区同一条路（`PUT /settings/locale`，一次只发一根轴）。
 * **服务端是真相**；下面那个 cookie 只是首帧用的提示，不是第二个真相（见
 * `themeFirstPaint.ts` 的文件头）。
 */

type Status = "idle" | "saving" | "error";

/** 三态。顺序即屏上顺序：**「跟随系统」排第一**，它是默认。 */
export const THEMES = ["system", "light", "dark"] as const;

export function ThemeControl(): JSX.Element {
  const { state, refetch } = useScreenData<LocaleResponse>("/settings/locale");
  const [status, setStatus] = useState<Status>("idle");

  const serverTheme = state.kind === "ready" ? (state.data.theme ?? "system") : null;

  useEffect(() => {
    // 服务端那份一到手就**对齐 DOM 与 cookie**。
    // 首帧靠 cookie 提示，这一步是**服务端把它纠正回来**——两者不一致时服务端赢。
    if (serverTheme === null) return;
    applyTheme(serverTheme);
    rememberThemeHint(serverTheme);
  }, [serverTheme]);

  if (state.kind !== "ready") {
    return (
      <div
        className="app-shell__theme"
        data-testid="shell-theme"
        data-screen-state={state.kind}
      >
        <span>{t("shell.not_provided")}</span>
      </div>
    );
  }

  const write = (next: string): void => {
    setStatus("saving");
    // 先把屏改过来：主题是**看得见的即时反馈**，等一个来回再变会让人以为没点上。
    // 服务端拒绝时下面 `catch` 里改回服务端那份——**NEVER 让屏与库长期不一致**。
    applyTheme(next);
    rememberThemeHint(next);
    void putLocaleAxis("theme", next)
      .then(() => {
        setStatus("idle");
        refetch();
      })
      .catch(() => {
        setStatus("error");
        applyTheme(state.data.theme ?? "system");
        rememberThemeHint(state.data.theme ?? "system");
      });
  };

  return (
    <div
      className="app-shell__theme"
      data-testid="shell-theme"
      data-screen-state="ready"
      data-theme-status={status}
      data-theme-choice={state.data.theme ?? "system"}
    >
      <label className="app-shell__theme-label" data-testid="shell-theme-label">
        <span>{t("theme.label")}</span>
        <select
          data-testid="shell-theme-select"
          data-locale-axis="theme"
          value={state.data.theme ?? "system"}
          disabled={status === "saving"}
          onChange={(e) => write(e.target.value)}
        >
          {THEMES.map((code) => (
            <option key={code} value={code}>{t(`theme.${code}`)}</option>
          ))}
        </select>
      </label>
      {status === "error" ? (
        <span data-theme-error="true">{t("locale.save_failed")}</span>
      ) : null}
      {/* cookie 名字露在 DOM 上，判据据此确认首帧那一段读的是同一个名字——
          两处各写一个名字的话，首帧永远读不到刚存下的选择，而屏上一切正常。 */}
      <span hidden data-theme-cookie={THEME_COOKIE} />
    </div>
  );
}
