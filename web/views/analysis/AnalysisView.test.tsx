// HOTSPOT-03 验收（前端半）：分析界面骨架。
//
// acceptance①「进入即渲染既有判定与证据概览；无任何新分析调用（网络层 spy）」——
// 两句缺一不可：**渲染发生了**（不是什么都没画）且 **只读**（不是顺手跑了一次分析）。
// 所以 spy 既断言「零写请求」，也断言「读请求真的发出去了」——组件什么都不 fetch
// 时「零写请求」同样成立，那种绿是空转。
//
// acceptance②「界面语言=系统语言（C11）」：文案全部经 t() 取自同一份 messages，
// 视图自己 NEVER 持有语言状态、NEVER 从浏览器或地区推语言（A3 反例第一/三条）。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisView } from "./AnalysisView";

const SOURCE = readFileSync(join(__dirname, "AnalysisView.tsx"), "utf8");

/** 只看代码行：块注释与行注释里的中文是解释文字，不是界面文案（DEC-008 同口径）。 */
function codeLines(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((l) => !l.trim().startsWith("//"))
    .join("\n");
}

type Call = { url: string; method: string };

const VERDICT = {
  verdict: "C_opportunity",
  all_satisfied: ["C_opportunity"],
  key_citation_ids: ["cit-1", "cit-2"],
  rationale_fact_ids: ["fact-1"],
  competitors: [{ name: "Acme", url: "http://a", strength: "weak" }],
  constraints_checked: true,
  gaps: [],
};

const CARDS = [
  {
    card_id: "card-1",
    cluster_id: "c-1",
    keyword_ids: ["k1", "k2"],
    flags: ["needs_price"],
    top_links: ["http://l1", "http://l2", "http://l3"],
  },
  {
    card_id: "card-2",
    cluster_id: "c-1",
    keyword_ids: ["k3"],
    flags: [],
    top_links: ["http://l4"],
  },
];

/** 网络层 spy：记下每一次请求（含方法），按 URL 派发既有读端点的罐头响应。 */
function spyFetch(
  calls: Call[],
  opts: { verdictStatus?: number; cards?: unknown[] } = {},
): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: (init?.method ?? "GET").toUpperCase() });
    if (url.includes("/verdict")) {
      const status = opts.verdictStatus ?? 200;
      return new Response(status === 200 ? JSON.stringify({ verdict: VERDICT }) : "{}", {
        status,
        headers: { "content-type": "application/json" },
      });
    }
    if (url.includes("/evidence-cards")) {
      return new Response(JSON.stringify({ evidence_cards: opts.cards ?? CARDS }), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    throw new Error(`spy: 未预期的请求 ${url}`);
  }) as unknown as typeof fetch;
}

