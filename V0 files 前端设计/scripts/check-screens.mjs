#!/usr/bin/env node
// 边缘态渲染验证 · 可重复跑
//
// 前一支（check-connectivity）证"后端确实回了这些诚实态"；本支证"前端确实把它们渲染出来了"。
// 做法：抓 Next 服务端渲染出的 HTML，断言诚实态的**可见文案与字段**真的在页面里。
// 这不是截图，但比截图可复核：断言写死在这里，谁跑都一样，回归即报错。
//
//   pnpm exec node scripts/check-screens.mjs
//   FLINT_WEB=http://localhost:3001 FLINT_API=http://localhost:8000 ...
//
// 前置：后端 :8000 起着；前端 :3001 起着；样本齐（见 check-connectivity 的重建命令）。

const WEB = (process.env.FLINT_WEB || "http://localhost:3001").replace(/\/+$/, "");
const API = (process.env.FLINT_API || "http://localhost:8000").replace(/\/+$/, "");
const VERDICT_JOB = process.env.FLINT_VERDICT_JOB || "job-gate1-live-qwen";
const DELIVERABLE = process.env.FLINT_DELIVERABLE || "del-demo-fixture-report";
const EMPTY_DAY = process.env.FLINT_EMPTY_DAY || "2020-01-01";

let pass = 0;
const failures = [];
const ok = (n, extra = "") => {
  pass += 1;
  console.log(`  ✓ ${n}${extra ? ` — ${extra}` : ""}`);
};
const fail = (n, why) => {
  failures.push(`${n}: ${why}`);
  console.log(`  ✗ ${n} — ${why}`);
};

async function page(path) {
  const res = await fetch(`${WEB}${path}`, { headers: { "accept-language": "zh-CN" } });
  const raw = await res.text();
  return { status: res.status, html: normalize(raw), raw };
}

// 断言只针对**屏上真渲染的标记**：
//   - 只取 <body>；<head> 的 metadata 不是呈现内容；
//   - 剥掉 <script>/<style>（body 里的 RSC flight 载荷会把 metadata 字符串又带进来一次）；
//   - 抹掉 React SSR 在相邻文本节点间插的 <!-- -->，否则 `gaps（{n}）` 会被切成三段而误判。
function normalize(html) {
  const body = /<body[^>]*>([\s\S]*)<\/body>/i.exec(html);
  return (body ? body[1] : html)
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<!--[\s\S]*?-->/g, "");
}

// HTML 里断言可见文案。Next 会把中文原样输出（无实体转义），直接 includes 即可。
function seen(name, html, needle) {
  if (html.includes(needle)) ok(name);
  else fail(name, `页面里找不到「${needle}」`);
}
function unseen(name, html, needle) {
  if (!html.includes(needle)) ok(name);
  else fail(name, `页面里**不该**出现「${needle}」，但出现了`);
}

async function liveDay() {
  const start = new Date(`${process.env.FLINT_DEMO_DAY || "2026-07-04"}T00:00:00Z`);
  for (let i = 0; i < 45; i += 1) {
    const d = new Date(start.getTime() - i * 86400000).toISOString().slice(0, 10);
    const res = await fetch(`${API}/plaza/hot?day=${d}`, { headers: { "x-user-id": "demo-user" } });
    if (res.ok) {
      const body = await res.json();
      if ((body.clusters?.length ?? 0) > 0) return { day: d, first: body.clusters[0] };
    }
  }
  return null;
}

