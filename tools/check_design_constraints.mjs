#!/usr/bin/env node
// AUDIT-02：把交付包《技术约束清单》做成机器断言。
//
// 用法：node tools/check_design_constraints.mjs web [--json]
//
// ## 这把尺子量的是「功能正确性」，不是风格
//
// 清单开头那句话是它自己的边界：「这里全是**功能正确性**问题——界面显示了后端
// 没给的东西，或漏掉了后端明确给出的状态。风格自由不受这份清单限制。」
// 所以本器一条样式规则都没有，只有「显示了不存在的东西」与「漏了存在的东西」。
//
// ## 不与既有尺子重叠
//
// 清单第 1 条的「置信度可视化」那一半归 `tools/lint_no_confidence_viz.mjs`
// （DESIGN-23 已建），本器**不重复实现**——两把尺子量同一件事的那天，
// 它们会在某个边界上给出不同答案，而两边各有一半的道理。
// 本器只补它没覆盖的那一半：星级 / 雷达 / 把布尔枚举画成百分比。
//
// ## 每条规则都要能被证明「认得出违规」
//
// 「没扫到违规」与「尺子瞎了」在退出码上长得一模一样（都是 0）。
// 所以每条规则在 `tests/v041/test_design_constraints.py` 里都配一条阴性对照：
// 构造一段真违规的源码，断言这条规则报红。**没有阴性对照的规则不算数。**

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { codeOnly } from "./_scan_lib.mjs";

const SOURCE_EXT = [".ts", ".tsx", ".js", ".mjs", ".css"];
const TEST_MARKERS = [".test.", ".spec.", `${sep}__tests__${sep}`];

// 未建接口的六类 id（清单第 3 条逐字点名）
const UNBUILT_REFS = [
  "citation_id", "chart_id", "card_ref", "hints_ref", "price_entry_id",
  "field_path",
];
// 留位必须说的那句话。**空白与假内容都不算**。
const NOT_PROVIDED = /接口未提供/;

/**
 * 把注释与**类型声明体**剥掉，剩下的就是这个文件真正会跑的部分。
 *
 * A3 用它判「这个文件有没有运行时」。注释也要剥：
 * 一段解释「这里为什么不需要 return」的注释里带着 `return` 二字，
 * 会让一个纯类型文件被当成有运行时——**说明问题的那句话又被当成问题本身**。
 */
function declarationsStripped(code) {
  return code
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, " ")
    .replace(/export\s+(interface|type)\s+[\s\S]*?(?:\n\}|;)\s*$/gm, " ");
}

/** 一条违规。`rule` 是清单里的条目号，读表的人据此回去看原文。 */
function violation(rule, file, line, detail) {
  return { rule, file, line, detail };
}

function linesOf(code) {
  return code.split("\n");
}

function scanLines(code, pattern, make) {
  const out = [];
  linesOf(code).forEach((text, index) => {
    if (pattern.test(text)) out.push(make(index + 1, text.trim()));
  });
  return out;
}

// ── 规则表 ────────────────────────────────────────────────────────
// 每条：{ id, title, appliesTo(file), check(code, file) -> violation[] }

