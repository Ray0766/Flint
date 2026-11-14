// I18N-01：locale 基建（zh 默认、en 可切、未登录回落 zh）。
//
// PRINCIPLES#A3：语言与地区**正交**。本文件只管语言——
// NEVER 从 locale 推地区、NEVER 从 Accept-Language 推地区（那是 A3 反例第三条）。

import { getRequestConfig } from "next-intl/server";

export const LOCALES = ["zh", "en"] as const;
export type Locale = (typeof LOCALES)[number];

/** A1：zh 是默认语言。未登录、无 profile、locale 非法 —— 一律回落到它。 */
export const DEFAULT_LOCALE: Locale = "zh";

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && (LOCALES as readonly string[]).includes(value);
}

/**
 * 决定本次请求用哪个语言。
 *
 * 真相源是 **profile（服务端）**，不是浏览器（I18N-06：跨设备一致）。
 * 传进来的 profileLocale 为空/非法时回落 zh —— NEVER 去读 navigator.language 或
 * Accept-Language 头：那会让同一个账号在不同设备上看到不同语言。
 */
export function resolveLocale(profileLocale?: string | null): Locale {
  return isLocale(profileLocale) ? profileLocale : DEFAULT_LOCALE;
}

/** next-intl 的服务端配置入口。messages 由 I18N-02 落地（本卡只搭基建）。 */
export default getRequestConfig(async ({ locale }) => {
  const active = resolveLocale(locale);
  return {
    locale: active,
    messages: (await import(`../../messages/${active}.json`)).default,
  };
});
