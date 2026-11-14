/**
 * NAV-02：点卡片主体 → 这个热点的分析界面。
 *
 * ## 改前的实况
 *
 * `AnalysisView`（`HOTSPOT-03` 的成品，四态齐全、只读）**没有任何屏在用**——
 * 全仓唯一引用它的 `GraphOpenAnalysis` 自己也没有屏在用。
 * 广场那边同时是断的：`PlazaCards` 早就有 `onSelectCluster`，广场屏没往里传，
 * 点卡片什么都不会发生。
 *
 * **建好的东西点不到，与没建长得一模一样。**
 *
 * ## 这一组判据守的四件事
 *
 * 1. **进入即渲染、进入不触发**（`DEC-042` ③）。网络层 spy 数请求方法：
 *    零写请求，且读请求真的发出去了——什么都不 fetch 时「零写请求」同样成立，
 *    那种绿是空转。
 * 2. **四态各自成一态**。「未判定」（还没过 Gate①）与「读失败」（我们没读到）
 *    尤其不能合并：用户据此做的下一步动作完全不同。
 * 3. **判定归属由调用方给出**。没带 `?verdictJob=` 就是未判定，
 *    且**一个 verdict 请求都不发**——`NEVER 拿 cluster_id 拼一个 job id 去试`。
 * 4. **点击排除区不倒**。点三个动作按钮 NEVER 触发卡片跳转，
 *    键盘上按回车同样不许跳（`stopPropagation` 拦的是 click，keydown 照样冒上来）。
 */
import { act, fireEvent, render, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/plaza" }));

import ClusterAnalysisPage from "../../app/clusters/[id]/page";
import PlazaPage from "../../app/plaza/page";
import zh from "../../messages/zh.json";

const messages = zh as Record<string, string>;

type Call = { url: string; method: string };

const VERDICT = {
  verdict: "C_opportunity",
  all_satisfied: ["rule_a"],
  key_citation_ids: ["cit-1", "cit-2"],
  rationale_fact_ids: ["fact-1"],
  competitors: [],
  constraints_checked: true,
  gaps: [],
};

const CARDS = [
  {
    card_id: "card-1", cluster_id: "c-1",
    keyword_ids: ["k1"], flags: [], top_links: ["http://l1"],
  },
];

const CLUSTERS = [
  {
    cluster_id: "c-1", canonical_name: "固态电池", category_id: "energy",
    status: "active", by_source: { gtrends: 91 }, total_heat: 91,
  },
];

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json" },
  });
}

/** 网络层 spy：**记下每一次请求的方法**，按 URL 派发既有读端点的罐头响应。 */
function spy(calls: Call[], opts: { verdictStatus?: number } = {}) {
  return vi.fn((input: unknown, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: (init?.method ?? "GET").toUpperCase() });
    if (url.includes("/verdict")) {
      const status = opts.verdictStatus ?? 200;
      // `WIRE-VERDICT` 之后按热点问的那条要回 `job_id`——
      // 它就是 `DEC-044` 补上的那条 cluster→job 对应关系。
      // 不给的话分析屏拿不到 id，会停在「还没读」而屏上什么都不说。
      return Promise.resolve(status === 200
        ? json({ cluster_id: "c-1", job_id: "job-from-cluster", verdict: VERDICT })
        : json({}, status));
    }
    if (url.includes("/evidence-cards")) {
      return Promise.resolve(json({ evidence_cards: CARDS }));
    }
    if (url.includes("/settings/locale")) {
      return Promise.resolve(json({ region: "CN", options: { region: ["CN"] } }));
    }
    if (url.includes("/plaza/hot")) return Promise.resolve(json({ clusters: CLUSTERS }));
    return Promise.reject(new Error(`spy: 未预期的请求 ${url}`));
  });
}

async function renderAsync(ui: React.ReactElement) {
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(<Suspense fallback={null}>{ui}</Suspense>);
  });
  return result;
}

const page = (id: string) => <ClusterAnalysisPage params={Promise.resolve({ id })} />;

beforeEach(() => {
  window.history.replaceState({}, "", "/");
});

// ───────────────────────── 一、承载屏装的是那个成品，不是它的复刻

