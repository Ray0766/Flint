#!/usr/bin/env node
// FB-03 / 终检 F-10：被 `t()` 引用的 key **必须在 zh 与 en 里都有定义**。
//
// 用法：node tools/i18n_key_defined.mjs web
//       node tools/i18n_key_defined.mjs <目录> --messages <词条目录> [--json]
// 退出码 0 = 每个被引用的 key 两侧都有定义；1 = 有 key 缺定义（逐条点名 key + 文件行号）。
//
// ## 这把尺子在防什么
//
// 终检实测：全仓 115 个被引用的 key 里有 **3 个两侧都不存在**，于是用户看到的是变量名本身——
// `QuoteSlot` 的展开按钮上写着 `quote.expand_original`、`RegionSwitch` 的标签写着
// `settings.region.label`。**前两处是该元素里唯一的文字**：按钮和标签整个显示成了变量名。
//
// 此前没有任何检查覆盖这个方向：`i18n_scan.mjs` 查的是「有没有中文硬编码」与 B7 静态规则，
// 三个组件自己的测试也没有断言这几处文案。
//
// ## 为什么缺 key 时界面显示的是 key 而不是空白
//
// `web/lib/i18n/t.ts` 缺键时返回 **key 本身**并 `console.warn`（DEC-009 明文，有意为之）。
// 空串会变成界面上一块**无声的空白**，没人会发现；显眼的 key 一眼就能被抓到——
// **这条设计正是 F-10 被发现的原因**，NEVER 把它改成返回空串。
//
// ## 三条判据边界
//
// 1. **两侧都要有**：只在 zh 里有，英文用户照样看到变量名。缺任一侧即红。
// 2. **测试文件不算**：`t()` 的缺键路径本来就要拿一个不存在的 key 当夹具
//    （`nope.key`）。把夹具算成缺陷，等于逼测试删掉自己的反例——而那条反例守的正是 DEC-009。
//    （与 `no_hardcoded_models.mjs` 的「测试文件不算」同一条口径。）
// 3. **定义了却没被引用的键只报不判红**：那不是缺陷，是清理线索。判红会逼人删掉将来要用的
//    文案，或者反过来给不用的键硬造一个引用。
// 4. **动态 key 按前缀判**：`t(`graph.role.${role}`)` 这种拼出来的 key，静态地看不出全集。
//    直接跳过它等于给自己开一个盲区（那正是本工具要治的病）；按**静态前缀**判——
//    `graph.role.` 下两侧都得至少有一个定义。一个前缀下一个候选都没有 = 真泄漏，判红。
//    本工具第一版没有这一档，把两处合法的动态 key 报成了缺失（实测现场，见 docs/trace/FB-03.md）。

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath 而不是 `new URL(…).pathname`：本仓库路径含空格与中文，
// pathname 给的是百分号编码串，拿去 readdirSync 直接 ENOENT。
const REPO_ROOT = resolve(fileURLToPath(new URL(".", import.meta.url)), "..");
const SCHEMA = "i18n-key-defined/1";
const SOURCE_EXT = [".ts", ".tsx", ".js", ".jsx", ".mjs"];
const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "coverage", ".git", "_ds"]);
const TEST_MARKERS = [".test.", ".spec.", `${sep}__tests__${sep}`];
const LOCALES = ["zh", "en"];

