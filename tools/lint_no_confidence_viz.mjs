#!/usr/bin/env node
// DESIGN-23：禁置信度可视化 + 图标纪律（G29/G30）。
//
// 用法：node tools/lint_no_confidence_viz.mjs web
//
// ## 为什么禁「置信度可视化」
//
// 一根 78% 的进度条画在一条结论旁边，读者会把它当成「这件事有 78% 的把握」——
// 而系统里**根本没有这个数**：Gate① 出的是 A/B/C/D 四分类，证据要么在要么不在。
// 那根条子是画上去的，它把一个不存在的精度感塞给了读者，而他会据此下注。
//
// 所以进度条只准绑两种东西：**`JobView.progress`（一次运行真的跑到哪了）**
// 与**骨架屏**（还没加载出来）。两者都是「进度」，不是「把握」。
//
// ## 为什么禁 emoji 当图标
//
// `_ds` 的识别物是几何印记（实心方=事实、空心方=价格、斜纹方=争议…），由组件内联渲染。
// 用 ⚠ 或 ✅ 当图标有三个问题：各平台字形不同、颜色不受 token 控制、
// 读屏会把它读成「警告标志」而不是这套系统里的语义。
//
// ## 判据
//
// 1. **置信度可视化**：`width`/`value`/`style` 上绑了 confidence/certainty/score/
//    probability/likelihood/relevance 这类名字的百分比表达；或出现
//    `confidence-bar` / `score-meter` 这类类名。
// 2. **emoji 当图标**：常见状态 emoji 出现在代码里（注释与测试文件不算）。
//
// 注释不算：注释里写「NEVER 用 ⚠ 当图标」正是在说明这条规则。

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { codeOnly } from "./_scan_lib.mjs";

const SOURCE_EXT = [".ts", ".tsx", ".js", ".mjs", ".css", ".html"];
const TEST_MARKERS = [".test.", ".spec.", `${sep}__tests__${sep}`];

// 允许绑进度条的两种来源
const ALLOWED_PROGRESS = /\b(progress|skeleton)\b/i;
// 「把握度」类名字
const CONFIDENCE_WORD =
  /\b(confidence|certainty|probability|likelihood|relevance|score)\b/i;
// 进度条/仪表类的表达位置
const VIZ_BINDING =
  /(width\s*[:=]|value\s*[:=]|aria-valuenow\s*[:=]|style\s*=\s*\{\{[^}]*width)/i;
const VIZ_CLASSNAME = /\b[\w-]*(?:confidence|score|certainty)[\w-]*(?:bar|meter|gauge)\b/i;
const ICON_EMOJI = /[⚠⚡❗✅❌🔺⛔ℹ🟢🔴🟡👍👎🚀🎯]/g;

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

const isTestFile = (p) => TEST_MARKERS.some((m) => p.includes(m));

// 剥注释；`//` 前不能是冒号，否则 URL 会被当成注释起点（DESIGN-21 踩过）
// 行注释：`//` 前不能是冒号，否则 `https://…` 会被当成注释起点（DESIGN-21 踩过）


const [, , target] = process.argv;
if (!target) {
  console.error("用法：node tools/lint_no_confidence_viz.mjs <目录>");
  process.exit(2);
}

const vizHits = [];
const iconHits = [];

for (const file of walk(target).filter((f) => !isTestFile(f))) {
  const rel = relative(target, file).split(sep).join("/");
  const code = codeOnly(readFileSync(file, "utf8"));
  code.split("\n").forEach((line, i) => {
    const confidenceViz =
      (CONFIDENCE_WORD.test(line) && VIZ_BINDING.test(line) &&
        !ALLOWED_PROGRESS.test(line)) || VIZ_CLASSNAME.test(line);
    if (confidenceViz) vizHits.push({ rel, line: i + 1, text: line.trim().slice(0, 72) });
    for (const m of line.matchAll(ICON_EMOJI)) {
      iconHits.push({ rel, line: i + 1, char: m[0] });
    }
  });
}

console.log(`扫描目录 ${target}（已排除测试文件）`);
console.log(`  置信度可视化：${vizHits.length} 处`);
console.log(`  emoji 当图标：${iconHits.length} 处`);
for (const h of vizHits) console.log(`  ✗ ${h.rel}:${h.line} ${h.text}`);
for (const h of iconHits) console.log(`  ✗ ${h.rel}:${h.line} ${h.char}`);
process.exit(vizHits.length + iconHits.length > 0 ? 1 : 0);