describe("热点分析屏", () => {
  it("装的是 AnalysisView 本体——NEVER 为这一屏再写一遍分析视图", async () => {
    const calls: Call[] = [];
    vi.stubGlobal("fetch", spy(calls));
    const { container } = await renderAsync(page("c-1"));

    await waitFor(() => {
      expect(container.querySelector("[data-testid='analysis-view']")).not.toBeNull();
    });
    expect(
      container.querySelector("[data-testid='analysis-view']")
        ?.getAttribute("data-cluster-id"),
    ).toBe("c-1");
  });

  it("**进入即渲染、进入不触发**：读请求发出去了，写请求一个都没有", async () => {
    const calls: Call[] = [];
    vi.stubGlobal("fetch", spy(calls));
    window.history.replaceState({}, "", "/clusters/c-1?verdictJob=job-7");
    const { container } = await renderAsync(page("c-1"));

    await waitFor(() => {
      expect(container.querySelector("[data-testid='analysis-verdict']")).not.toBeNull();
    });

    // 两句缺一不可。只断言「零写请求」的话，一个什么都不 fetch 的空组件也能绿。
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.map((c) => c.method).filter((m) => m !== "GET")).toEqual([]);
    // 打开一个热点的分析界面**只是查看**：跑一次分析要让用户付一次钱，
    // 且同一个热点每次可能显示不同判定，判定本身就不再可被引用。
    expect(calls.some((c) => /\/analysis\b/.test(c.url))).toBe(false);
  });

  it("没带 verdictJob 时**去问那个热点判过什么**，NEVER 拼一个 job id 去试", async () => {
    // 这条判据原来断言「一个 verdict 请求都不发」，理由是
    // `cluster → job` 的对应关系没有持久化真相（`DEC-012` / `HOTSPOT-03`）。
    // **那个理由在当时是对的**，而 `DEC-044` 之后前提变了：
    // `cluster_verdicts` 就是那份真相，`PERSIST-04` 建了端点把它读出来。
    //
    // 所以断言跟着翻面——**翻的是「发不发请求」，不是那条禁令**：
    // 「NEVER 拿 cluster_id 拼一个 job id 去试」一字未改，下面第二句钉着它。
    const calls: Call[] = [];
    vi.stubGlobal("fetch", spy(calls));
    const { container } = await renderAsync(page("c-1"));

    await waitFor(() => {
      expect(container.querySelector("[data-testid='analysis-view']")).not.toBeNull();
    });
    // 问的是**按热点**那条。
    expect(calls.some((c) => /\/clusters\/c-1\/verdict/.test(c.url))).toBe(true);
    // 取判定内容仍走 `/jobs/{id}/verdict`——**而那个 id 是端点给的**。
    // 第一版我在这里断言「一个 /jobs/…/verdict 都不发」，**写反了**：
    // 拿端点回的 id 去取内容正是「去问」，而禁令禁的是「去猜」。
    // 所以钉的是那个 id 的**来源**：它必须是端点回的那一个，
    // 且 NEVER 是从 cluster id 拼出来的。
    const jobCalls = calls.filter((c) => /\/jobs\/[^/]+\/verdict/.test(c.url));
    expect(jobCalls.every((c) => c.url.includes("job-from-cluster"))).toBe(true);
    expect(jobCalls.some((c) => c.url.includes("c-1"))).toBe(false);
  });

  it("「未判定」与「读失败」各自成一态，NEVER 互相冒充", async () => {
    const calls: Call[] = [];
    vi.stubGlobal("fetch", spy(calls, { verdictStatus: 500 }));
    window.history.replaceState({}, "", "/clusters/c-1?verdictJob=job-7");
    const { container } = await renderAsync(page("c-1"));

    await waitFor(() => {
      expect(container.querySelector("[data-testid='analysis-verdict-error']")).not.toBeNull();
    });
    expect(container.querySelector("[data-testid='analysis-verdict-unjudged']")).toBeNull();
    expect(container.textContent).toContain(messages["analysis.verdict.error"]);
  });

  it("读 URL 参数之前先说「正在读」，NEVER 先闪一下「未判定」再改口", async () => {
    const calls: Call[] = [];
    vi.stubGlobal("fetch", spy(calls));
    // 首帧：effect 还没跑，`verdictJob` 是 undefined。
    const { container } = render(<Suspense fallback={null}>{page("c-1")}</Suspense>);

    expect(container.querySelector("[data-testid='analysis-verdict-unjudged']")).toBeNull();
  });
});