const RULES = [
  {
    id: "A1",
    title: "把布尔/枚举画成连续量（星级 / 雷达 / 合成百分比）",
    check: (code, file) => [
      ...scanLines(code, /[★☆]|radar[-_ ]?chart|StarRating/i, (line, text) =>
        violation("A1", file, line, `星级或雷达：${text.slice(0, 70)}`)),
      // `${x}%` 只有绑真进度（JobView.progress）或骨架屏时才成立。
      ...scanLines(
        code,
        /\$\{(?![^}]*\b(progress|skeleton|pct|percent_from_backend)\b)[^}]*\}%/,
        (line, text) =>
          violation("A1", file, line, `前端合成的百分比：${text.slice(0, 70)}`)),
    ],
  },
  {
    id: "A3",
    title: "未建接口留位必须写「接口未提供」（不是假内容，也不是空白）",
    appliesTo: (file) => /deref|Deref/.test(file),
    check: (code, file) => {
      const touches = UNBUILT_REFS.some((ref) => code.includes(ref));
      if (!touches || NOT_PROVIDED.test(code)) return [];
      // **纯类型声明文件不在这条规则的射程内**（`TYPE-05` 撞出来的）。
      //
      // 这条规则治的是「留位处显示了假内容或空白」——那是一件**渲染时**的事。
      // 一个只有 `export interface` / `export type` 的文件什么都不渲染，
      // 它连一个能显示那句话的位置都没有。
      //
      // 要它写上「接口未提供」，写出来的会是一句**它并不执行的承诺**——
      // 而那比不写更坏：下一个人读到那句话，会以为这条通道的留位已经处理过了。
      //
      // 判的是**有没有运行时**（函数 / 箭头 / JSX / 取数），不是文件后缀：
      // 按后缀判的话，一个 `.ts` 里塞进真逻辑就能顺带免检。
      // `\b` 对 `=>` 无效（两侧都不是单词字符），写成 `\b(function|=>|…)`
      // 会让箭头函数**永远匹配不上**——阴性对照当场抓到了这一处。
      if (!/(\bfunction\b|=>|fetch\(|\breturn\b)/.test(declarationsStripped(code))) {
        return [];
      }
      return [violation("A3", file, 1,
        "这个文件处理未建接口的 id，却没有一处写「接口未提供」")];
    },
  },
  {
    id: "A4",
    title: "状态标记要有非颜色载体（形状 / 质地 / 底纹）",
    // `UIX-03` 建了 `web/components/shell/StatusMark.tsx`，这条规则**有对象了**。
    //
    // 原先这里挂着一句 `optionalSubject` 豁免语（大意：那个组件还没建）——
    // 那是「没有对象不等于跑过了、干净」的登记方式，
    // 它让这条规则的绿不会被读成「状态标记已经查过了」。
    //
    // **豁免语现在必须撤掉**：留着它，哪天 `StatusMark` 被删掉或改名，
    // 这条规则会**悄悄退回豁免**——报告上写着「无可量对象」，
    // 而真相是「本来有，被弄没了」。两者在报告里长得一模一样。
    // （判据 `tests/v041/test_status_mark.py::test_a4_is_no_longer_excused`）
    //
    // ## DS-01 补一条：**把记号交给 `_ds` 的那种写法**
    //
    // `web/components/shell/DsStatusMark.tsx` 是 `_ds` 八态标记的封装，它**一行视觉都不写**
    // ——形状、质地、底纹全在 `_ds_bundle.js` 里。抄一份过来才是坏事：
    // 两份视觉从此各自漂移，而屏上看不出哪一份才是设计系统。
    // 于是它在这条规则下先天不及格，而它其实是最合格的那一个。
    //
    // 所以「交给 `_ds`」算过——**但不是白算**：载体到底在不在，源码扫描器看不见，
    // 由一把更硬的尺子在真浏览器里量（`tests/v041/test_ds_bundle_wired.py::
    // test_the_status_mark_carries_a_non_colour_difference_at_runtime`：
    // 三态的边框笔法、底纹、记号形状必须互不相同）。
    // 认的是 `useDsComponent("StatusMark")` 这一句：改成自己画，这里立刻回到红。
    appliesTo: (file) => /StatusMark|status-mark/i.test(file),
    check: (code, file) => {
      const hasNonColour = /(shape|glyph|pattern|texture|hatch|dash|stripe|border)/i
        .test(code);
      const delegatesToDs = /useDsComponent\s*(<[^>]*>)?\s*\(\s*"StatusMark"/.test(code);
      return hasNonColour || delegatesToDs ? [] : [violation("A4", file, 1,
        "状态标记只有颜色，没有形状/质地/底纹——灰度打印下分不出来")];
    },
  },
  {
    id: "A5",
    title: "`--rust` 只留给阻塞标 / 409 / 503",
    check: (code, file) => scanLines(
      code,
      /--rust/,
      (line, text) => (
        /(block|409|conflict|503|unavailable|dispute)/i.test(text)
          ? null
          : violation("A5", file, line, `--rust 被挪用：${text.slice(0, 70)}`)
      )).filter(Boolean),
  },
  {
    id: "B8",
    title: "`/plaza/hot` 按后端序渲染，无前端重排",
    appliesTo: (file) => /plaza|Plaza|hotspot/i.test(file),
    check: (code, file) => scanLines(
      code, /\.sort\(|sortBy|orderBy/,
      (line, text) => violation("B8", file, line, `前端重排：${text.slice(0, 70)}`)),
  },
  {
    id: "B9",
    title: "`by_source` 四源不合成、不堆叠",
    check: (code, file) => scanLines(
      code, /by_source[^\n]*\.(reduce|flat|concat)\(|sum\([^\n]*by_source/,
      (line, text) => violation("B9", file, line, `四源被合成：${text.slice(0, 70)}`)),
  },
  {
    id: "C17a",
    title: "verdict 直取后端值，前端 NEVER 自己判",
    check: (code, file) => scanLines(
      code,
      // 两种形态都算「前端在判」：拿 verdict 与字面量比，
      // **以及从一个计算里三元出一个 A/B/C/D**——后者才是最常见的那种，
      // 而它长得完全不像在判 verdict。
      /verdict\s*[=!]==?\s*["'](A|B|C|D)["']|\?\s*["'](A|B|C|D)["']\s*:/,
      (line, text) =>
        violation("C17a", file, line, `前端在判 verdict：${text.slice(0, 70)}`)),
  },
  {
    id: "C17b",
    title: "`constraints_checked` 按**对象**处理，不是 boolean",
    check: (code, file) => scanLines(
      code,
      /constraints_checked\s*(===?\s*(true|false)|\?\s*["'])|!\s*constraints_checked/,
      (line, text) =>
        violation("C17b", file, line,
          `constraints_checked 被当成 boolean：${text.slice(0, 70)}`)),
  },
  {
    id: "C19",
    title: "`unknown` 竞品与 `weak` 不同形",
    check: (code, file) => {
      if (!/["']unknown["']/.test(code) || !/["']weak["']/.test(code)) return [];
      // 两者被写进同一个分支 = 同形。
      // 真实写法是 `s === 'unknown' || s === 'weak'`，两个字面量中间隔着比较式。
      // 只认「两个字面量紧挨着」的话，这条规则永远抓不到真的那一种。
      const merged =
        /["'](unknown|weak)["'].{0,24}\|\|.{0,24}["'](unknown|weak)["']/;
      return scanLines(code, merged, (line, text) =>
        violation("C19", file, line,
          `unknown 与 weak 被合成一档：${text.slice(0, 70)}`));
    },
  },
  {
    id: "D23",
    title: "`quantity` 原样呈现，NEVER 乘算",
    check: (code, file) => scanLines(
      code, /quantity\s*\*|\*\s*quantity/,
      (line, text) => violation("D23", file, line, `quantity 被乘算：${text.slice(0, 70)}`)),
  },
  {
    id: "A6",
    title: "每屏三态齐全，且空态 ≠ 错误态",
    // 相对路径是 `app/plaza/page.tsx`——**开头就是 `app/`，前面没有分隔符**。
    // 写成 `[\\/]app[\\/]` 的话这条规则一个文件都落不到，而它会静静地全绿。
    appliesTo: (file) => /^app[\\/].*page\.tsx$/.test(file),
    // 三态**常常不在 page 里**：页面把它们交给 `<Screen>`、`<PlazaView>` 这类
    // 本地组件。只看 page 自己的文本会把六个页面全报成「缺三态」——
    // 而它们一个都不缺。所以连**它 import 进来的本仓文件**一起看（一层）。
    withLocalImports: true,
    check: (code, file) => {
      const has = (re) => re.test(code);
      // **三态是给取数屏的。** 一屏什么都不取，就没有「加载中」这回事——
      // 硬要它写一个加载态，写出来的是一段永远进不去的死分支，
      // 而死分支会让下一个人以为这屏在取数。
      // 判据窄到「这屏发不发请求」：发请求的一律要三态，不发的这条不管。
      // （UI-03 的 `/workbenches/[id]` 就是这一种：`GET /workbenches` 未建，
      //  它一个请求都不发，如实标「接口未提供」。）
      // **读信号要认「进屏取数」，不是认「文件里出现过 Client」。**
      //
      // `CHAIN-04` 的发起分析屏是一张**写**屏：进屏零请求，按下键才 POST。
      // 它只因 import 了 `chainClient` 就命中 `Client\b`，于是被要求写一个空态——
      // 而它没有任何列表可空。那正是本规则自己上面那段注释警告的
      // 「写出来的是一段永远进不去的死分支」。
      //
      // 收窄成三样**进屏就会跑**的东西：`useScreenData`（本仓取数钩子）、
      // `useEffect`（进屏副作用）、`fetchXxx(`（具名取数函数）。
      // 写屏不受这条管，但它仍受**自己卡上的判据**管
      // （`test_analysis_entry_screens.py` 里有进行态与三种拒绝各自的断言）。
      if (!has(/useScreenData|useEffect|fetch[A-Z]\w*\s*\(/)) return [];
      const missing = [];
      if (!has(/Loading|Skeleton|loading/)) missing.push("加载态");
      if (!has(/Empty|empty|空/)) missing.push("空态");
      if (!has(/Error|error|错误/)) missing.push("错误态");
      if (missing.length) {
        return [violation("A6", file, 1, `缺${missing.join("、")}`)];
      }
      // 空态与错误态**同一个组件**渲染 = 把「没有内容」做成了「出错了」。
      return scanLines(code, /Empty[A-Za-z]*\s*=\s*Error|isEmpty\s*\|\|\s*isError/,
        (line, text) =>
          violation("A6", file, line, `空态被当成错误态：${text.slice(0, 70)}`));
    },
  },
];

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (["node_modules", ".next", "public", "design"].includes(entry)) continue;
      out.push(...walk(full));
      continue;
    }
    if (SOURCE_EXT.some((ext) => entry.endsWith(ext))) out.push(full);
  }
  return out;
}

/** 一个文件 import 进来的**本仓相对路径**源码（一层，读不到就跳过）。 */
function localImportSources(file, code) {
  const dir = file.slice(0, Math.max(file.lastIndexOf(sep), 0));
  const specifiers = [...code.matchAll(/from\s+["'](\.[^"']+)["']/g)].map((m) => m[1]);
  const out = [];
  for (const spec of specifiers) {
    for (const ext of [".tsx", ".ts", "/index.tsx", "/index.ts"]) {
      try {
        out.push(readFileSync(join(dir, spec + ext), "utf8"));
        break;
      } catch {
        // 读不到就试下一个后缀；都读不到就跳过——**NEVER 因此报违规**，
        // 那会把「我没找到这个文件」说成「这个页面缺三态」。
      }
    }
  }
  return out.join("\n");
}

/**
 * App Router 的**同目录约定文件**：`loading.tsx` / `error.tsx` / `not-found.tsx`。
 *
 * ## 为什么要连它们一起看
 *
 * `app/deliverables/[id]/page.tsx` 是 **async 服务器组件**——
 * 它 `await` 完才返回 JSX，组件内部**没有「正在加载」那一刻可以渲染**。
 * Next 的机制是：同目录的 `loading.tsx` 被框架自动包成 `<Suspense fallback>`。
 *
 * 不认这个约定的话，A6 会要求那类页面在 `page.tsx` 里写一个加载分支——
 * 而那是一段**永远进不去的死分支**。A6 自己的注释就写着
 * 「硬凑的死分支比没有更坏」，规则却在逼人写它。
 *
 * `loading.tsx` 与页面**在同一个目录**、由框架直接配对，
 * 所以把它算进这一页的三态面是准确的，不是放水：
 * 它确实会在这一页取数时显示。
 */
function routeConventions(file) {
  const dir = file.slice(0, file.lastIndexOf(sep));
  const parts = [];
  for (const name of ["loading.tsx", "error.tsx", "not-found.tsx"]) {
    const candidate = join(dir, name);
    try {
      parts.push(codeOnly(readFileSync(candidate, "utf8")));
    } catch {
      // 没有这个约定文件——不是错误，多数页面本来就不需要。
    }
  }
  return parts.join("\n");
}


export function scanTree(root) {
  const findings = [];
  // 每条规则**落到过几个文件**。一条规则一个文件都没落到 = 它是瞎的，
  // 而瞎的规则与「跑过了、没问题」在退出码上长得一模一样。
  const applied = Object.fromEntries(RULES.map((r) => [r.id, 0]));
  for (const file of walk(root)) {
    const shown = relative(root, file);
    // 测试文件不算：测试里**故意**写违规样例来证明尺子认得出它们。
    if (TEST_MARKERS.some((marker) => file.includes(marker))) continue;
    const code = codeOnly(readFileSync(file, "utf8"));
    const withImports =
      code + "\n" + localImportSources(file, code) + "\n" + routeConventions(file);
    for (const rule of RULES) {
      if (rule.appliesTo && !rule.appliesTo(shown)) continue;
      applied[rule.id] += 1;
      findings.push(...rule.check(rule.withLocalImports ? withImports : code, shown));
    }
  }
  // 返回**对象**而不是给数组挂一个属性：`JSON.stringify` 只序列化数组的元素，
  // 挂上去的 `applied` 会在 `--json` 里悄悄消失——报告里没有它，
  // 读的人也就无从知道哪几条规则其实没跑。
  const unapplied = RULES.filter((r) => applied[r.id] === 0);
  return {
    findings,
    applied,
    // 「规则写错了、一个文件都没落到」与「这条规则的对象本仓还没有」是两件事：
    // 前者是 bug（要修），后者是实况（要说出来但不算失败）。
    blind: unapplied.filter((r) => !r.optionalSubject).map((r) => r.id),
    noSubject: unapplied
      .filter((r) => r.optionalSubject)
      .map((r) => ({ id: r.id, why: r.optionalSubject })),
  };
}

export const RULE_IDS = RULES.map((r) => r.id);

function main(argv) {
  const root = argv.find((a) => !a.startsWith("--")) ?? "web";
  const { findings, applied, blind, noSubject } = scanTree(root);
  if (argv.includes("--json")) {
    process.stdout.write(
      JSON.stringify({ root, findings, applied, blind, noSubject }, null, 1));
  } else if (findings.length === 0) {
    process.stdout.write(
      `技术约束清单：${RULES.length} 条规则跑过 ${root}，0 处违规。\n`);
    if (blind.length) {
      process.stdout.write(
        `**但这几条一个文件都没落到（= 没跑）**：${blind.join("、")}\n`);
    }
  } else {
    for (const f of findings) {
      process.stdout.write(`${f.rule} ${f.file}:${f.line} — ${f.detail}\n`);
    }
    process.stdout.write(`\n共 ${findings.length} 处违规。\n`);
  }
  // 有违规、或有规则没落到过任何文件，都算不通过：
  // 一条没跑过的规则给出的绿，与真绿不是一回事。
  return findings.length === 0 && blind.length === 0 ? 0 : 1;
}

if (import.meta.url === `file://${process.argv[1]}`.replace(/\\/g, "/")
    || process.argv[1]?.endsWith("check_design_constraints.mjs")) {
  process.exit(main(process.argv.slice(2)));
}