// ── 批次一新增：S0 外壳 / P1 排序与筛选 / P2 工作台 / P3 combo ──────
async function screenShellAndBatchOne() {
  console.log("\n[5] 批次一 · S0 外壳 / P1 排序 / P2 工作台 / P3 combo");

  const live = await liveDay();
  if (live === null) return fail("批次一", "后端 45 天内无热点数据");

  // S0 外壳：真目录 + 用户位占位（NEVER 硬编码大类）
  const catsRes = await fetch(`${API}/categories`, { headers: { "x-user-id": "demo-user" } });
  if (!catsRes.ok) return fail("S0 大类目录", `GET /categories → ${catsRes.status}`);
  const cats = await catsRes.json();
  const p = await page(`/plaza?day=${live.day}`);
  seen("S0 wordmark 在场", p.html, "Flint 燧石");
  seen("S0 用户位标明账户端点未建", p.html, "账户端点未建");
  seen("S0 大类来自真端点", p.html, "GET /categories");
  if (cats.length > 0) seen(`S0 渲染真大类名（${cats[0].name}）`, p.html, cats[0].name);

  // P1 主榜序 = 后端序：逐一比对页面上 cluster_id 的出现次序
  const apiRes = await fetch(`${API}/plaza/hot?day=${live.day}`, {
    headers: { "x-user-id": "demo-user" },
  });
  const apiBody = await apiRes.json();
  const backendOrder = apiBody.clusters.map((c) => c.cluster_id);
  const idRe = /c-\d{8}-\d{3}/g;
  const shown = [...new Set(p.html.match(idRe) ?? [])];
  const shownMain = shown.filter((id) => backendOrder.includes(id));
  const sameOrder =
    shownMain.length === backendOrder.length &&
    shownMain.every((id, i) => id === backendOrder[i]);
  if (sameOrder) ok("P1 主榜序与后端逐一致（前端零重排）", `${backendOrder.length} 簇`);
  else fail("P1 主榜序", "页面 cluster_id 次序与后端返回次序不一致");
  unseen("P1 无排序控件（不出现『按热度排序』一类）", p.html, "排序方式");
  seen("P1 弱信号单列一轨", p.html, "弱信号轨 weak_signals");
  seen("P1 弱信号不并入综合分", p.html, "不并入综合分");

  // P1 筛选：仅隐藏行，不重排（用一个真实存在的 category_id）
  const someCat = apiBody.clusters[0]?.category_id;
  if (someCat) {
    const f = await page(`/plaza?day=${live.day}&cat=${someCat}`);
    const fShown = [...new Set(f.html.match(idRe) ?? [])].filter((id) =>
      backendOrder.includes(id),
    );
    const expect = apiBody.clusters
      .filter((c) => c.category_id === someCat)
      .map((c) => c.cluster_id);
    const filterOk =
      fShown.length === expect.length && fShown.every((id, i) => id === expect[i]);
    if (filterOk) ok("P1 筛选仅隐藏行、次序不变", `${expect.length} 行`);
    else fail("P1 筛选", "筛选后次序与后端子序列不一致（疑似重排）");
  }

  // P2 工作台：flags 各自可辨 + top_links 可点 + 未知簇为空态非 404
  const cardsRes = await fetch(`${API}/clusters/${live.first.cluster_id}/evidence-cards`, {
    headers: { "x-user-id": "demo-user" },
  });
  const cardsBody = await cardsRes.json();
  const wb = await page(`/clusters/${live.first.cluster_id}`);
  seen("P2 200 且渲染", wb.html, "工作台");
  if (cardsBody.evidence_cards.length > 0) {
    const c0 = cardsBody.evidence_cards[0];
    seen("P2 card_id 上屏", wb.html, c0.card_id);
    for (const fl of c0.flags ?? []) {
      // 三种旗标各自带中文标签，NEVER 合并成统一标签
      const label = { novelty: "novelty · 新奇", momentum: "momentum · 动量", revival: "revival · 复燃" }[fl];
      if (label) seen(`P2 旗标各自可辨（${fl}）`, wb.html, label);
    }
    if ((c0.top_links ?? []).length > 0) {
      seen("P2 top_links 可点（真实 href）", wb.html, `href="${c0.top_links[0]}"`);
    }
  }
  const unknown = await page("/clusters/c-unknown-999");
  if (unknown.status === 200) ok("P2 未知簇 HTTP 200（不是 404）");
  else fail("P2 未知簇", `期望 200 空态，实际 ${unknown.status}`);
  seen("P2 未知簇渲染为空态", unknown.html, "该簇暂无证据卡");
  unseen("P2 未知簇不渲染成错误页", unknown.html, "后端内部出错");

  // P3 combo：校验规则上屏 + 提交禁用 + degraded 文案在场
  const cb = await page("/combo/new");
  seen("P3 200 且渲染", cb.html, "combo · 跨簇关联");
  seen("P3 选卡区间规则上屏", cb.html, "需 2~5 张");
  seen("P3 未满足时提交禁用", cb.html, "disabled");
  seen("P3 不画百分比进度", cb.html, "后端没有进度数据");
}

