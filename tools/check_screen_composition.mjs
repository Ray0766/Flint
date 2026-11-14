#!/usr/bin/env node
// GAUGE-12：逐屏组件对照 —— 本仓**第一把正向尺子**。
//
// ## 为什么需要它
//
// 全仓此前的判据都是**禁止性**的：NEVER 空转、NEVER 空态冒充、NEVER 硬编码。
// 它们挡得住做错，**挡不住没做**。
//
// 广场屏那四条 `EYE-03` 判据（HTTP 200 · 零控制台报错 · 无横向溢出 · 两主题截图）
// **全绿**，而那一屏是个 `ul/li`、全文件零 `className`——它就是这么过去的。
// 一屏「什么都没做」在禁止性判据下永远是干净的：它没有错误可犯。
//
// ## 它判什么
//
// 声明在 `assets/screen_composition.json`，每屏两样：
//
//   components  MUST 被**真渲染**的选择器 —— 取渲染后的 DOM，**不是**「文件存在」；
//   styled      MUST 有样式的类名     —— 取计算样式，与裸元素基线逐条比，
//                                        **一样即零样式，判红**。
//
// 「文件存在」与「组件被渲染」是两件事：组件建好了而屏上没接，
// 正是本批要治的病（`TopicListView`/`ComboEntryView`/`BlockInterventionPanel`
// 三个组件都建好了、四张屏都没有）。
//
// ## 运行时观测从哪来
//
// 本脚本**不开浏览器**（node 侧没有 DOM）。它消费一份观测产物：
//
//     .ui-probe/screen_composition.json   ← 由 tests/v041/test_screen_composition.py
//                                            用 C:\pwenv 的 playwright 落下
//
// 分工与本仓既有的 `check_design_constraints.mjs`（静态）+ `ui_probe.py`（运行时）
// 是同一套：**判据在这里，眼睛在那里**。
//
// 用法：
//     node tools/check_screen_composition.mjs [--json]
//     node tools/check_screen_composition.mjs --declaration a.json --observed b.json
//
// 退出码：0 = 零违规；1 = 有违规；2 = 观测产物不在（**与「有违规」分开**——
// 修法完全不同：一个是去做界面，一个是去跑取证）。

import { readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..");
const DECLARATION = join(REPO, "assets", "screen_composition.json");
const OBSERVED = join(REPO, ".ui-probe", "screen_composition.json");

export const EXIT_OK = 0;
export const EXIT_VIOLATIONS = 1;
export const EXIT_NO_OBSERVATION = 2;

/** 一条违规。`kind` 三种，各自的修法完全不同，所以 NEVER 合成一种。 */
export function violation(kind, route, subject, detail) {
  return { kind, route, subject, detail };
}

/**
 * 对账。`declaration` 是「该有什么」，`observed` 是「屏上真有什么」。
 *
 * 三类违规：
 *
 * - `missing_component`：声明要它，DOM 里没有 —— **那一屏没接这个组件**；
 * - `zero_size`：DOM 里有，宽高是 0 —— `F-09` 的形状（用户看不见）；
 * - `unstyled_class`：类名在，计算样式与裸元素**逐条相同** —— 零样式。
 */
export function audit(declaration, observed) {
  const seen = new Map(observed.screens.map((s) => [s.route, s]));
  const findings = [];

  for (const screen of declaration.screens) {
    const rows = seen.get(screen.route);
    if (rows === undefined) {
      findings.push(violation(
        "not_probed", screen.route, "",
        "声明了这一屏，取证里却没有它——**没量过的屏不算做过**"));
      continue;
    }
    for (const selector of screen.components ?? []) {
      const found = rows.components?.[selector];
      if (!found || found.present !== true) {
        findings.push(violation(
          "missing_component", screen.route, selector,
          "声明 MUST 用到这个组件，屏上没有它"));
        continue;
      }
      if (!(found.width > 0 && found.height > 0)) {
        findings.push(violation(
          "zero_size", screen.route, selector,
          `DOM 里有、宽高是 ${found.width}×${found.height}——用户看不见（F-09 的形状）`));
      }
    }
    for (const cls of screen.styled ?? []) {
      const found = rows.styled?.[cls];
      if (!found || found.present !== true) {
        findings.push(violation(
          "missing_component", screen.route, `.${cls}`,
          "声明 MUST 有样式的类名，屏上没有它"));
        continue;
      }
      if (found.differsFromBare !== true) {
        findings.push(violation(
          "unstyled_class", screen.route, `.${cls}`,
          "类名在，而计算样式与裸元素逐条相同——**零样式**"));
      }
    }
  }
  return findings;
}

function main(argv) {
  const declPath = argIn(argv, "--declaration") ?? DECLARATION;
  const obsPath = argIn(argv, "--observed") ?? OBSERVED;

  if (!existsSync(obsPath)) {
    process.stdout.write(
      `没有观测产物：${obsPath}\n` +
      "修法：起栈后跑 pytest tests/v041/test_screen_composition.py -q\n" +
      "（**这不是「有违规」**：一个是去做界面，一个是去跑取证，修法完全不同）\n");
    return EXIT_NO_OBSERVATION;
  }
  const declaration = JSON.parse(readFileSync(declPath, "utf8"));
  const observed = JSON.parse(readFileSync(obsPath, "utf8"));
  const findings = audit(declaration, observed);

  if (argv.includes("--json")) {
    process.stdout.write(JSON.stringify({ findings }, null, 1));
  } else if (findings.length === 0) {
    const screens = declaration.screens.length;
    const items = declaration.screens.reduce(
      (n, s) => n + (s.components?.length ?? 0) + (s.styled?.length ?? 0), 0);
    process.stdout.write(
      `逐屏组件对照：${screens} 屏 / ${items} 项声明，0 处违规。\n`);
  } else {
    for (const f of findings) {
      process.stdout.write(`${f.kind} ${f.route} ${f.subject} — ${f.detail}\n`);
    }
    process.stdout.write(`\n共 ${findings.length} 处违规。\n`);
  }
  return findings.length === 0 ? EXIT_OK : EXIT_VIOLATIONS;
}

function argIn(argv, flag) {
  const at = argv.indexOf(flag);
  return at === -1 ? null : argv[at + 1];
}

if (process.argv[1] && process.argv[1].endsWith("check_screen_composition.mjs")) {
  process.exit(main(process.argv.slice(2)));
}
