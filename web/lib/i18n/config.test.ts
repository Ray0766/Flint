// I18N-01 验收：locale 基建（zh 默认、en 可切、未登录回落 zh）。
import { describe, expect, it } from "vitest";

import { DEFAULT_LOCALE, LOCALES, isLocale, resolveLocale } from "./config";

describe("locale 基建", () => {
  it("语言集恰是 zh/en（A3：语言与地区正交，地区不在此列）", () => {
    expect([...LOCALES]).toEqual(["zh", "en"]);
    expect(DEFAULT_LOCALE).toBe("zh");
  });

  it("en 可切", () => {
    expect(resolveLocale("en")).toBe("en");
  });

  it("未登录 / 无 profile → 回落 zh", () => {
    expect(resolveLocale(undefined)).toBe("zh");
    expect(resolveLocale(null)).toBe("zh");
    expect(resolveLocale("")).toBe("zh");
  });

  it("非法 locale 回落 zh，NEVER 抛错让整页白屏", () => {
    expect(resolveLocale("ja")).toBe("zh");
    expect(resolveLocale("zh-CN")).toBe("zh");
  });

  it("地区码 NEVER 被当成语言（A3 反例：用 Accept-Language 推地区）", () => {
    expect(isLocale("JP")).toBe(false);
    expect(resolveLocale("JP")).toBe("zh");
  });

  it("两份 messages 都能加载且键集一致", async () => {
    const zh = (await import("../../messages/zh.json")).default as Record<string, string>;
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    expect(Object.keys(zh).sort()).toEqual(Object.keys(en).sort());
    expect(zh["app.name"]).toBeTruthy();
  });
});
