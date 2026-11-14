#!/usr/bin/env node
// I18N-02-a：i18n 扫描器（CJK 字面量 + B7 静态规则）。
//
// 用法：
//   node tools/i18n_scan.mjs web/components --fail-on-cjk
//   node tools/i18n_scan.mjs web/components            # 只报告不失败
//
// ## 为什么测试文件不在扫描面内（DEC-008）
//
// 测试文件里的中文是**断言数据**，不是发给用户的界面文案。把它们也 key 化，
// 测试就会变成「断言 t('some.key') 等于 t('some.key')」——那不再验证用户看到什么，
// 反而把测试削弱成同义反复。扫描面因此是**要发出去的源文件**：
// 排除 *.test.* / *.spec.* / __tests__/。
//
// ## 白名单是推进机制，不是豁免机制
//
// 白名单里的文件仍会被逐一列出（pending），只是暂不使 --fail-on-cjk 失败。
// I18N-02 的 acceptance 要求**白名单最终为空**——留一条永久豁免就等于没做这张卡。
//
// ## B7 静态规则
//
// embedding / 检索调用点只许引 name_native。引到 name_display（机翻派生物）
// 会让同一个热点因为译文不同而被认成两个——B7 的失守形态之一。

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { codeOnly } from "./_scan_lib.mjs";

const CJK = /[\u4e00-\u9fff\u3040-\u30ff]/;
const SOURCE_EXT = [".ts", ".tsx"];
const TEST_MARKERS = [".test.", ".spec.", `${sep}__tests__${sep}`];
// B7：这些调用点附近 NEVER 出现 name_display / *_display
const B7_CONTEXT = /(embed|embedding|search|retriev|dedup|cluster)/i;
const DISPLAY_FIELD = /\b(name_display|[A-Za-z_]+_display)\b/;

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

function isTestFile(path) {
  return TEST_MARKERS.some((m) => path.includes(m));
}

// 逐行找 CJK 字面量。注释不算——注释不发给用户（DEC-008）。
//
// 剥注释走共享的 `_scan_lib.mjs#codeOnly`：它把三件事一次做对——
// 跨行块注释（JSDoc）、行尾 `//`（且 `//` 前不能是冒号，否则 URL 会被当成注释起点）、
// 以及 CRLF 归一（不归一的话行尾留着回车符，整行注释一个字符都剥不掉）。
// 这三条分别对应 DEC-013 登记的两类假阳性与 DESIGN-21 实测的那次假绿。
const NEWLINE = "\n";
const CRLF_RE = /\r\n?/g;

function cjkLines(text) {
  const hits = [];
  const codeLines = codeOnly(text).split(NEWLINE);
  const rawLines = text.replace(CRLF_RE, NEWLINE).split(NEWLINE);
  rawLines.forEach((line, i) => {
    if (CJK.test(codeLines[i] ?? "")) {
      hits.push({ line: i + 1, text: line.trim().slice(0, 72) });
    }
  });
  return hits;
}