// ── 批次二：P4 主题列表 / P5 主题详情 / P6 发起分析 / P7 SSE / P8 判定 ────
// 环境变量：FLINT_PROJECT（真 project_id）· FLINT_TOPIC（真 topic_id）
//   缺省时自动跳过并**明确报为跳过**，NEVER 当通过。
async function screenTopicAndJob() {
  console.log("\n[6] 批次二 · P4/P5/P6 主题层 + P7/P8 作业与判定");

  const projectId = process.env.FLINT_PROJECT;
  const topicId = process.env.FLINT_TOPIC;

  if (!projectId || !topicId) {
    return fail(
      "P4/P5/P6 主题层",
      "缺 FLINT_PROJECT / FLINT_TOPIC（重建：经 demo 后端 POST /projects/combo）",
    );
  }

  // —— P4 主题列表 ——
  const apiTopics = await (
    await fetch(`${API}/projects/${projectId}/topics`, { headers: { "x-user-id": "demo-user" } })
  ).json();
  if ((apiTopics.topics?.length ?? 0) === 0) {
    return fail(
      "P4 主题列表",
      `project ${projectId} 无主题（库被清空？重建：经 demo 后端 POST /projects/combo）`,
    );
  }
  const p4 = await page(`/projects/${projectId}/topics`);
  seen("P4 200 且渲染", p4.html, "候选主题");
  seen("P4 project_id 上屏", p4.html, projectId);
  if (apiTopics.topics.length > 0) {
    seen("P4 真 one_liner 上屏", p4.html, apiTopics.topics[0].one_liner);
    seen("P4 topic_id 上屏", p4.html, apiTopics.topics[0].topic_id);
  }
  // chosen_topic_id 直取后端：null 时必须如实写 null，NEVER 挑一个当选中
  if (apiTopics.chosen_topic_id === null) {
    seen("P4 chosen_topic_id 为 null 时如实标注", p4.html, "null（尚未选主题）");
    unseen("P4 未选主题时不出现选中徽记", p4.html, "chosen_topic_id</span>");
  }
  // 清单 13：speculative 主题必须抑制溯源入口
  const specTopics = apiTopics.topics.filter((t) => t.why_now.speculative);
  if (specTopics.length > 0) {
    seen("P4 推测态标注", p4.html, "推测 · 未经证据对齐");
    seen("P4 推测态抑制溯源入口", p4.html, "不提供溯源入口");
  } else {
    ok("P4 本批真数据无 speculative 主题（分支未被实屏验证，已如实登记）");
  }

  // 未知 project → 空数组（非 404）
  const p4empty = await page("/projects/proj-unknown-999/topics");
  if (p4empty.status === 200) ok("P4 未知 project HTTP 200（不是 404）");
  else fail("P4 未知 project", `期望 200 空态，实际 ${p4empty.status}`);
  seen("P4 未知 project 渲染为空态", p4empty.html, "该项目暂无候选主题");

  // —— P5 主题详情 ——
  // 样本不在库时 MUST 明确报为失败并给重建命令，NEVER 崩栈、NEVER 当通过。
  const topicRes = await fetch(`${API}/topics/${topicId}`, {
    headers: { "x-user-id": "demo-user" },
  });
  if (!topicRes.ok) {
    return fail(
      "P5 主题详情",
      `topic ${topicId} 不在库（HTTP ${topicRes.status}；重建：经 demo 后端 POST /projects/combo）`,
    );
  }
  const apiTopic = await topicRes.json();
  const p5 = await page(`/topics/${topicId}`);
  seen("P5 200 且渲染", p5.html, topicId);
  seen("P5 one_liner 上屏", p5.html, apiTopic.topic.one_liner);
  seen("P5 target_user_tag 上屏", p5.html, apiTopic.topic.target_user_tag);
  seen("P5 keyword_mapping 在场", p5.html, "keyword_mapping");
  // 未知 topic → 404（单资源不存在，与 P4 空数组语义不同）
  const p5missing = await page("/topics/topic-unknown-999");
  if (p5missing.status === 404) ok("P5 未知 topic HTTP 404（单资源语义）");
  else fail("P5 未知 topic", `期望 404，实际 ${p5missing.status}`);

  // —— P6 发起分析 ——
  const p6 = await page(`/projects/${projectId}/analysis/new`);
  seen("P6 200 且渲染", p6.html, "发起 Gate① 分析");
  seen("P6 主题单选且无默认", p6.html, "单选，无默认");
  seen("P6 未选时提交禁用", p6.html, "disabled");
  seen("P6 budget_cny 契约必填", p6.html, "budget_cny");
  unseen("P6 不显示任何预计花费", p6.html, "预计花费</");

  // —— P7/P8 由 job 状态决定 ——
  const jobsRes = await fetch(`${API}/jobs/job-gate1-live-qwen/verdict`, {
    headers: { "x-user-id": "demo-user" },
  });
  if (jobsRes.ok) {
    const vb = await jobsRes.json();
    const p8 = await page("/gate/job-gate1-live-qwen");
    seen("P8 verdict 档位直取后端", p8.html, vb.verdict.verdict);
    // 清单 17：constraints_checked 当对象处理
    if (vb.verdict.constraints_checked !== undefined) {
      seen("P8 constraints_checked 按对象展开", p8.html, "constraints_checked");
      seen("P8 gap_count 上屏", p8.html, `gap_count ${vb.verdict.constraints_checked.gap_count}`);
    }
    // 清单 19：unknown 与 weak 不同形并标未知
    const unknowns = (vb.verdict.competitors ?? []).filter((c) => c.strength === "unknown");
    if (unknowns.length > 0) {
      seen("P8 unknown 竞品标「未知」", p8.html, "strength · 未知");
      seen("P8 unknown 用虚线中空（与 weak 不同形）", p8.html, "border-dashed");
      seen("P8 unknown 竞品名上屏", p8.html, unknowns[0].name);
    }
    // 清单 18：两类缺口入口不同
    const gaps = vb.verdict.gaps ?? [];
    if (gaps.some((g) => g.cause === "missing_data")) {
      seen("P8 missing_data 走补充资料入口", p8.html, "缺资料");
    }
    if (gaps.some((g) => g.cause === "missing_permission")) {
      seen("P8 missing_permission 走请授权入口", p8.html, "请 owner 授权");
    } else {
      ok("P8 本批真数据无 missing_permission 缺口（分支未被实屏验证，已如实登记）");
    }
    unseen("P8 判定屏不出现百分比进度", p8.html, "%的进度");
  }

  // P7：非终态 job → SSE 进度屏（清单 14/16）
  const runRes = await fetch(`${API}/jobs/m2005-job`, { headers: { "x-user-id": "demo-user" } });
  if (runRes.ok) {
    const rj = await runRes.json();
    if (!["done", "failed", "cancelled"].includes(rj.state)) {
      const p7 = await page("/gate/m2005-job");
      seen("P7 进度屏渲染", p7.html, "分析进行中");
      seen("P7 state 取自后端", p7.html, rj.state);
      seen("P7 SSE 接线阶段可见", p7.html, "Last-Event-ID");
      seen("P7 去重口径可见", p7.html, "终态自动 close()");
    }
  }

  // 清单 15：failed 显示后端 error 原文
  const failRes = await fetch(`${API}/jobs/m4029-dagfail`, { headers: { "x-user-id": "demo-user" } });
  if (failRes.ok) {
    const fj = await failRes.json();
    if (fj.state === "failed") {
      const pf = await page("/gate/m4029-dagfail");
      seen("failed 屏渲染", pf.html, "分析未能完成");
      if (fj.error) seen("failed 显示后端 error 原文", pf.html, fj.error.slice(0, 24));
      unseen("failed 不假装完成", pf.html, "分析已完成");
    }
  }
}

