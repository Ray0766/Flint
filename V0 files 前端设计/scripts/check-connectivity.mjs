#!/usr/bin/env node
// 连通性检查 · 可重复跑 · 零依赖（node 原生 fetch）
//
//   pnpm check:api                      # 用 .env.local 的 NEXT_PUBLIC_FLINT_API
//   FLINT_API=http://127.0.0.1:8000 pnpm check:api
//
// 做三件事：
//   ① 打真端点，断言**关键字段存在**（不是断言值——值是后端的事，会变）；
//   ② 顺带做一次 CORS 预检，确认 v0 前端源（:3001）跨源取得到；
//   ③ 把边缘态（404 / 400 / 409 / 503 / 空态）当作**期望结果**来断言——
//      诚实态必须真能被触发，否则前端等于没接。
// 任一断言失败 → exit 1。NEVER 因为"看起来能跑"就放过。

import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

function envFromFile() {
  const path = resolve(ROOT, ".env.local");
  if (!existsSync(path)) return {};
  const out = {};
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m) out[m[1]] = m[2];
  }
  return out;
}

const fileEnv = envFromFile();
const BASE = (
  process.env.FLINT_API ||
  process.env.NEXT_PUBLIC_FLINT_API ||
  fileEnv.NEXT_PUBLIC_FLINT_API ||
  "http://localhost:8000"
).replace(/\/+$/, "");
const USER = process.env.NEXT_PUBLIC_FLINT_USER_ID || fileEnv.NEXT_PUBLIC_FLINT_USER_ID || "demo-user";
const ORIGIN = process.env.FLINT_WEB_ORIGIN || "http://localhost:3001";
const DAY = process.env.FLINT_DEMO_DAY || "2026-07-04";
const EMPTY_DAY = process.env.FLINT_EMPTY_DAY || "2020-01-01";

// 边缘态样本的缺省 id。都是**后端真产物**，各有可重复的重建命令：
//   verdict（D_insufficient + unknown 竞品）→ python -m harness.gate1_live replay-qwen（零联网回放）
//   报告 Block 树（含 blocking / 保护 / 争议）→ python -m harness.demo_seed_report
// 缺样本 → 该组断言**跳过并打出重建命令**，NEVER 当成通过。
const VERDICT_JOB = process.env.FLINT_VERDICT_JOB || "job-gate1-live-qwen";
const DELIVERABLE = process.env.FLINT_DELIVERABLE || "del-demo-fixture-report";
const REBUILD = {
  verdict: "python -m harness.gate1_live replay-qwen",
  deliverable: "python -m harness.demo_seed_report",
};

let pass = 0;
const failures = [];

function ok(name, extra = "") {
  pass += 1;
  console.log(`  ✓ ${name}${extra ? ` — ${extra}` : ""}`);
}
function fail(name, why) {
  failures.push(`${name}: ${why}`);
  console.log(`  ✗ ${name} — ${why}`);
}
function check(name, cond, why) {
  if (cond) ok(name);
  else fail(name, why);
}

// GET /jobs/{id} 与 SSE 有权限矩阵（审6）：调用者须是 initiated_by 本人或 owner_scope 成员。
// 库里的样板 job 多由 u-owner 发起，故字段断言用「该 job 的持有者」身份发；
// 403 越权态另用 demo-user 身份对 FLINT_FOREIGN_JOB 单独断言。
const JOB_USER = process.env.FLINT_JOB_USER || USER;

async function get(path, init = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "x-user-id": USER, ...(init.headers ?? {}) },
  });
  let body = null;
  const text = await res.text();
  try {
    body = JSON.parse(text);
  } catch {
    body = text;
  }
  return { status: res.status, body, headers: res.headers };
}

const has = (obj, key) => obj !== null && typeof obj === "object" && key in obj;

// ── 0 · 后端在不在 ────────────────────────────────────────────────
async function backendUp() {
  try {
    await fetch(`${BASE}/plaza/hot?day=${DAY}`, { headers: { "x-user-id": USER } });
    return true;
  } catch (err) {
    console.error(`\n后端不可达：${BASE}\n  ${err.message}`);
    console.error(`  先起后端：python -m harness.demo_server（FLINT_DEMO_DSN 指向本地 PG）`);
    return false;
  }
}

