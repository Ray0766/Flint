#!/usr/bin/env node
// FB-10：产品面不许出现 A 类脚手架。
//
// 用法：node tools/no_scaffold_on_screen.mjs web [--json]
// 退出码 0 = 产品面干净；1 = 有脚手架跑到了屏上（逐条点名文件与行号）。
//
// ## A 类脚手架 = 开发要看的东西跑到了产品面
//
// 端点路径、内部文件路径、block/section 内部 id、`X-User-Id` / `demo-user`。
// 它们对用户毫无意义，只会让人以为产品还没做完——而在 FB-09 之前，
// 报告屏上那一排 `fact-demo-vecdb-cost` 就是这么来的。
//
// ## 诚实态不是脚手架，一条都不许误伤
//
// 哪块被阻断导出、哪个数字有出处、哪条陈述有争议、哪处「接口未提供」——
// 这些是**产品需求**，用户有权看见。**一把会误伤它们的尺子，会逼着后人把这些从
// 界面上删掉，而那正好是这套系统最不该丢的东西。**
// 所以判据只认「开发面形态」，并且：
//
// - **只扫代码层**：注释里写 `POST /workbenches/{id}/edges` 是在解释实现，不是渲染它
//   （本批第六次同一类问题——判据落在代码上，不落在解释代码的话上）；
// - **`data-*` 属性不算**：那是取证与调试的落点（EYE-01 的 `--selector` 靠它），
//   属开发面但**不显示给用户**，与「跑到屏上」是两回事；
// - **出处 id 本身不算**：`{c.citation_id}` 那类是引用通道的内容（FB-09 之后由
//   `DerefValue` 换成人话，换不到时如实显示原 id——那是诚实态，不是脚手架）。
//
// ## 一处显式例外：`field_path`
//
// `ProfileRef.field_path`（第三条出处通道）看起来像 schema 字段名，但它说的是
// **这个数字来自档案里的哪一项**——删了就是删出处。按 FB-10 acceptance④ 保留，
// 在这里显式登记而不是让规则悄悄漏过去。**例外只此一个**，别的字段名照旧判红。

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const REPO_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const SCHEMA = "no-scaffold/1";
const SOURCE_EXT = [".ts", ".tsx", ".js", ".jsx"];
const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "coverage", ".git", "_ds"]);
const TEST_MARKERS = [".test.", ".spec.", `${sep}__tests__${sep}`];

// 显式例外：出处通道，删了就是删出处（见文件头）。
const ALLOWED_FIELD_RENDERS = new Set(["field_path"]);

const RULES = [
  {
    name: "端点路径",
    // `GET /…` 这类跑到屏上等于把 API 文档贴给用户。
    re: /\b(GET|POST|PUT|PATCH|DELETE)\s+\/[\w{}/-]+/,
  },
  {
    name: "内部文件路径",
    re: /\b(?:flint|tests|harness|migrations)\/[\w/-]+\.(?:py|tsx?|jsx?|json|md)\b/,
  },
  {
    name: "身份头/演示账号",
    re: /X-User-Id|demo-user/,
  },
  {
    name: "内部 id 直接当正文",
    // `{x.block_id}` 作为元素内容。`data-block-id={…}` 是属性，不在此列。
    re: /[>{]\s*\{\s*\w+\.(\w*(?:block|section|deliverable|job|ledger)_id)\s*\}/,
  },
  {
    name: "schema 字段名当正文",
    re: /[>{]\s*\{\s*\w+\.(\w+_(?:path|field|schema|column))\s*\}/,
  },
];

function sources(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) sources(full, out);
    else if (SOURCE_EXT.some((e) => entry.endsWith(e))
             && !TEST_MARKERS.some((m) => full.includes(m))) out.push(full);
  }
  return out;
}

/** 剥注释：注释里提端点是在**解释**实现，不是渲染它。 */
function codeOnly(text) {
  return text
    .replace(/\r\n?/g, "\n")
    .replace(/\/\*[\s\S]*?\*\//g, (b) => "\n".repeat((b.match(/\n/g) ?? []).length))
    .split("\n")
    .map((line) => line.replace(/(^|[^:])\/\/.*$/, "$1"))
    .join("\n");
}

function scan(dir) {
  const hits = [];
  const files = sources(dir);
  for (const file of files) {
    const rel = relative(REPO_ROOT, file).split(sep).join("/");
    codeOnly(readFileSync(file, "utf8")).split("\n").forEach((line, i) => {
      for (const rule of RULES) {
        const m = rule.re.exec(line);
        if (!m) continue;
        if (m[1] && ALLOWED_FIELD_RENDERS.has(m[1])) continue;   // 登记过的例外
        hits.push({ rule: rule.name, file: rel, line: i + 1, text: line.trim().slice(0, 100) });
      }
    });
  }
  return { schema: SCHEMA, scanned_files: files.length, hits };
}

function main(argv) {
  const asJson = argv.includes("--json");
  const target = resolve(REPO_ROOT, argv.find((a) => !a.startsWith("--")) ?? "web");
  const report = scan(target);

  if (asJson) {
    console.log(JSON.stringify(report, null, 2));
    return report.hits.length > 0 ? 1 : 0;
  }

  console.log(`扫描 ${report.scanned_files} 个源文件（测试文件与注释不算）`);
  if (report.hits.length === 0) {
    console.log("产品面没有 A 类脚手架。");
    return 0;
  }
  console.error(`\n脚手架跑到产品面 ${report.hits.length} 处：`);
  for (const h of report.hits) {
    console.error(`    ✗ ${h.file}:${h.line}  [${h.rule}]  ${h.text}`);
  }
  console.error("这些是开发要看的东西，用户看到只会以为产品还没做完。");
  return 1;
}

process.exit(main(process.argv.slice(2)));