// ── 批次三：P10 可干预页 / P13 导出面板（清单 D 组 20/21/26/27/28）──────
async function screenIntervenAndExport() {
  console.log("\n[7] 批次三 · P10 可干预页 / P13 导出面板");

  const blocksRes = await fetch(`${API}/deliverables/${DELIVERABLE}/blocks`, {
    headers: { "x-user-id": "demo-user" },
  });
  if (!blocksRes.ok) {
    return fail("P10/P13", `夹具不在库（重建：python -m harness.demo_seed_report）`);
  }
  const tree = await blocksRes.json();
  const isProt = (b) => b.locked || b.author === "user" || b.user_modified;
  const prot = tree.blocks.filter(isProt);
  const unprot = tree.blocks.filter((b) => !isProt(b));
  const blocking = tree.blocks.filter((b) => b.review_severity === "blocking");
  const advisory = tree.blocks.filter((b) => b.review_severity === "advisory");

  // —— P10：门控（清单 20）——
  const p10 = await page(`/deliverables/${DELIVERABLE}/edit?project_id=proj-x`);
  seen("P10 200 且渲染", p10.html, "可干预页");
  ok(`P10 夹具保护块 ${prot.length} / ${tree.blocks.length}`);
  seen("P10 保护块明示控件未渲染", p10.html, "控件未渲染，非置灰");
  for (const b of prot) {
    // 保护块所在片段里 MUST 不出现任何干预控件文案
    const idx = p10.html.indexOf(b.block_id);
    const seg = idx >= 0 ? p10.html.slice(idx, idx + 1200) : "";
    const hasCtl = /重生成本块|>争议<|补证据/.test(seg);
    if (!hasCtl) ok(`P10 保护块 ${b.block_id} 未渲染任何控件`);
    else fail(`P10 保护块 ${b.block_id}`, "受保护却渲染了干预控件");
  }
  if (unprot.length > 0) {
    seen("P10 非保护块渲染控件", p10.html, "重生成本块");
  }
  // 清单 21：两级复核一眼可辨
  if (blocking.length > 0) seen("P10 blocking 标『挡导出』", p10.html, "阻断 · 挡导出");
  if (advisory.length > 0) seen("P10 advisory 标『不挡导出』", p10.html, "提示 · 不挡导出");
  // 无 project_id 时不猜
  const p10np = await page(`/deliverables/${DELIVERABLE}/edit`);
  seen("P10 缺 project_id 时不猜且不渲染控件", p10np.html, "干预端点都需要 project_id");

  // —— P13：导出（清单 21/28）——
  const p13 = await page(`/deliverables/${DELIVERABLE}/export`);
  seen("P13 200 且渲染", p13.html, "能不能导出由后端说了算");
  seen("P13 五格式在场", p13.html, "vibe_pack zip");
  unseen("P13 不预判 409", p13.html, "该格式将被阻断");
  if (blocking.length > 0) {
    seen("P13 块清单标出 blocking", p13.html, "blocking · 挡导出");
    seen("P13 blocking 块 id 在场", p13.html, blocking[0].block_id);
  }
  // 后端真值对照：markdown 应 409、pack/pdf 应 503（前端不预判，这里只核后端事实）
  const mdCode = (await fetch(`${API}/deliverables/${DELIVERABLE}/render?fmt=markdown`)).status;
  const packCode = (await fetch(`${API}/deliverables/${DELIVERABLE}/render?fmt=pack`)).status;
  const pdfCode = (await fetch(`${API}/deliverables/${DELIVERABLE}/render?fmt=pdf`)).status;
  if (mdCode === 409) ok("后端 markdown → 409 EXPORT_BLOCKED（存在 blocking 块）");
  else fail("后端 markdown", `期望 409，实际 ${mdCode}`);
  if (packCode === 503) ok("后端 pack → 503（builder 未接线）");
  else fail("后端 pack", `期望 503，实际 ${packCode}`);
  if (pdfCode === 503) ok("后端 pdf → 503（GTK 缺失）");
  else fail("后端 pdf", `期望 503，实际 ${pdfCode}`);

  // 坑二守卫：pack 与 deliverables 未撞路由（撞了 render 会 404/405）
  if ([409, 503, 200].includes(mdCode)) ok("render 路由未被 pack 撞掉（挂 interventions 后仍正常）");
}