// ── 1 · CORS：v0 前端源跨源取 ────────────────────────────────────
async function checkCors() {
  console.log("\n[1] CORS · v0 前端源跨源");
  const res = await fetch(`${BASE}/plaza/hot?day=${DAY}`, {
    method: "OPTIONS",
    headers: {
      Origin: ORIGIN,
      "Access-Control-Request-Method": "GET",
      "Access-Control-Request-Headers": "x-user-id",
    },
  });
  const allow = res.headers.get("access-control-allow-origin");
  check(
    `预检放行 ${ORIGIN}`,
    res.status < 400 && (allow === "*" || allow === ORIGIN),
    `status=${res.status} access-control-allow-origin=${allow}`,
  );
  const simple = await fetch(`${BASE}/plaza/hot?day=${DAY}`, {
    headers: { Origin: ORIGIN, "x-user-id": USER },
  });
  check(
    "实际 GET 带 CORS 头",
    simple.headers.get("access-control-allow-origin") !== null,
    "响应缺 access-control-allow-origin",
  );
}

// 演示库与测试库是同一个 PG，跑测试/ingest 回放会把热度窗口整体挪走。
// 故不硬钉某一天：从 FLINT_DEMO_DAY 起向前找最多 45 天，取第一个有簇的日子。
let RESOLVED_DAY = DAY;
async function resolveDay() {
  const start = new Date(`${DAY}T00:00:00Z`);
  for (let i = 0; i < 45; i += 1) {
    const d = new Date(start.getTime() - i * 86400000).toISOString().slice(0, 10);
    const res = await get(`/plaza/hot?day=${d}`);
    if (res.status === 200 && (res.body?.clusters?.length ?? 0) > 0) {
      RESOLVED_DAY = d;
      if (d !== DAY) console.log(`  · ${DAY} 无簇，回退到最近有数据的一天：${d}`);
      return d;
    }
  }
  return null;
}

// ── 2 · GET /plaza/hot ───────────────────────────────────────────
async function checkPlaza() {
  console.log("\n[2] GET /plaza/hot");
  const day = await resolveDay();
  if (day === null) {
    fail("找得到有簇的一天", `从 ${DAY} 起回看 45 天都为空——库里没有热点数据`);
    return null;
  }
  const { status, body } = await get(`/plaza/hot?day=${day}`);
  check("200", status === 200, `status=${status}`);
  check("有 day / clusters / weak_signals", has(body, "day") && Array.isArray(body?.clusters) && Array.isArray(body?.weak_signals), JSON.stringify(body)?.slice(0, 160));
  if (Array.isArray(body?.clusters) && body.clusters.length > 0) {
    const c = body.clusters[0];
    for (const k of ["cluster_id", "canonical_name", "category_id", "status", "by_source", "total_heat", "hotness", "hotness_components"]) {
      check(`cluster.${k} 在场`, has(c, k), `缺 ${k}`);
    }
    for (const k of ["velocity", "accel", "cross_count", "multi_boost", "novelty_factor", "decay"]) {
      check(`hotness_components.${k} 在场`, has(c.hotness_components, k), `缺 ${k}`);
    }
    ok("by_source 源键", `实际 ${Object.keys(c.by_source).join("/") || "（空）"}`);
    ok("本次使用的演示日", RESOLVED_DAY);
    return c.cluster_id;
  }
  fail("当日有簇", `${RESOLVED_DAY} clusters 为空`);
  return null;
}

