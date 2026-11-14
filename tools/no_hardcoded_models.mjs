#!/usr/bin/env node
// DESIGN-17：硬编码模型名扫描器（G23）。
//
// 用法：node tools/no_hardcoded_models.mjs web
//
// ## 为什么模型名一个都不许写进代码
//
// 模型会换。写死在某个组件里的 `claude-3-5-sonnet`，换代那天要靠人去全仓找——
// 找漏一处，那一处就永远用着旧模型，而界面上看不出任何区别：它照样出结果，
// 只是比别处差一档，且账单也不一样。
//
// 列表与默认值都从**环境配置**来（`NEXT_PUBLIC_DESIGN_MODELS` 之类），
// 代码里只有「读配置」这一件事。
//
// ## 判据
//
// 命中形如 `claude-*` / `gpt-*` / `gemini-*` / `llama-*` 的**字符串字面量**。
// 注释与文档不算——那里写模型名通常正是在说明为什么不写进代码
// （与 i18n_scan 的注释口径一致）。
// 配置**键名**不算（`NEXT_PUBLIC_DESIGN_MODELS` 里没有型号）。
// 测试文件不算：测试要拿真实型号当样本，那正是它该干的事。

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { codeOnly } from "./_scan_lib.mjs";

const SOURCE_EXT = [".ts", ".tsx", ".js", ".mjs"];
const TEST_MARKERS = [".test.", ".spec.", `${sep}__tests__${sep}`];
// 型号形态：厂商前缀 + 连字符 + 版本片段
const MODEL_PATTERN =
  /["'`](?:claude|gpt|gemini|llama|mistral|qwen|deepseek)-[a-z0-9][a-z0-9.-]*["'`]/gi;

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === "node_modules" || entry === ".next" || entry === "public") continue;
      out.push(...walk(full));
    } else if (SOURCE_EXT.some((e) => entry.endsWith(e))) {
      out.push(full);
    }
  }
  return out;
}

function isTestFile(path) {
  return TEST_MARKERS.some((m) => path.includes(m));
}

/** 剥注释后再扫：注释里写模型名通常正是在说明为什么不写进代码。 */
// 行注释：`//` 前不能是冒号，否则 `https://…` 会被当成注释起点（DESIGN-21 踩过）


const [, , target] = process.argv;
if (!target) {
  console.error("用法：node tools/no_hardcoded_models.mjs <目录>");
  process.exit(2);
}

const files = walk(target).filter((f) => !isTestFile(f));
const hits = [];
for (const file of files) {
  const rel = relative(target, file).split(sep).join("/");
  const code = codeOnly(readFileSync(file, "utf8"));
  code.split("\n").forEach((line, i) => {
    for (const m of line.matchAll(MODEL_PATTERN)) {
      hits.push({ rel, line: i + 1, text: m[0] });
    }
  });
}

console.log(`扫描 ${files.length} 个源文件（已排除测试文件与 public/）`);
console.log(`  硬编码模型名：${hits.length} 处`);
for (const h of hits) console.log(`  ✗ ${h.rel}:${h.line} ${h.text}`);
process.exit(hits.length > 0 ? 1 : 0);