// ── 批次四：P11 受众分叉 / P12 vibe_pack / P14 项目总览 / R1~R4（E 组 29~32 + A 组）──
async function screenForkPackOverview() {
  console.log("\n[8] 批次四 · P11 受众分叉 / P12 vibe_pack / P14 总览 / R1~R4");

  const projectId = process.env.FLINT_PROJECT;
  if (!projectId) return fail("批次四", "缺 FLINT_PROJECT");

  // —— P11（清单 29/30）——
  const p11 = await page(`/projects/${projectId}/proposal`);
  seen("P11 200 且渲染", p11.html, "受众分叉");
  seen("P11 受众单选且无默认", p11.html, "单选，无默认");
  // 无默认：两个 radio 都不能是 checked
  const radios = (p11.raw.match(/<input[^>]*type="radio"[^>]*>/g) ?? []).filter((t) =>
    /name="audience"/.test(t),
  );
  const anyChecked = radios.some((t) => /\bchecked\b/.test(t));
  if (radios.length === 2 && !anyChecked) ok("P11 两支受众均未预选（无默认）");
  else fail("P11 无默认", `radio 数=${radios.length} 预选=${anyChecked}`);
  // 未选受众时不预先展示模板
  seen("P11 未选受众时不展示默认模板", p11.html, "此处不预先展示任何默认模板");
  // 422 混用规则四条如实列出
  seen("P11 列出 422 混用规则", p11.html, "受众混用 → 后端 422");
  seen("P11 ai_executor 锁 vibe_pack 规则在场", p11.html, "非 vibe_pack 的 template_id → 422");
  // 提交端点未接线：不做假按钮、不造假 job
  seen("P11 提交端点如实标未接线", p11.html, "端点未接线");
  seen("P11 明说没有可点的提交按钮", p11.html, "没有可点的提交按钮");
  unseen("P11 不造永远 queued 的假作业", p11.html, "已提交，正在排队");

  // —— P12（清单 31）：与报告屏结构不同 ——
  const p12 = await page(`/deliverables/${DELIVERABLE}/pack`);
  seen("P12 200 且渲染", p12.html, "vibe_pack");
  seen("P12 标明受众/模板", p12.html, "AUDIENCE · ai_executor");
  seen("P12 S1~S9 章节族在场", p12.html, "Escalation Rules");
  seen("P12 内容端点如实标未建", p12.html, "端点未建");
  // 结构差异：报告屏有出处槽与 8 支 content 渲染，pack 屏都不该有
  unseen("P12 无出处槽（非报告换皮）", p12.html, "出处槽空态");
  unseen("P12 不渲染报告的块类型", p12.html, "citation_list ·");

  // —— P14（清单 A-7）：组合屏必须写清由哪几支端点组合 ——
  const p14 = await page(`/projects/${projectId}`);
  seen("P14 200 且渲染", p14.html, "项目总览");
  seen("P14 明示无专属端点", p14.html, "这一屏没有专属端点（设计决策）");
  seen("P14 写清组合来源", p14.html, "/topics");
  seen("P14 明示没有按 project 列作业的端点", p14.html, "没有「列出本项目全部作业」的端点");
  unseen("P14 不假装列出全部作业", p14.html, "本项目全部作业：");

  // —— R1~R4（清单 32）：端点未建 MUST 明写 ——
  for (const [name, needle] of [
    ["R1 账户", "R1 账户"],
    ["R2 额度", "R2 额度"],
    ["R3 质量卡", "R3 质量卡"],
    ["R4 陈旧横幅", "R4 陈旧横幅"],
  ]) {
    seen(`${name} 预留位在场`, p14.html, needle);
  }
  seen("R2 写明 billing_enabled = False", p14.html, "billing_enabled = False");
  seen("R1~R4 统一标端点未建", p14.html, "此处不提供任何可点控件");

  // A 组通用：本批三屏都不得出现百分比/星级/进度条
  for (const [n, h] of [["P11", p11.html], ["P12", p12.html], ["P14", p14.html]]) {
    unseen(`${n} 无可靠度进度条`, h, "可靠度");
    unseen(`${n} 无星级`, h, "★");
  }
}