// ── 3 · 边缘态：空态日 + 非法 day ────────────────────────────────
async function checkPlazaEdges() {
  console.log("\n[3] 边缘态 · 广场空态 / 参数非法");
  const empty = await get(`/plaza/hot?day=${EMPTY_DAY}`);
  check(
    `空态日 ${EMPTY_DAY} → 200 + 空数组（非 404/500）`,
    empty.status === 200 && empty.body?.clusters?.length === 0 && empty.body?.weak_signals?.length === 0,
    `status=${empty.status}`,
  );
  const bad = await get("/plaza/hot?day=not-a-date");
  check(
    "非法 day → 400 VALIDATION_FAILED",
    bad.status === 400 && bad.body?.code === "VALIDATION_FAILED",
    `status=${bad.status} code=${bad.body?.code}`,
  );
}

// ── 4 · GET /clusters/{id}/evidence-cards ────────────────────────
async function checkEvidence(clusterId) {
  console.log("\n[4] GET /clusters/{id}/evidence-cards");
  if (clusterId === null) return fail("证据卡", "上一步没拿到 cluster_id");
  const { status, body } = await get(`/clusters/${encodeURIComponent(clusterId)}/evidence-cards`);
  check("200", status === 200, `status=${status}`);
  check("有 cluster_id / evidence_cards", has(body, "cluster_id") && Array.isArray(body?.evidence_cards), "字段缺失");
  if (body?.evidence_cards?.length > 0) {
    const card = body.evidence_cards[0];
    for (const k of ["card_id", "cluster_id", "keyword_ids", "flags", "top_links"]) {
      check(`card.${k} 在场`, has(card, k), `缺 ${k}`);
    }
  }
  const unknown = await get("/clusters/c-does-not-exist/evidence-cards");
  check(
    "未知簇 → 200 + 空列表（非 404）",
    unknown.status === 200 && unknown.body?.evidence_cards?.length === 0,
    `status=${unknown.status}`,
  );
}

// ── 5 · GET /jobs/{id}/verdict（含 D_insufficient 诚实态） ───────
async function checkVerdict() {
  console.log("\n[5] GET /jobs/{id}/verdict");
  const jobId = VERDICT_JOB;
  const probe = await get(`/jobs/${encodeURIComponent(jobId)}/verdict`);
  if (probe.status === 404) {
    console.log(`  · 样本 ${jobId} 不在库，跳过判定断言。重建：${REBUILD.verdict}`);
  } else {
    const { status, body } = probe;
    check("200", status === 200, `status=${status}`);
    check("有 job_id / verdict", has(body, "job_id") && has(body, "verdict"), "字段缺失");
    const v = body?.verdict ?? {};
    check(
      "verdict ∈ 四档",
      ["A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"].includes(v.verdict),
      `verdict=${v.verdict}`,
    );
    if (v.verdict === "D_insufficient") {
      check("D 档必带非空 gaps（审8）", Array.isArray(v.gaps) && v.gaps.length > 0, `gaps=${JSON.stringify(v.gaps)}`);
      for (const g of v.gaps ?? []) {
        check(
          `gap.cause ∈ {missing_data, missing_permission}`,
          ["missing_data", "missing_permission"].includes(g.cause),
          `cause=${g.cause}`,
        );
      }
      const unknowns = (v.competitors ?? []).filter((c) => c.strength === "unknown");
      ok("unknown 竞品计数", `${unknowns.length} / ${(v.competitors ?? []).length}`);
    }
    const strengths = new Set((v.competitors ?? []).map((c) => c.strength));
    for (const s of strengths) {
      check(
        `competitor.strength "${s}" 在 TS 镜像四值内`,
        ["strong", "moderate", "weak", "unknown"].includes(s),
        `未知强度值 ${s}——契约镜像漏支`,
      );
    }
  }
  const missing = await get("/jobs/job-does-not-exist/verdict");
  check(
    "未就绪 job → 404 NOT_FOUND",
    missing.status === 404 && missing.body?.code === "NOT_FOUND",
    `status=${missing.status} code=${missing.body?.code}`,
  );
}

