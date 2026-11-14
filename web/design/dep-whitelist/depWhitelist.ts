// DESIGN-20：样板依赖白名单（G26，越界剥除 + 报错）。
//
// 样板是**模型生成**的，它见过无数带 CDN 引用的示例，于是很自然地写出
// `<script src="https://cdn.../chart.js">`。那一行的后果不是「多了个依赖」——
// 它让产物在客户机器上**向第三方发请求**：网络不通时页面塌掉、内容被对方看见、
// 而且哪天那个 CDN 改版，早已交付的文件会自己变样。
//
// **剥完必须报**：静默剥除会让作者以为图表功能好好的，直到客户打开一个空白框。
// 剥 + 说清楚剥了什么 + 给一句「换成什么」，他才改得动。
//
// **内联 script 不动**：它不向外发请求；剥了反而毁掉页面自己的逻辑。
// 白名单管的是「向谁要东西」，不是「有没有脚本」。
//
// **协议相对 `//cdn…` 是最容易漏的一种写法**：看起来像路径，实际是外部来源。

import { t } from "../../lib/i18n/t";

/** 默认白名单：同源（以 `/` 开头的路径）与 `_ds` 自托管资产。 */
export const DEFAULT_ALLOWED_ORIGINS: readonly string[] = ["self", "/_ds/"];

export type RemovedDep = { kind: "script" | "link"; url: string };

export type StripResult = {
  html: string;
  removed: RemovedDep[];
  /** 剥了什么之后该怎么办——只说剥了等于把问题丢回给作者 */
  action: string;
};

function isAllowed(url: string, allowed: readonly string[]): boolean {
  const external =
    url.startsWith("//") ||
    /^[a-z][a-z0-9+.-]*:/i.test(url);          // http: https: data: blob: …
  if (!external) {
    // 同源路径：白名单里含 "self" 即放行；另可按前缀细分（如只放 /_ds/）
    if (allowed.includes("self")) return true;
    return allowed.some((prefix) => prefix !== "self" && url.startsWith(prefix));
  }
  return allowed.some((prefix) => prefix !== "self" && url.startsWith(prefix));
}

const SCRIPT_SRC = /<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*>\s*<\/script>/gi;
const LINK_HREF = /<link\b[^>]*\bhref=["']([^"']+)["'][^>]*>/gi;

export function stripDisallowedDeps(
  html: string,
  allowed: readonly string[] = DEFAULT_ALLOWED_ORIGINS,
): StripResult {
  const removed: RemovedDep[] = [];

  const withoutScripts = html.replace(SCRIPT_SRC, (tag, url: string) => {
    if (isAllowed(url, allowed)) return tag;
    removed.push({ kind: "script", url });
    return "";
  });
  const cleaned = withoutScripts.replace(LINK_HREF, (tag, url: string) => {
    if (isAllowed(url, allowed)) return tag;
    removed.push({ kind: "link", url });
    return "";
  });

  return {
    html: cleaned.replace(/^\s*\n/gm, ""),      // 剥掉标签后留下的空行一并收拾
    removed,
    action: t("design.dep.action"),
  };
}