// ── 1 · 广场：真数据 + 空态 + 后端 400 ───────────────────────────
async function screenPlaza() {
  console.log("\n[1] /plaza · 真数据 / 空态 / 参数错");
  const live = await liveDay();
  if (live === null) return fail("广场真数据", "后端 45 天内无热点数据");

  const p = await page(`/plaza?day=${live.day}`);
  seen("200 且页面渲染", p.html, "热点广场");
  seen("day 来自后端", p.html, live.day);
  seen("真簇名上屏", p.html, live.first.canonical_name);
  seen("cluster_id 上屏", p.html, live.first.cluster_id);
  seen("hotness 上屏（后端算好的值）", p.html, String(live.first.hotness));
  // by_source 缺源必须显"该源当日无数据"，不得补 0
  const present = Object.keys(live.first.by_source);
  const missing = ["arxiv", "ghtrend", "gtrends", "weibo"].filter((s) => !present.includes(s));
  if (missing.length > 0) seen(`缺源如实标注（缺 ${missing.join("/")}）`, p.html, "该源当日无数据");
  else ok("四源齐全，无缺源标注需求");

  const e = await page(`/plaza?day=${EMPTY_DAY}`);
  seen("空态日 → 「该日无热点」", e.html, "该日无热点");
  seen("空态措辞明说非加载/非错误", e.html, "非加载中、非错误");

  const bad = await page("/plaza?day=not-a-date");
  seen("非法 day → 抬后端错误体", bad.html, "VALIDATION_FAILED");
  unseen("非法 day 时不冒充空态", bad.html, "该日无热点");
}