// ── 6 · GET /jobs/{id} 快照 + SSE 端点可达 ───────────────────────
async function checkJob() {
  console.log("\n[6] GET /jobs/{id} 快照 · SSE");
  const jobId = process.env.FLINT_JOB;
  if (!jobId) {
    console.log("  · 未设 FLINT_JOB，跳过快照字段断言（只验 404 / 403 语义）");
  } else {
    const { status, body } = await get(`/jobs/${encodeURIComponent(jobId)}`, {
      headers: { "x-user-id": JOB_USER },
    });
    check("200", status === 200, `status=${status}（身份 ${JOB_USER}；越权改 FLINT_JOB_USER）`);
    for (const k of ["job_id", "kind", "project_id", "state", "progress", "partial_output_ref", "budget", "cost_accum", "error", "created_at", "updated_at"]) {
      check(`job.${k} 在场`, has(body, k), `缺 ${k}`);
    }
    check(
      "state ∈ 冻结件八值",
      ["queued", "retrieving", "judging", "drafting", "validating", "done", "failed", "cancelled"].includes(body?.state),
      `state=${body?.state}`,
    );
  }
  const missing = await get("/jobs/job-does-not-exist");
  check("未知 job → 404", missing.status === 404, `status=${missing.status}`);

  // 越权：他人发起的 job → 403 PERMISSION_DENIED（诚实态，不是"没数据"）
  const foreign = process.env.FLINT_FOREIGN_JOB;
  if (foreign) {
    const res = await get(`/jobs/${encodeURIComponent(foreign)}`);
    check(
      "他人 job → 403 PERMISSION_DENIED",
      res.status === 403 && res.body?.code === "PERMISSION_DENIED",
      `status=${res.status} code=${res.body?.code}`,
    );
  } else {
    console.log("  · 未设 FLINT_FOREIGN_JOB，跳过 403 越权断言");
  }

  // SSE：真订阅一次，确认 text/event-stream + 至少一条 id/data（终态 job 会重放后关流）
  if (jobId) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 8000);
    try {
      const res = await fetch(`${BASE}/jobs/${encodeURIComponent(jobId)}/events`, {
        headers: { "x-user-id": JOB_USER, accept: "text/event-stream" },
        signal: ctrl.signal,
      });
      check(
        "SSE content-type = text/event-stream",
        (res.headers.get("content-type") ?? "").includes("text/event-stream"),
        `content-type=${res.headers.get("content-type")}`,
      );
      let buf = "";
      for await (const chunk of res.body) {
        buf += Buffer.from(chunk).toString("utf8");
        if (buf.includes("data:")) break;
      }
      check("SSE 收到至少一条 data 帧", buf.includes("data:"), `收到 ${buf.length} 字节`);
      const idLine = /^id:\s*(\d+)/m.exec(buf);
      check("SSE 帧带 id（= seq，供 Last-Event-ID 续订）", idLine !== null, buf.slice(0, 120));
      const dataLine = /^data:\s*(.+)$/m.exec(buf);
      if (dataLine) {
        const payload = JSON.parse(dataLine[1]);
        check(
          "SSE payload.kind ∈ 冻结件四支",
          ["status", "step", "partial_block", "failed"].includes(payload.kind),
          `kind=${payload.kind}`,
        );
      }
    } catch (err) {
      if (err.name === "AbortError") fail("SSE 8s 内无帧", "订阅超时");
      else fail("SSE 订阅", err.message);
    } finally {
      clearTimeout(timer);
      ctrl.abort();
    }
  }
}