// ───────────────────────── 二、广场：卡片主体是导航，三个按钮是动作

describe("广场 → 热点分析", () => {
  function stubAssign(): { to: string[] } {
    const to: string[] = [];
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, assign: (u: string) => to.push(u), search: "" },
    });
    return { to };
  }

  // 广场上同一张卡出现在**两处**：上面的堆叠（精选）与下面的网格（全量）。
  // 两处都要能进去，且进的是同一屏——所以判据分开点，NEVER 只点其中一处。
  const gridItem = (c: HTMLElement) =>
    c.querySelector('.plaza-grid__item[data-cluster-id="c-1"]')!;
  const stackCard = (c: HTMLElement) =>
    c.querySelector('.plaza-stack__slot[data-cluster-id="c-1"]')!;

  it("点网格里的卡片主体 → /clusters/{id}（DEC-042 ①）", async () => {
    vi.stubGlobal("fetch", spy([]));
    const nav = stubAssign();
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => expect(gridItem(container)).not.toBeNull());
    await act(async () => { fireEvent.click(gridItem(container)); });

    expect(nav.to).toEqual(["/clusters/c-1"]);
  });

  it("点堆叠里当前那张也进同一屏——两个广场 NEVER 各去各的", async () => {
    vi.stubGlobal("fetch", spy([]));
    const nav = stubAssign();
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => expect(stackCard(container)).not.toBeNull());
    await act(async () => { fireEvent.click(stackCard(container)); });

    expect(nav.to).toEqual(["/clusters/c-1"]);
  });

  it("**NEVER 把 verdictJob 带过去**：那个 job 不属于任何一张具体的卡（DEC-012）", async () => {
    vi.stubGlobal("fetch", spy([]));
    window.history.replaceState({}, "", "/plaza?verdictJob=job-7");
    const nav = stubAssign();
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => expect(gridItem(container)).not.toBeNull());
    await act(async () => { fireEvent.click(gridItem(container)); });

    expect(nav.to).toEqual(["/clusters/c-1"]);
    expect(nav.to[0]).not.toContain("job-7");
  });

  it("点击排除区不倒：点三个动作按钮 NEVER 跳屏（HOTSPOT-02 双断言）", async () => {
    vi.stubGlobal("fetch", spy([]));
    const nav = stubAssign();
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => expect(gridItem(container)).not.toBeNull());
    const item = gridItem(container);
    for (const which of ["favorite", "workbench", "share"]) {
      await act(async () => {
        fireEvent.click(item.querySelector(`[data-testid='action-${which}']`)!);
      });
      expect(nav.to).toEqual([]);           // 按了一下屏还在
    }
    // 另一半断言：卡片主体照样能跳——排除区没有把整张卡一起废掉。
    await act(async () => { fireEvent.click(item); });
    expect(nav.to).toEqual(["/clusters/c-1"]);
  });

  it("键盘也能进去，而在按钮上按回车 NEVER 跳屏", async () => {
    vi.stubGlobal("fetch", spy([]));
    const nav = stubAssign();
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => expect(gridItem(container)).not.toBeNull());
    const item = gridItem(container);
    expect(item.getAttribute("tabindex")).toBe("0");
    expect(item.getAttribute("role")).toBe("link");

    // `stopPropagation` 拦的是 click——keydown 照样冒到卡片上。
    await act(async () => {
      fireEvent.keyDown(item.querySelector("[data-testid='action-favorite']")!, {
        key: "Enter",
      });
    });
    expect(nav.to).toEqual([]);

    await act(async () => { fireEvent.keyDown(item, { key: "Enter" }); });
    expect(nav.to).toEqual(["/clusters/c-1"]);
  });

  it("堆叠上也能用键盘打开：改前方向键能翻，却没有一个键能进去", async () => {
    vi.stubGlobal("fetch", spy([]));
    const nav = stubAssign();
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => expect(stackCard(container)).not.toBeNull());
    await act(async () => {
      fireEvent.keyDown(container.querySelector("[data-testid='plaza-stack-deck']")!, {
        key: "Enter",
      });
    });

    expect(nav.to).toEqual(["/clusters/c-1"]);
  });
});