// ── 2 · Gate：D_insufficient + gaps + unknown 竞品 / 未知 job / 越权 ──
async function screenGate() {
  console.log("\n[2] /gate/[jobId] · 判定诚实态");
  const res = await fetch(`${API}/jobs/${encodeURIComponent(VERDICT_JOB)}/verdict`, {
    headers: { "x-user-id": "demo-user" },
  });
  if (res.status === 404) {
    return fail("判定样本", `${VERDICT_JOB} 不在库（重建：python -m harness.gate1_live replay-qwen）`);
  }
  const { verdict: v } = await res.json();

  const p = await page(`/gate/${VERDICT_JOB}`);
  seen("verdict 档位上屏", p.html, v.verdict);
  if (v.verdict === "D_insufficient") {
    seen("D 档措辞：不是失败", p.html, "暂无法判定");
    seen("D 档措辞：诚实的空白", p.html, "诚实的空白");
    seen("gaps 计数上屏", p.html, `缺口 · gaps（${v.gaps.length}）`);
    for (const g of v.gaps) seen(`gap 文案上屏「${g.missing_what.slice(0, 12)}…」`, p.html, g.missing_what);
  }
  const unknowns = (v.competitors ?? []).filter((c) => c.strength === "unknown");
  if (unknowns.length > 0) {
    seen("unknown 竞品显「未知」而非「弱」", p.html, "strength · 未知");
    for (const c of unknowns.slice(0, 3)) seen(`竞品名上屏「${c.name.slice(0, 16)}」`, p.html, c.name);
  }
  seen("constraints_checked 可展开", p.html, "constraints_checked");
  seen("rule_c failed_conditions 上屏", p.html, "failed_conditions");

  // notFound() 边界：Next 16 dev 下由 flight 载荷在客户端挂载，首屏 HTML body 无标记，
  // 故这里断言 HTTP 404 + 载荷里带 not-found 文案（不是"页面空白"）。
  const unknown = await page("/gate/job-does-not-exist");
  if (unknown.status === 404) ok("未知 job → HTTP 404");
  else fail("未知 job → HTTP 404", `status=${unknown.status}`);
  seen("未知 job → 「后端没有这个 job」", unknown.raw, "后端没有这个 job");
  unseen("未知 job 时不编一个判定（渲染标记内）", unknown.html, "D_insufficient");

  const foreign = process.env.FLINT_FOREIGN_JOB;
  if (foreign) {
    const f = await page(`/gate/${foreign}`);
    seen("越权 job → 抬 PERMISSION_DENIED", f.html, "PERMISSION_DENIED");
  }
}

