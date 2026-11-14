#!/usr/bin/env node
// 故障注入桩后端 · 只为压测前端的两种"坏链路"诚实态，NEVER 参与正常演示。
//
//   node scripts/stub-backend.mjs 500   # 一律回 500（压 5xx 诚实态）
//   node scripts/stub-backend.mjs 503   # 一律回 503 契约错误体
//
// 配合：
//   $env:NEXT_PUBLIC_FLINT_API='http://localhost:8010'; pnpm exec next dev -p 3002
// 「后端不可达」态不需要桩：把 NEXT_PUBLIC_FLINT_API 指向一个没人监听的端口即可。

import { createServer } from "node:http";

const MODE = process.argv[2] || "500";
const PORT = Number(process.env.STUB_PORT || 8010);

const BODIES = {
  500: { status: 500, body: null }, // 裸 5xx：连错误体都没有（最难看的那种）
  503: {
    status: 503,
    body: { code: "SERVICE_UNAVAILABLE", message: "桩后端：依赖不可用" },
  },
};

const conf = BODIES[MODE];
if (!conf) {
  console.error(`unknown mode: ${MODE}（可用：${Object.keys(BODIES).join(", ")}）`);
  process.exit(2);
}

createServer((req, res) => {
  const headers = {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "*",
    "access-control-allow-methods": "*",
  };
  if (req.method === "OPTIONS") {
    res.writeHead(204, headers);
    return res.end();
  }
  console.log(`  stub ${MODE} ← ${req.method} ${req.url}`);
  if (conf.body === null) {
    res.writeHead(conf.status, { ...headers, "content-type": "text/plain" });
    return res.end("Internal Server Error");
  }
  res.writeHead(conf.status, { ...headers, "content-type": "application/json" });
  res.end(JSON.stringify(conf.body));
}).listen(PORT, () => console.log(`stub backend (${MODE}) on http://localhost:${PORT}`));