// `t("key")` / `t('key')` / `t(\`key\`)`，允许第二个参数（插值）。
const T_CALL = /\bt\(\s*["'`]([^"'`]+)["'`]/g;

function sources(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (SKIP_DIRS.has(entry)) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) sources(full, out);
    else if (SOURCE_EXT.some((ext) => entry.endsWith(ext))
             && !TEST_MARKERS.some((m) => full.includes(m))) out.push(full);
  }
  return out;
}

/** 逐行扫，因为报告要给行号——只给文件名的话，一个 key 在哪一行仍要人去找。 */
function references(files, root) {
  const found = [];
  for (const file of files) {
    const rel = relative(root, file).split(sep).join("/");
    readFileSync(file, "utf8").replace(/\r\n?/g, "\n").split("\n").forEach((line, i) => {
      for (const m of line.matchAll(T_CALL)) {
        found.push({ key: m[1], file: rel, line: i + 1 });
      }
    });
  }
  return found;
}

function catalogs(messagesDir) {
  const loaded = {};
  for (const locale of LOCALES) {
    const path = join(messagesDir, `${locale}.json`);
    loaded[locale] = JSON.parse(readFileSync(path, "utf8"));
  }
  return loaded;
}

function main(argv) {
  const asJson = argv.includes("--json");
  const flags = argv.filter((a) => a.startsWith("--"));
  const positional = argv.filter((a) => !a.startsWith("--"));
  const target = resolve(REPO_ROOT, positional[0] ?? "web");

  const msgFlag = argv.indexOf("--messages");
  const messagesDir = msgFlag >= 0
    ? resolve(REPO_ROOT, argv[msgFlag + 1])
    : join(target, "messages");
  const scanRoot = msgFlag >= 0 ? target : REPO_ROOT;
  void flags;

  const catalog = catalogs(messagesDir);
  const refs = references(sources(target), scanRoot);

  const missing = [];
  const dynamic = [];
  for (const ref of refs) {
    if (ref.key.includes("${")) {
      // 动态 key：取 `${` 之前的静态前缀，两侧各要至少一个候选。
      const prefix = ref.key.slice(0, ref.key.indexOf("${"));
      const absent = LOCALES.filter(
        (l) => !Object.keys(catalog[l]).some((k) => k.startsWith(prefix) && k !== prefix),
      );
      const row = { ...ref, prefix, absent_in: absent };
      dynamic.push(row);
      if (prefix === "" || absent.length > 0) missing.push(row);
      continue;
    }
    const absent = LOCALES.filter((l) => !(ref.key in catalog[l]));
    if (absent.length > 0) missing.push({ ...ref, absent_in: absent });
  }

  const referencedKeys = new Set(refs.map((r) => r.key));
  const dynamicPrefixes = dynamic.map((d) => d.prefix).filter(Boolean);
  const unused = Object.keys(catalog.zh)
    .filter((k) => !k.startsWith("_") && !referencedKeys.has(k))
    .filter((k) => !dynamicPrefixes.some((p) => k.startsWith(p)))   // 动态前缀下的键算被引用
    .sort();

  const report = {
    schema: SCHEMA,
    scanned_files: sources(target).length,
    referenced: refs.length,
    unique_keys: referencedKeys.size,
    references: refs,
    dynamic,
    missing,
    unused,
  };

  if (asJson) {
    console.log(JSON.stringify(report, null, 2));
    return missing.length > 0 ? 1 : 0;
  }

  console.log(`扫描 ${report.scanned_files} 个源文件（测试文件不算）；`
    + `t() 引用 ${report.referenced} 处 / ${report.unique_keys} 个不同 key`);
  console.log(`动态 key（按前缀判）：${dynamic.length} 处 —— `
    + `${dynamic.map((d) => d.prefix + "*").join("、") || "无"}`);
  console.log(`定义了但没被引用的键：${unused.length} 个（只报不判红，属清理线索）`);
  if (unused.length > 0) console.log(`    ${unused.slice(0, 12).join("、")}`);

  if (missing.length === 0) {
    console.log("每个被引用的 key 在 zh 与 en 里都有定义。");
    return 0;
  }
  console.error(`\n引用了却没有定义的 key ${missing.length} 处：`);
  for (const row of missing) {
    console.error(`    ✗ ${row.file}:${row.line}  ${row.key}  —— ${row.absent_in.join(" / ")} 里没有`);
  }
  console.error("用户看到的就是这几个字符串本身（t() 缺键返回 key，DEC-009 有意为之）。");
  return 1;
}

// `process.exitCode`，不是 `process.exit()`：后者不等 stdout 排空就退。stdout 接的是管道时
// （pytest 的 `capture_output`），macOS 上超过 64KB 的那一截会被直接丢掉——`--json` 的报告
// 在 65536 字节处断开，读的人拿到半截 JSON（`CHAIN-UI-01-a` 加了 6 个键之后实测撞上）。
process.exitCode = main(process.argv.slice(2));