describe("AnalysisView（分析界面骨架）", () => {
  it("进入即渲染既有判定：判定值逐字来自后端，前端 NEVER 自判", async () => {
    const calls: Call[] = [];
    render(
      <AnalysisView clusterId="c-1" verdictJobId="job-1" fetchImpl={spyFetch(calls)} />,
    );

    const slot = await screen.findByTestId("analysis-verdict");
    expect(slot.textContent).toContain("C_opportunity");
    // 判定标记必须可被机器读回，否则下游（收藏快照 verdict_at_save）无从取值
    expect(slot).toHaveAttribute("data-verdict", "C_opportunity");
    expect(screen.queryByTestId("analysis-verdict-unjudged")).toBeNull();
  });

  it("进入即渲染证据概览：每张证据卡独立成条，计数取自后端字段", async () => {
    const calls: Call[] = [];
    render(
      <AnalysisView clusterId="c-1" verdictJobId="job-1" fetchImpl={spyFetch(calls)} />,
    );

    const items = await screen.findAllByTestId("analysis-evidence-card");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveAttribute("data-card-id", "card-1");
    expect(items[0].textContent).toContain("3"); // top_links 三条
    expect(items[1]).toHaveAttribute("data-card-id", "card-2");
  });

  it("无任何新分析调用：spy 全程只有 GET，且读请求确实发生过（非空转）", async () => {
    const calls: Call[] = [];
    render(
      <AnalysisView clusterId="c-1" verdictJobId="job-1" fetchImpl={spyFetch(calls)} />,
    );
    await screen.findByTestId("analysis-verdict");
    await screen.findAllByTestId("analysis-evidence-card");

    expect(calls.length).toBeGreaterThanOrEqual(2); // 阴性对照：读真的发生了
    expect(calls.every((c) => c.method === "GET")).toBe(true);
    // 分析触发端点（C8 `POST /analysis/deep`）一次都不许出现
    expect(calls.some((c) => c.url.includes("/analysis"))).toBe(false);
    expect(calls.some((c) => c.url.includes("/jobs/") && c.method !== "GET")).toBe(false);
    // 命中的只有两个既有读端点，NEVER 冒出第三个 URL 形态
    for (const c of calls) {
      expect(/\/jobs\/[^/]+\/verdict$|\/clusters\/[^/]+\/evidence-cards$/.test(c.url)).toBe(
        true,
      );
    }
  });

  it("尚无既有判定时渲染未判定态：NEVER 造一个判定，也 NEVER 顺手去跑一次", async () => {
    const calls: Call[] = [];
    render(
      <AnalysisView
        clusterId="c-1"
        verdictJobId="job-1"
        fetchImpl={spyFetch(calls, { verdictStatus: 404 })}
      />,
    );

    const empty = await screen.findByTestId("analysis-verdict-unjudged");
    expect(screen.queryByTestId("analysis-verdict")).toBeNull();
    // 未判定态的文案 NEVER 是四分类里的任何一个（那就成了假判定）
    expect(empty.textContent).not.toMatch(/A_infeasible|B_red_ocean|C_opportunity|D_/);
    expect(calls.every((c) => c.method === "GET")).toBe(true);
    expect(calls.some((c) => c.url.includes("/analysis"))).toBe(false);
  });

  it("调用方未给出判定所在 job 时不猜：不发 verdict 请求，只渲染未判定态", async () => {
    const calls: Call[] = [];
    render(<AnalysisView clusterId="c-1" fetchImpl={spyFetch(calls)} />);

    await screen.findByTestId("analysis-verdict-unjudged");
    await screen.findAllByTestId("analysis-evidence-card");
    // cluster→判定 的对应关系当前无持久化真相（见 docs/blocked/HOTSPOT-03.md）：
    // 缺就是缺，NEVER 拿 cluster_id 拼一个 job id 去试
    expect(calls.some((c) => c.url.includes("/verdict"))).toBe(false);
    expect(calls.some((c) => c.url.includes("/evidence-cards"))).toBe(true);
  });

  it("读端点复用既有客户端：不在视图里重写一遍 URL", () => {
    const code = codeLines(SOURCE);
    expect(code).toMatch(/from "\.\.\/\.\.\/lib\/viewsClient"/);
    expect(code).not.toContain("/evidence-cards");
    expect(code).not.toContain("/jobs/");
  });

  it("界面语言=系统语言：文案经 t() 取词条，源码代码行零 CJK", async () => {
    const code = codeLines(SOURCE);
    expect(code).not.toMatch(/[一-鿿]/);
    expect(code).toMatch(/from "\.\.\/\.\.\/lib\/i18n\/t"/);

    render(<AnalysisView clusterId="c-1" fetchImpl={spyFetch([])} />);
    const empty = await screen.findByTestId("analysis-verdict-unjudged");
    // 回落形态是「key 原样」：取不到词条时这里会是 analysis.verdict.unjudged
    expect(empty.textContent).toBeTruthy();
    expect(empty.textContent).not.toBe("analysis.verdict.unjudged");
  });

  it("视图不持有语言状态：无 lang/locale 入参，NEVER 读浏览器语言或从地区推", () => {
    const code = codeLines(SOURCE);
    expect(code).not.toContain("navigator.language");
    expect(code).not.toContain("Accept-Language");
    expect(code).not.toMatch(/\b(lang|locale)\s*[?:]/); // props 面无语言开关
    expect(code).not.toMatch(/resolveLocale|region\s*===/); // 不从地区反推语言
  });
});
