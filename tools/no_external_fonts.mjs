#!/usr/bin/env node
// DESIGN-21：外部字体 URL 扫描器（G27，字体自托管）。
//
// 用法：node tools/no_external_fonts.mjs web
//
// ## 为什么字体必须自托管
//
// 一个 `@import url("https://fonts.googleapis.com/…")` 的后果不是「字体好看了」：
// 交付出去的文件会在**客户机器上**向第三方要东西——内网打不开、离线打不开、
// 对方能看见谁在什么时候读了这份文件；而哪天那个 CDN 改版，早已交付的文件会自己变样。
// 这与 DESIGN-20 的依赖白名单是同一条纪律：**产物不向外要东西**。
//
// ## 判据
//
// 扫 `.css` / `.ts` / `.tsx` / `.js` / `.html` 里指向外部来源的字体引用：
// `@import url(<外部>)`、`src: url(<外部>)`（@font-face）、以及 `<link>` 指向
// 已知字体 CDN 的写法。同源路径（`/` 开头）与 `data:` 内联字体不算——
// 前者是自托管，后者已经在文件里了。
//
// 注释不算：注释里写一句「原来这里挂的是 Google Fonts」正是在说明为什么不这么做。

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { codeOnly } from "./_scan_lib.mjs";

const SOURCE_EXT = [".css", ".ts", ".tsx", ".js", ".mjs", ".html"];
const FONT_CDN =
  /(fonts\.googleapis\.com|fonts\.gstatic\.com|use\.typekit\.net|fast\.fonts\.net|cdn\.jsdelivr\.net\/[^"')]*font|unpkg\.com\/[^"')]*font)/i;
const URL_IN_CSS = /(?:@import\s+url|src\s*:\s*url)\(\s*["']?([^"')]+)["']?\s*\)/gi;
const LINK_HREF = /<link\b[^>]*href=["']([^"']+)["']/gi;

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === "node_modules" || entry === ".next") continue;
      out.push(...walk(full));
    } else if (SOURCE_EXT.some((e) => entry.endsWith(e))) {
      out.push(full);
    }
  }
  return out;
}

// 剥注释：注释里提到外部字体通常正是在说明为什么不用它。
//
// `//` 前面要求不是冒号——否则 `https://fonts…` 会被当成行注释起点，整条 URL
// 被剥掉，扫描器于是报「0 处」而其实一处没看见。初版就是这么写的，第一次跑就
// 骗过了自己（见 docs/trace/DESIGN-21.md）。
// 行注释：`//` 前不能是冒号，否则 `https://…` 会被当成注释起点（DESIGN-21 踩过）


function isExternal(url) {
  if (url.startsWith("data:")) return false;      // 已经在文件里了
  if (url.startsWith("//")) return true;
  if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return true;
  return false;                                    // 同源路径 = 自托管
}

const [, , target] = process.argv;
if (!target) {
  console.error("用法：node tools/no_external_fonts.mjs <目录>");
  process.exit(2);
}

const hits = [];
for (const file of walk(target)) {
  const rel = relative(target, file).split(sep).join("/");
  const code = codeOnly(readFileSync(file, "utf8"));
  code.split("\n").forEach((line, i) => {
    for (const m of line.matchAll(URL_IN_CSS)) {
      if (isExternal(m[1])) hits.push({ rel, line: i + 1, url: m[1] });
    }
    for (const m of line.matchAll(LINK_HREF)) {
      if (isExternal(m[1]) && FONT_CDN.test(m[1])) {
        hits.push({ rel, line: i + 1, url: m[1] });
      }
    }
  });
}

console.log(`扫描目录 ${target}`);
console.log(`  外部字体 URL：${hits.length} 处`);
for (const h of hits) console.log(`  ✗ ${h.rel}:${h.line} ${h.url}`);
process.exit(hits.length > 0 ? 1 : 0);
