#!/usr/bin/env node
// GAUGE-04 / 终检 F-08：文档里的 vitest 过滤器自检——**匹配零文件的过滤器必须被点名**。
//
// 用法：node tools/check_vitest_filters.mjs [文档…]        （默认 WORKORDER-v04.md + docs/PRINCIPLES-v04.md）
//       node tools/check_vitest_filters.mjs --json 文档…    （机读报告，供 pytest 消费）
// 退出码 0 = 每条命令的每个过滤器都至少匹配到一个测试文件；1 = 有匹配零文件的过滤器（逐条点名）。
//
// ## 这把尺子在防什么（F-08 实测，非推测）
//
// vitest 的位置参数是**过滤器**，匹配不到的那些**一声不响地被丢掉**：
//
//   A 只给不存在的过滤器：  npm test -- --run src/views
//     → No test files found, exiting with code 1        ← 大声失败，这种没问题
//   B 混合过滤器（文档里的形状）：npm test -- --run components src/views
//     → Test Files 21 passed / Tests 143 passed，EXIT=0  ← 静默丢掉 src/views，报绿
//
// **只要有一个过滤器能匹配上，vitest 就 exit 0。** 于是 `WORKORDER-v04.md:528`（V4 图谱工作台
// 里程碑门）按文档跑只跑到 128 条里的 6 条——**4.7%**——并且报绿。人看到绿就走了。
//
// 兜底开关挡不住这种情况：`--passWithNoTests=false` 判的是「一个文件都没匹配到」，
// 而混合过滤器**匹配到了**（只是少了一大半）。**唯一挡得住的判据是逐个过滤器数它的匹配数。**
//
// ## 匹配语义（对着真 vitest 标定过，不是照文档猜的）
//
// 判据 = 过滤器字符串是**测试文件相对 web/ 路径**（正斜杠）的子串。四个标定点，
// 与真 vitest 逐个对上（2026-08-04 实测）：
//
//   components                                        → 21 文件（vitest: Test Files 21）
//   components/graph-node                             → 1  文件（vitest: 1，6 tests）
//   components views                                  → 31 文件（vitest: 31，225 tests）
//   components/graph-node components/graph-edge lib/undo lib/graph-layout views
//                                                     → 16 文件（vitest: 16，128 tests）
//
// 只拿相对路径比、不拿绝对路径比：仓库目录名里若含 `web` / `components` 这类词，
// 绝对路径会让任何过滤器都「匹配得到」——那正是这把尺子要防的假绿，NEVER 用它。
//
// ## 扫到零条命令 = 红
//
// 文档改名、章节重排、命令换写法，都会让扫描器扫到零条命令。**那时候报绿等于说
// 「我检查过了，没问题」，而它其实什么都没检查**——F-08 本身就是这么长出来的。

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

// 用 fileURLToPath 而不是 `new URL(…).pathname`：本仓库路径里有空格与中文，
// pathname 给的是百分号编码串（`Vibe%20coding`），拿去 readdirSync 直接 ENOENT。
const REPO_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const WEB_ROOT = join(REPO_ROOT, "web");
const DEFAULT_DOCS = ["WORKORDER-v04.md", "docs/PRINCIPLES-v04.md"];

// vitest 默认 include：**/*.{test,spec}.?(c|m)[jt]s?(x)
const TEST_FILE_RE = /\.(test|spec)\.(c|m)?[jt]sx?$/;
const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "coverage", ".git"]);

/** web/ 下全部测试文件，路径相对 web/、正斜杠。 */
function testFiles(dir = WEB_ROOT, out = []) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) testFiles(full, out);
    else if (TEST_FILE_RE.test(entry)) out.push(relative(WEB_ROOT, full).split(sep).join("/"));
  }
  return out;
}

/** 一个过滤器匹配到的文件（vitest 语义：路径子串）。 */
function matches(filter, files) {
  return files.filter((f) => f.includes(filter));
}

/**
 * 0 命中过滤器的补救建议：逐段砍掉开头，看哪一截能命中。
 * `src/lib/undo` → `lib/undo` 命中 1 个 —— DEC-007 那次 `web/src/`→`web/` 重映射漏掉的正是这一形状。
 */
function suggest(filter, files) {
  const parts = filter.split("/");
  for (let i = 1; i < parts.length; i += 1) {
    const tail = parts.slice(i).join("/");
    const hit = matches(tail, files);
    if (hit.length > 0) return { filter: tail, count: hit.length };
  }
  return null;
}