// 自证：这把尺子先证明自己认得出该报的、也不误报不该报的，再去量别人。
// 一把量不准的尺子给出的「0 个文件」，比不量还糟——没人会去查一个通过了的检查。
function selfTest() {
  const cases = [
    {
      name: "块注释里的中文不算",
      lines: ["/**", " * 取一条文案。", " */", "export const a = 1;"],
      expect: 0,
    },
    {
      name: "行尾注释里的中文不算",
      lines: ["const a = 1; // 这是注释"],
      expect: 0,
    },
    {
      name: "真实未 key 化文案仍报红",
      lines: ['const s = "未找到交付物";'],
      expect: 1,
    },
    {
      name: "URL 不被当成注释起点",
      lines: ['const u = "https://x/y"; const s = "中文";'],
      expect: 1,
    },
    {
      // 这一条是本工具真正出过的错：块注释被**删掉**而不是换成等量换行时，
      // 行号整体前移，注释后面那行的中文会被报到别的行号上（I18N-09 实测）。
      // 所以自证不只数命中条数，还要对**行号**。
      name: "块注释后的中文行号不偏移",
      lines: ["/**", " * 说明。", " */", 'const s = "未找到";'],
      expect: 1,
      expectLine: 4,
    },
  ];
  const failures = [];
  for (const c of cases) {
    const lf = c.lines.join(NEWLINE) + NEWLINE;
    const hits = cjkLines(lf);
    const got = hits.length;
    if (got !== c.expect) failures.push(`${c.name}：期望 ${c.expect} 命中，实际 ${got}`);
    if (c.expectLine !== undefined && hits[0]?.line !== c.expectLine) {
      failures.push(
        `${c.name}：期望报在第 ${c.expectLine} 行，实际第 ${hits[0]?.line ?? "无"} 行`,
      );
    }
    // CRLF 与 LF 必须给出相同结果（GRAPH-11 实测的第二类假阳性）
    const crlfSrc = c.lines.join("\r\n") + "\r\n";
    const crlf = cjkLines(crlfSrc).length;
    if (crlf !== got) failures.push(`${c.name}：CRLF 与 LF 结果不同（${crlf} vs ${got}）`);
  }
  return failures;
}

/** B7：同一行里既有检索/embedding 语境、又引了 *_display 字段。 */
function b7Violations(text) {
  const hits = [];
  text.split("\n").forEach((line, i) => {
    if (B7_CONTEXT.test(line) && DISPLAY_FIELD.test(line)) {
      hits.push({ line: i + 1, text: line.trim().slice(0, 72) });
    }
  });
  return hits;
}

function loadWhitelist(root) {
  try {
    const raw = readFileSync(join(root, "i18n-whitelist.json"), "utf8");
    return new Set(JSON.parse(raw).pending ?? []);
  } catch {
    return new Set();
  }
}

const [, , target, ...flags] = process.argv;
if (!target) {
  console.error("用法：node tools/i18n_scan.mjs <目录> [--fail-on-cjk]");
  process.exit(2);
}
const failOnCjk = flags.includes("--fail-on-cjk");

const selfTestFailures = selfTest();
if (selfTestFailures.length > 0) {
  console.error("扫描器自证未通过（先修尺子，再量东西）：");
  for (const f of selfTestFailures) console.error(`  ✗ ${f}`);
  process.exit(2);
}
const whitelist = loadWhitelist(target);

const files = walk(target).filter((f) => !isTestFile(f));
const offenders = [];
const pending = [];
const b7 = [];

for (const file of files) {
  const rel = relative(target, file).split(sep).join("/");
  const text = readFileSync(file, "utf8");
  const cjk = cjkLines(text);
  if (cjk.length) (whitelist.has(rel) ? pending : offenders).push({ rel, cjk });
  const v = b7Violations(text);
  if (v.length) b7.push({ rel, v });
}

console.log(`扫描 ${files.length} 个源文件（已排除测试文件，见 DEC-008）`);
console.log(`  CJK 字面量未 key 化：${offenders.length} 个文件`);
console.log(`  白名单内待推进（pending）：${pending.length} 个文件`);
console.log(`  B7 违规（检索/embedding 引 *_display）：${b7.length} 个文件`);

for (const o of offenders.slice(0, 20)) {
  console.log(`  ✗ ${o.rel}  第 ${o.cjk[0].line} 行: ${o.cjk[0].text}`);
}
for (const p of pending.slice(0, 20)) {
  console.log(`  … ${p.rel}（白名单，待 I18N-02-b 推进）`);
}
for (const x of b7) {
  console.log(`  ✗B7 ${x.rel}  第 ${x.v[0].line} 行: ${x.v[0].text}`);
}

if (whitelist.size > 0) {
  console.log(
    `\n白名单尚有 ${whitelist.size} 项。acceptance 要求**收尾时为空**——` +
      `留一条永久豁免就等于没做这张卡。`,
  );
}

const failed = (failOnCjk && offenders.length > 0) || b7.length > 0;
process.exit(failed ? 1 : 0);