// ── 7 · GET /deliverables/{id}/blocks（+ 导出门禁 409/503） ──────
async function checkDeliverable() {
  console.log("\n[7] GET /deliverables/{id}/blocks · 导出门禁");
  const missing = await get("/deliverables/does-not-exist/blocks");
  check(
    "未生成 → 404 NOT_FOUND（端点已挂载，不是 404 路由）",
    missing.status === 404 && missing.body?.code === "NOT_FOUND",
    `status=${missing.status} body=${JSON.stringify(missing.body)?.slice(0, 120)}`,
  );

  const id = DELIVERABLE;
  const probe = await get(`/deliverables/${encodeURIComponent(id)}/blocks`);
  if (probe.status === 404) {
    console.log(`  · 样本 ${id} 不在库，跳过 Block 树与导出门禁断言。重建：${REBUILD.deliverable}`);
    return;
  }
  const { status, body } = probe;
  check("200", status === 200, `status=${status}`);
  check("有 deliverable_id / blocks", has(body, "deliverable_id") && Array.isArray(body?.blocks), "字段缺失");
  const blocks = body?.blocks ?? [];
  for (const b of blocks.slice(0, 1)) {
    for (const k of ["block_id", "deliverable_id", "section_id", "order", "type", "content", "claim_ids", "fact_ids", "author", "revision", "locked", "user_modified", "needs_review", "review_reason", "review_severity"]) {
      check(`block.${k} 在场`, has(b, k), `缺 ${k}`);
    }
  }
  const kinds = new Set(blocks.map((b) => b?.content?.kind));
  const KNOWN = ["heading", "paragraph", "table", "chart", "declaration", "quality_card", "citation_list", "gap_notice"];
  for (const k of kinds) {
    check(`content.kind "${k}" 在 8 支判别联合内`, KNOWN.includes(k), `未知 kind ${k}`);
  }
  const protectedBlocks = blocks.filter((b) => b.locked || b.author === "user" || b.user_modified);
  ok("保护块（locked ∨ author==user ∨ user_modified）", `${protectedBlocks.length} / ${blocks.length}`);
  const blocking = blocks.filter((b) => b.review_severity === "blocking");
  ok("blocking 复核块", `${blocking.length}`);
  const disputed = blocks.filter(
    (b) => b?.content?.kind === "paragraph" && (b.content.spans ?? []).some((s) => s.kind === "claim" && s.disputed_mark),
  );
  ok("disputed claim 块", `${disputed.length}`);

  // 导出门禁：有 blocking → markdown 必须 409；无 blocking → 必须 200
  const md = await get(`/deliverables/${encodeURIComponent(id)}/render?fmt=markdown`);
  if (blocking.length > 0) {
    check(
      "存在 blocking → markdown 导出 409 EXPORT_BLOCKED",
      md.status === 409 && md.body?.code === "EXPORT_BLOCKED",
      `status=${md.status} code=${md.body?.code}`,
    );
    check(
      "409 携 detail.blocking_block_ids",
      Array.isArray(md.body?.detail?.blocking_block_ids) && md.body.detail.blocking_block_ids.length > 0,
      JSON.stringify(md.body?.detail),
    );
  } else {
    check("无 blocking → markdown 导出 200", md.status === 200, `status=${md.status}`);
  }

  // pack builder 未接线 → 503（E6 姿态：明说不可用）
  const pack = await get(`/deliverables/${encodeURIComponent(id)}/render?fmt=pack`);
  check(
    "fmt=pack → 503 SERVICE_UNAVAILABLE（builder 未接线）",
    pack.status === 503 && pack.body?.code === "SERVICE_UNAVAILABLE",
    `status=${pack.status} code=${pack.body?.code}`,
  );

  // pdf：GTK 就绪则 200/409，未就绪则 503。两种都是诚实态，只断言"不是 500"。
  const pdf = await get(`/deliverables/${encodeURIComponent(id)}/render?fmt=pdf`);
  check("fmt=pdf 有明确态（非 5xx 崩溃）", [200, 409, 503].includes(pdf.status), `status=${pdf.status}`);
  ok("pdf 实际态", `${pdf.status}${pdf.body?.code ? ` ${pdf.body.code}` : ""}`);
}

// ── main ─────────────────────────────────────────────────────────
console.log(`Flint v0 前端 · 连通性检查`);
console.log(`  API_BASE = ${BASE}`);
console.log(`  Origin   = ${ORIGIN}   X-User-Id = ${USER}   day = ${DAY}`);

if (!(await backendUp())) process.exit(1);

await checkCors();
const clusterId = await checkPlaza();
await checkPlazaEdges();
await checkEvidence(clusterId);
await checkVerdict();
await checkJob();
await checkDeliverable();

console.log(`\n通过 ${pass} 项，失败 ${failures.length} 项。`);
if (failures.length > 0) {
  console.log("\n失败明细：");
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}
process.exit(0);
