#!/usr/bin/env node
// DESIGN-05：`_ds` 资产扫描器（两处已知问题的机器判据）。
//
// 用法：
//   node tools/scan_ds_assets.mjs web/public/_ds --tabular-nums --no-warn-emoji
//   node tools/scan_ds_assets.mjs web/public/_ds            # 只报告不失败
//
// ## 检查一：数字容器必须 tabular-nums（--tabular-nums）
//
// 等宽数字不是排版洁癖：一列数字若各位宽度不一，上下行的小数点对不齐，
// 读者要逐个字符去比大小。判据只针对**数字容器**——mono 也常用作标签字体
// （表头、按钮、说明），给标签加 tabular-nums 没有意义，把它们也算违规
// 会让这把尺子每次都报一堆无关项，然后没人再看它。
//
// 「数字容器」= 用了 mono 字体，且上下文出现数值语义的名字
// （count/value/num/total/qty/amount/score/price/seq/version/delta/percent）。
//
// ## 检查二：⚠ 之类的字符 NEVER 当图标（--no-warn-emoji）
//
// `_ds` 的识别物是几何印记（实心方/空心方/三角/斜纹方），由组件内联渲染。
// 用 ⚠ 当图标有三个问题：各平台字形不同、颜色不受 token 控制、读屏会把它读成
// 「警告标志」而不是这套系统里的语义。
//
// 代码文件（.js/.jsx/.css/.html）里出现即违规；文档（.md）里出现单独列出——
// 文档里描述这套记号是正当的，但**描述必须与代码一致**，所以照样报出来给人看。

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const CODE_EXT = [".js", ".jsx", ".mjs", ".css", ".html"];
const DOC_EXT = [".md"];
// 当图标用的字符：⚠ ⚡ ❗ ✅ ❌ 🔺 ⛔ ℹ
const ICON_CHARS = /[⚠⚡❗✅❌🔺⛔ℹ]/g;
const MONO = /fontFamily:\s*[^,}\n]*(--font-mono|monospace)|font-family:[^;}\n]*(--font-mono|monospace)/gi;
const TABULAR = /tabular-nums/;
const NUM_HINT =
  /\b(count|value|num|total|qty|amount|score|price|seq|version|delta|percent)\b/i;
const CONTEXT = 400;

// 跳过 vendor 与构建产物，口径与另外三把扫描器逐字一致
// （`i18n_scan.mjs` / `lint_no_confidence_viz.mjs` / `no_external_fonts.mjs`）。
// 按**目录名**跳，NEVER 按路径子串跳：`includes("node_modules")` 会把
// `my_node_modules_notes/` 这种用户自己的目录一起跳掉，而漏扫是静默的——
// 报告上写着「扫描 N 个文件」，少的那些一个字都不会提。
//
// 跳在递归里而不是读完再筛：读完再筛的话 node_modules 底下几万个文件照样被
// statSync + readFileSync 走一遍，功能上看不出差别，扫一次 web 却要多花几十秒。
function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

function lineOf(text, index) {
  return text.slice(0, index).split("\n").length;
}

function scanTabular(file, text) {
  const hits = [];
  for (const m of text.matchAll(MONO)) {
    const i = m.index ?? 0;
    const after = text.slice(i, i + CONTEXT);
    const around = text.slice(Math.max(0, i - CONTEXT), i + CONTEXT);
    if (TABULAR.test(after)) continue;          // 已经有了
    if (!NUM_HINT.test(around)) continue;       // 标签用途，不是数字容器
    hits.push({ file, line: lineOf(text, i) });
  }
  return hits;
}

function scanIconChars(file, text) {
  const hits = [];
  for (const m of text.matchAll(ICON_CHARS)) {
    const i = m.index ?? 0;
    hits.push({ file, line: lineOf(text, i), char: m[0] });
  }
  return hits;
}

const [, , target, ...flags] = process.argv;
if (!target) {
  console.error(
    "用法：node tools/scan_ds_assets.mjs <_ds 目录> [--tabular-nums] [--no-warn-emoji]",
  );
  process.exit(2);
}
const failOnTabular = flags.includes("--tabular-nums");
const failOnIcons = flags.includes("--no-warn-emoji");

const files = walk(target);
const tabularHits = [];
const codeIconHits = [];
const docIconHits = [];
let numClassSeen = false;

for (const file of files) {
  const rel = relative(target, file).split(sep).join("/");
  const isCode = CODE_EXT.some((e) => file.endsWith(e));
  const isDoc = DOC_EXT.some((e) => file.endsWith(e));
  if (!isCode && !isDoc) continue;
  const text = readFileSync(file, "utf8");

  if (isCode) {
    tabularHits.push(...scanTabular(rel, text));
    codeIconHits.push(...scanIconChars(rel, text));
    if (/\.num\b[^{]*\{[^}]*tabular-nums/.test(text)) numClassSeen = true;
  } else {
    docIconHits.push(...scanIconChars(rel, text));
  }
}

console.log(`扫描 ${files.length} 个文件（${target}）`);
console.log(`  数字容器缺 tabular-nums：${tabularHits.length} 处`);
console.log(`  .num 类带 tabular-nums：${numClassSeen ? "在" : "缺失"}`);
console.log(`  代码里的图标字符：${codeIconHits.length} 处`);
console.log(`  文档里的图标字符：${docIconHits.length} 处`);
for (const h of [...tabularHits]) console.log(`  ✗ ${h.file}:${h.line} 数字容器缺 tabular-nums`);
for (const h of [...codeIconHits, ...docIconHits]) {
  console.log(`  ✗ ${h.file}:${h.line} 图标字符 ${h.char}`);
}

let failed = false;
if (failOnTabular && (tabularHits.length > 0 || !numClassSeen)) failed = true;
if (failOnIcons && codeIconHits.length + docIconHits.length > 0) failed = true;
process.exit(failed ? 1 : 0);
