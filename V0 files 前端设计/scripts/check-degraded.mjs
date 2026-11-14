#!/usr/bin/env node
// 坏链路诚实态验证 · 可重复跑
//
// 压两件事：后端**回 5xx** 与后端**根本连不上**。两者必须是两种不同的、说得清的屏，
// 而不是空白页、不是"该日无热点"、更不是退回 mock。
//
// 跑法（两轮，各起一次前端；.next 有单实例锁，故不能并行）：
//   ① 5xx：  node scripts/stub-backend.mjs 500          （另开一个窗口，:8010）
//            $env:NEXT_PUBLIC_FLINT_API='http://localhost:8010'; pnpm exec next dev -p 3001
//            node scripts/check-degraded.mjs 500
//   ② 不可达：$env:NEXT_PUBLIC_FLINT_API='http://localhost:8099'; pnpm exec next dev -p 3001
//            node scripts/check-degraded.mjs down

const WEB = (process.env.FLINT_WEB || "http://localhost:3001").replace(/\/+$/, "");
const MODE = process.argv[2] || "500";

let pass = 0;
const failures = [];
const ok = (n) => {
  pass += 1;
  console.log(`  ✓ ${n}`);
};
const fail = (n, why) => {
  failures.push(`${n}: ${why}`);
  console.log(`  ✗ ${n} — ${why}`);
};

function normalize(html) {
  const body = /<body[^>]*>([\s\S]*)<\/body>/i.exec(html);
  return (body ? body[1] : html)
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<!--[\s\S]*?-->/g, "");
}

async function page(path) {
  const res = await fetch(`${WEB}${path}`);
  return { status: res.status, html: normalize(await res.text()) };
}

const seen = (n, html, needle) =>
  html.includes(needle) ? ok(n) : fail(n, `找不到「${needle}」`);
const unseen = (n, html, needle) =>
  !html.includes(needle) ? ok(n) : fail(n, `不该出现「${needle}」，但出现了`);

const PATHS = ["/plaza", "/deliverables/del-demo-fixture-report", "/gate/job-any"];

console.log(`Flint v0 前端 · 坏链路诚实态（模式 ${MODE}）`);
console.log(`  WEB = ${WEB}`);

for (const path of PATHS) {
  console.log(`\n${path}`);
  const p = await page(path);
  ok(`HTTP ${p.status}（页面本身没崩）`);
  if (MODE === "500") {
    seen("显 5xx 状态码", p.html, "500 ·");
    seen("点名后端内部出错", p.html, "后端内部出错");
    unseen("不冒充空态", p.html, "该日无热点");
    unseen("不冒充「尚未生成」", p.html, "该交付物尚未生成");
  } else {
    seen("显「后端不可达」", p.html, "后端不可达");
    seen("点名 API_BASE（连的是谁）", p.html, "API_BASE ·");
    seen("说明这不是空数据", p.html, "这不是空数据");
    unseen("不冒充空态", p.html, "该日无热点");
    unseen("不冒充「尚未生成」", p.html, "该交付物尚未生成");
  }
}

console.log(`\n通过 ${pass} 项，失败 ${failures.length} 项。`);
if (failures.length > 0) {
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}
process.exit(0);
