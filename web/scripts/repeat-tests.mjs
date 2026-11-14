#!/usr/bin/env node
// FIX-08：连跑前端单测并**把失败用例名留下来**。
//
// ## 它治的病
//
// `docs/blocked/ONE-UNNAMED-FRONTEND-RED-NOT-CAPTURED.md`：
// 一次 `npm test -- --run` 红了，而当时的命令**只 grep 了汇总行**，
// 把用例名过滤掉了。于是那次红只剩下「1 failed」四个字——
// 不知道是哪个文件、哪条用例，也就无从判断它与 `FIX-04` 修掉的那处是不是同一个。
//
// **现场丢了就再也找不回来**：间歇红下一次出现可能是几十跑之后。
// 所以这件事要固化成脚本，NEVER 靠人每次现敲一条命令。
//
// ## 为什么必须连跑很多次
//
// `FIX-04` 那处是 **40 次里第 29 次**才复现的。
// 连跑 6 次全绿**不能证明它不存在**——那张单子自己写着这句话。
//
// 用法：
//     node web/scripts/repeat-tests.mjs [--runs 30] [--out .ui-probe/frontend-red.json]
//
// 退出码恒 0：**它是取证工具，不是判据**。
// 判据在 `tests/v041/test_frontend_red_capture.py`——
// 取证工具自己判红的话，「没复现」与「工具挂了」会长得一样。

import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(WEB, "..");

function arg(flag, fallback) {
  const at = process.argv.indexOf(flag);
  return at === -1 ? fallback : process.argv[at + 1];
}

const runs = Number(arg("--runs", "30"));
const out = resolve(REPO, arg("--out", ".ui-probe/frontend-red.json"));

/**
 * 从 vitest 的 verbose 输出里抽**失败用例名**。
 *
 * 抓两种形状，因为两种都出现过：
 *   `  × 用例名 12ms`            ← 行内失败标记
 *   ` FAIL  path > suite > 用例名` ← 汇总段
 *
 * **NEVER 只 grep 汇总行**——那正是这张单子的由来。
 */
function failedNames(text) {
  const names = new Set();
  for (const line of text.split(/\r?\n/)) {
    const inline = line.match(/^\s*×\s+(.+?)(?:\s+\d+ms)?\s*$/);
    if (inline) names.add(inline[1].trim());
    const summary = line.match(/^\s*FAIL\s+(.+?)\s*$/);
    if (summary) names.add(summary[1].trim());
  }
  return [...names];
}

const runsOut = [];
for (let i = 1; i <= runs; i += 1) {
  const started = process.hrtime.bigint();
  const done = spawnSync("npm", ["test", "--", "--run", "--reporter=verbose"], {
    cwd: WEB, encoding: "utf8", shell: true, maxBuffer: 64 * 1024 * 1024,
  });
  const text = `${done.stdout ?? ""}\n${done.stderr ?? ""}`;
  const names = failedNames(text);
  const ms = Number((process.hrtime.bigint() - started) / 1000000n);
  runsOut.push({
    run: i,
    exitCode: done.status,
    green: done.status === 0,
    failed: names,
    // 汇总行也留一份：它是**给人核对的**那一条，与用例名互为佐证。
    summary: (text.match(/Tests\s+.*$/m) ?? [""])[0].trim(),
    ms,
  });
  const mark = done.status === 0 ? "绿" : `红 → ${names.join(" | ") || "（没抓到名字）"}`;
  process.stdout.write(`第 ${i}/${runs} 次：${mark}\n`);
}

const reds = runsOut.filter((r) => !r.green);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify({
  schema: "frontend-red/1",
  runs,
  greens: runs - reds.length,
  reds: reds.length,
  // **每一次红都带用例名**。名字为空 = 这个工具没抓住现场，那本身就是缺陷。
  names: [...new Set(reds.flatMap((r) => r.failed))],
  detail: runsOut,
}, null, 1), "utf8");

process.stdout.write(
  `\n连跑 ${runs} 次：绿 ${runs - reds.length} · 红 ${reds.length}\n` +
  (reds.length
    ? `失败用例名：${[...new Set(reds.flatMap((r) => r.failed))].join(" | ")}\n`
    : "**30 次未复现不等于它不存在**（FIX-04 那处是 40 次里第 29 次才复现的）。\n") +
  `产物：${out}\n`);
