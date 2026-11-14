// I18N-06-b 验收：前端 store 无 localStorage 读写（源码断言）+ 服务端为真相。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_PREFS,
  __resetPrefs,
  getPrefs,
  hydrateFromServer,
  savePrefs,
  subscribe,
} from "./prefs";

afterEach(() => __resetPrefs());

describe("prefs store", () => {
  it("源码里没有任何浏览器存储读写（acceptance 源码断言）", () => {
    const source = readFileSync(join(__dirname, "prefs.ts"), "utf8");
    // 注释里解释「NEVER 读写 localStorage」不算读写——只看**代码行**
    const code = source
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    for (const forbidden of ["localStorage", "sessionStorage", "document.cookie"]) {
      expect(code).not.toContain(forbidden);
    }
  });

  it("未拉取前是默认值，NEVER 是空", () => {
    expect(getPrefs()).toEqual(DEFAULT_PREFS);
    expect(getPrefs().lang).toBe("zh");
  });

  it("服务端回值即真相", () => {
    hydrateFromServer({ lang: "en", region: "JP" });
    expect(getPrefs()).toEqual({ lang: "en", region: "JP" });
  });

  it("保存走「先写服务端、回什么是什么」，NEVER 乐观更新", async () => {
    const put = vi.fn(async () => ({ lang: "en", region: "US" }) as const);
    const promise = savePrefs({ lang: "en" }, put);
    // 请求未回时缓存**不该**已经变了
    expect(getPrefs().lang).toBe("zh");
    await promise;
    expect(getPrefs()).toEqual({ lang: "en", region: "US" });
  });

  it("服务端拒绝时缓存保持原样（不留「界面变了、服务端没变」）", async () => {
    const put = vi.fn(async () => {
      throw new Error("422");
    });
    await expect(savePrefs({ lang: "en" }, put)).rejects.toThrow("422");
    expect(getPrefs()).toEqual(DEFAULT_PREFS);
  });

  it("订阅者收到服务端刷新", () => {
    const seen: string[] = [];
    subscribe((p) => seen.push(p.lang));
    hydrateFromServer({ lang: "en", region: "GB" });
    expect(seen).toEqual(["en"]);
  });
});