// ── 3 · 报告：Block 树 / 保护块 / 争议 / 缺口 / 未生成 ────────────
async function screenReport() {
  console.log("\n[3] /deliverables/[id] · 报告 L0 诚实态");
  const res = await fetch(`${API}/deliverables/${encodeURIComponent(DELIVERABLE)}/blocks`, {
    headers: { "x-user-id": "demo-user" },
  });
  if (res.status === 404) {
    return fail("报告样本", `${DELIVERABLE} 不在库（重建：python -m harness.demo_seed_report）`);
  }
  const { blocks } = await res.json();

  const p = await page(`/deliverables/${DELIVERABLE}`);
  seen("deliverable_id 上屏", p.html, DELIVERABLE);

  // 8 支 BlockContent 全部有对应渲染痕迹
  const kinds = new Set(blocks.map((b) => b.content.kind));
  const PROBE = {
    declaration: blocks.find((b) => b.content.kind === "declaration")?.content.text,
    heading: blocks.find((b) => b.content.kind === "heading")?.content.text,
    paragraph: blocks.find((b) => b.content.kind === "paragraph")?.content.spans.find((s) => s.kind === "text")?.text,
    table: blocks.find((b) => b.content.kind === "table")?.content.header?.[0],
    chart: blocks.find((b) => b.content.kind === "chart")?.content.chart_id,
    quality_card: blocks.find((b) => b.content.kind === "quality_card")?.content.card_ref,
    citation_list: blocks.find((b) => b.content.kind === "citation_list")?.content.citation_ids?.[0],
    gap_notice: blocks.find((b) => b.content.kind === "gap_notice")?.content.hints_ref,
  };
  for (const k of kinds) {
    const needle = PROBE[k];
    if (needle) seen(`content.kind=${k} 已渲染`, p.html, needle);
    else fail(`content.kind=${k} 已渲染`, "取不到可断言的探针值");
  }

  // 保护块：locked ∨ author==user ∨ user_modified → 只读，且不渲染编辑控件
  const prot = blocks.filter((b) => b.locked || b.author === "user" || b.user_modified);
  if (prot.length > 0) {
    seen("保护块标记上屏", p.html, "保护块 ·");
    seen("保护块明示不提供编辑控件", p.html, "受保护 · 不提供编辑控件");
    unseen("保护块不渲染「编辑」按钮", p.html, ">编辑<");
    ok("保护块计数", `${prot.length} / ${blocks.length}`);
  }

  // 争议 claim
  const disputed = blocks.find(
    (b) => b.content.kind === "paragraph" && b.content.spans.some((s) => s.kind === "claim" && s.disputed_mark),
  );
  if (disputed) {
    const claim = disputed.content.spans.find((s) => s.kind === "claim" && s.disputed_mark);
    seen("争议 claim 原文保留（标记不删原文）", p.html, claim.text);
    seen("争议印记上屏", p.html, "争议");
  }

  // blocking 复核 → 阻断印记
  const blocking = blocks.filter((b) => b.review_severity === "blocking");
  if (blocking.length > 0) {
    seen("blocking 阻断印记上屏", p.html, "阻断");
    ok("blocking 块", blocking.map((b) => b.block_id).join(", "));
  }

  // gap_notice → 物理切口，不以生成文字填满
  if (kinds.has("gap_notice")) {
    seen("缺口如实呈现措辞", p.html, "缺口如实呈现，未以占位数据填充");
    seen("缺口印记上屏", p.html, "缺口");
  }

  // 未生成 → 诚实 404 态（不是 mock 兜底）
  const none = await page("/deliverables/del-does-not-exist");
  seen("未生成 → 「该交付物尚未生成」", none.html, "该交付物尚未生成");
  seen("未生成态点名 404 端点", none.html, "NOT_FOUND");
  unseen("未生成时不退回 mock 正文", none.html, "本报告结论均以引用为准");
}

// ── 4 · 后端不可达：前端必须显「后端不可达」而不是空页 ───────────
async function screenBackendDown() {
  console.log("\n[4] 后端不可达（起一个指向死端口的前端才可测——此处只验组件在场）");
  // 用一个必然连不上的 API 基址无法在同一 dev server 上切换，故此处只断言
  // 错误组件的文案已编进 bundle：抓 /plaza?day=not-a-date（后端 400 → 走同一组件）。
  const bad = await page("/plaza?day=not-a-date");
  seen("错误体 code 上屏", bad.html, "VALIDATION_FAILED");
  seen("错误体指明请求 URL", bad.html, "/plaza/hot");
}

console.log("Flint v0 前端 · 边缘态渲染验证");
console.log(`  WEB = ${WEB}   API = ${API}`);
try {
  await fetch(`${WEB}/plaza`);
} catch {
  console.error(`\n前端不可达：${WEB}（先 pnpm dev）`);
  process.exit(1);
}

await screenPlaza();
await screenGate();
await screenReport();
await screenBackendDown();
await screenShellAndBatchOne();
await screenTopicAndJob();
await screenIntervenAndExport();
await screenForkPackOverview();

console.log(`\n通过 ${pass} 项，失败 ${failures.length} 项。`);
if (failures.length > 0) {
  console.log("\n失败明细：");
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}
process.exit(0);