/** 从一行 markdown 里抽出全部 vitest 调用的过滤器串。 */
function extractCommands(line) {
  const found = [];
  // 先抽反引号内联代码段：表格的 `|` 与句末中文标点都在段外，段内原样。
  const spans = [...line.matchAll(/`([^`]+)`/g)].map((m) => m[1]);
  const bare = line.replace(/`[^`]*`/g, "");
  for (const text of [...spans, bare]) {
    for (const m of text.matchAll(/npm\s+test\s+--\s+--run\s+([^`|;]*)/g)) {
      // 命令在 `&&` 处结束：`npm test -- --run design/model-picker && node tools/…`
      const rest = m[1].split(/&&|\|\|/)[0];
      const tokens = rest.trim().split(/\s+/).filter(Boolean);
      const filters = tokens.filter((t) => !t.startsWith("-"));
      found.push({ raw: `npm test -- --run ${rest.trim()}`, filters });
    }
  }
  return found;
}

function scanDoc(docPath, files) {
  // resolve 而不是 join：测试会传绝对路径的构造文档，join 会把它接在仓库根后面。
  const abs = resolve(REPO_ROOT, docPath);
  const text = readFileSync(abs, "utf8").replace(/\r\n?/g, "\n");
  const commands = [];
  text.split("\n").forEach((line, i) => {
    for (const cmd of extractCommands(line)) {
      const filters = cmd.filters.map((f) => {
        const hit = matches(f, files);
        return {
          filter: f,
          count: hit.length,
          suggestion: hit.length === 0 ? suggest(f, files) : null,
        };
      });
      const union = new Set();
      const repaired = new Set();
      for (const f of filters) {
        for (const hit of matches(f.filter, files)) union.add(hit);
        const effective = f.count > 0 ? f.filter : f.suggestion?.filter;
        if (effective) for (const hit of matches(effective, files)) repaired.add(hit);
      }
      commands.push({
        doc: docPath,
        line: i + 1,
        raw: cmd.raw,
        filters,
        filesMatched: union.size,
        filesIfRepaired: repaired.size,
      });
    }
  });
  return commands;
}

function main(argv) {
  const asJson = argv.includes("--json");
  const docs = argv.filter((a) => !a.startsWith("--"));
  const targets = docs.length > 0 ? docs : DEFAULT_DOCS;

  const files = testFiles();
  const commands = targets.flatMap((doc) => scanDoc(doc, files));
  const dead = commands.flatMap((c) =>
    c.filters.filter((f) => f.count === 0).map((f) => ({ ...f, doc: c.doc, line: c.line, raw: c.raw })),
  );

  if (asJson) {
    console.log(JSON.stringify({ testFileCount: files.length, targets, commands, dead }, null, 2));
    return commands.length === 0 || dead.length > 0 ? 1 : 0;
  }

  console.log(`web/ 下测试文件：${files.length} 个；扫描文档：${targets.join(" ")}`);
  if (commands.length === 0) {
    console.error(
      `扫到 0 条 vitest 命令：${targets.join(" ")}\n` +
        "这不是「没问题」，是这把尺子没量到任何东西——文档改名或命令换写法都会走到这里。",
    );
    return 1;
  }

  for (const cmd of commands) {
    const broken = cmd.filters.some((f) => f.count === 0);
    console.log(`\n${broken ? "✗" : "✓"} ${cmd.doc}:${cmd.line}  ${cmd.raw}`);
    for (const f of cmd.filters) {
      if (f.count > 0) {
        console.log(`    ✓ ${f.filter} → ${f.count} 个文件`);
      } else {
        const tip = f.suggestion
          ? `试试 ${f.suggestion.filter}（→ ${f.suggestion.count} 个文件）`
          : "web/ 下没有任何测试文件路径含这一串";
        console.log(`    ✗ ${f.filter} → 0 个文件，vitest 会静默丢掉它 —— ${tip}`);
      }
    }
    if (broken) {
      console.log(
        `    实际跑到 ${cmd.filesMatched} 个文件；按建议修好后 ${cmd.filesIfRepaired} 个`,
      );
    }
  }

  if (dead.length > 0) {
    console.error(
      `\n匹配零文件的过滤器 ${dead.length} 个：` +
        dead.map((d) => `${d.doc}:${d.line} ${d.filter}`).join("、") +
        "\nvitest 对它们静默丢弃且仍 exit 0——这条门跑的比它声称的少。",
    );
    return 1;
  }
  console.log(`\n全部 ${commands.length} 条命令、${commands.reduce((n, c) => n + c.filters.length, 0)} 个过滤器均有命中。`);
  return 0;
}

process.exit(main(process.argv.slice(2)));
