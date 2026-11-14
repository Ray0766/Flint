/**
 * UI-02：主链路四屏可点通 —— 广场 → Gate① → 报告 → 导出（含 409 阻断态）。
 *
 * ## 这一组判据守的三件事
 *
 * 1. **判定归属由调用方持有**（DEC-012）。没有 `verdictJobId` 时渲染「未判定」
 *    且**一个请求都不发**——猜一个 job 去问，猜错时用户会看到**另一个热点的判定**
 *    并把它引进计划书。所以判据不只看渲染结果，还看 `fetch` **被调用了几次**。
 * 2. **阻断时说清原因与被阻断的块**。只弹一句「导出失败」的话，用户既不知道为什么，
 *    也不知道去哪儿改。409 是他**能自己解决**的，503 是他**等就行**的，
 *    合成一句就都变成了「不知道该怎么办」。
 * 3. **四屏真的连得起来**。判据查每一屏都渲染出通往下一屏的 href，
 *    且那些 href 指向本仓真实存在的路由文件。
 */
import { act, render, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import zh from "../../messages/zh.json";
import { requestExport } from "../../app/deliverables/[id]/export/exportClient";

const messages = zh as Record<string, string>;

vi.mock("next/navigation", () => ({ usePathname: () => "/plaza" }));

import PlazaPage from "../../app/plaza/page";
import GatePage from "../../app/gate/[id]/page";
import ExportPage from "../../app/deliverables/[id]/export/page";

const CLUSTERS = [
  {
    cluster_id: "c-1", canonical_name: "固态电池", category_id: "energy",
    status: "active", by_source: { gtrends: 91, weibo: 40 }, total_heat: 131,
  },
];

const VERDICT = {
  verdict: "C_opportunity",
  all_satisfied: ["rule_a"],
  key_citation_ids: ["cit-1"],
  rationale_fact_ids: ["fact-1"],
  competitors: [{ name: "Acme", url: "https://acme.test", strength: "strong" }],
  constraints_checked: true,
  gaps: [],
};

let fetchMock: ReturnType<typeof vi.fn>;

function jsonOnce(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => "application/json" },
    json: async () => body,
  };
}

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  window.history.replaceState({}, "", "/");
});

async function renderAsync(ui: React.ReactElement) {
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(<Suspense fallback={null}>{ui}</Suspense>);
  });
  return result;
}

// PLAZA-03：广场屏现在取两条（`/plaza/hot` 与 `/settings/locale`），
// 所以 mock **按 URL 分派**，NEVER 让同一个响应体喂给两条不同的端点——
// 那样 `/settings/locale` 会收到一份 `{clusters: […]}`，读它的 `options.region`
// 报出来的错会指向广场，而真相是 mock 喂错了。
function plazaFetch(body: unknown) {
  return (url: unknown) =>
    Promise.resolve(
      String(url).includes("/settings/locale")
        ? jsonOnce({ region: "CN", options: { lang: ["zh"], region: ["CN", "JP"] } })
        : jsonOnce(body),
    );
}

// ───────────────────────── 一、广场（第一屏）

describe("广场屏", () => {
  it("列出后端给的热点，顺序原样——前端零计算", async () => {
    fetchMock.mockImplementation(plazaFetch({ clusters: CLUSTERS }));
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => {
      expect(container.querySelector("[data-plaza-list]")).not.toBeNull();
    });
    expect(container.querySelector('[data-cluster-id="c-1"]')).not.toBeNull();
  });

  it("没有 verdictJob 时标「未判定」，且**不发 verdict 请求**（DEC-012）", async () => {
    fetchMock.mockImplementation(plazaFetch({ clusters: CLUSTERS }));
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => {
      expect(container.querySelector("[data-gate-unjudged]")).not.toBeNull();
    });
    expect(container.querySelector("[data-gate-link]")).toBeNull();
    expect(container.textContent).toContain(messages["plaza.gate_entry.unjudged"]);
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/verdict"))).toBe(false);
  });

  it("调用方给了 verdictJob 时才出现通往 Gate 的链接", async () => {
    window.history.replaceState({}, "", "/plaza?verdictJob=job-7");
    fetchMock.mockImplementation(plazaFetch({ clusters: CLUSTERS }));
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => {
      expect(container.querySelector("[data-gate-link]")).not.toBeNull();
    });
    expect(container.querySelector("[data-gate-link]")?.getAttribute("href")).toBe("/gate/job-7");
  });

  it("取数失败时说出来，NEVER 装成空广场", async () => {
    fetchMock.mockResolvedValue(jsonOnce({}, 500));
    const { container } = await renderAsync(<PlazaPage />);

    await waitFor(() => {
      expect(container.querySelector("[data-plaza-error]")).not.toBeNull();
    });
    expect(container.querySelector("[data-plaza-empty]")).toBeNull();
  });
});

// ───────────────────────── 二、Gate①（第二屏）

describe("Gate 屏", () => {
  it("判定直取后端，前端 NEVER 自判分类", async () => {
    fetchMock.mockResolvedValue(jsonOnce({ verdict: VERDICT }));
    const { container } = await renderAsync(
      <GatePage params={Promise.resolve({ id: "job-7" })} />,
    );

    await waitFor(() => {
      expect(container.querySelector("[data-verdict]")).not.toBeNull();
    });
    expect(container.querySelector("[data-verdict]")?.getAttribute("data-verdict")).toBe(
      "C_opportunity",
    );
    expect(fetchMock.mock.calls.map((c) => String(c[0]))[0]).toContain("/jobs/job-7/verdict");
  });

  it("后端说还没判定（404）时渲染「未判定」", async () => {
    fetchMock.mockResolvedValue(jsonOnce({}, 404));
    const { container } = await renderAsync(
      <GatePage params={Promise.resolve({ id: "job-7" })} />,
    );

    await waitFor(() => {
      expect(container.querySelector("[data-gate-unjudged]")).not.toBeNull();
    });
    expect(container.textContent).toContain(messages["gate.screen.unjudged"]);
    expect(container.querySelector("[data-verdict]")).toBeNull();
  });

  it("缺 jobId 时渲染「未判定」且**一个请求都不发**（acceptance②）", async () => {
    const { container } = await renderAsync(<GatePage params={Promise.resolve({ id: "" })} />);

    await waitFor(() => {
      expect(container.querySelector("[data-gate-unjudged]")).not.toBeNull();
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("「没判定」与「读失败」是两回事，分别渲染", async () => {
    fetchMock.mockResolvedValue(jsonOnce({}, 500));
    const { container } = await renderAsync(
      <GatePage params={Promise.resolve({ id: "job-7" })} />,
    );

    await waitFor(() => {
      expect(container.querySelector("[data-gate-error]")).not.toBeNull();
    });
    expect(container.querySelector("[data-gate-unjudged]")).toBeNull();
  });

  it("调用方给了 deliverable 时才出现通往报告的链接", async () => {
    window.history.replaceState({}, "", "/gate/job-7?deliverable=del-9");
    fetchMock.mockResolvedValue(jsonOnce({ verdict: VERDICT }));
    const { container } = await renderAsync(
      <GatePage params={Promise.resolve({ id: "job-7" })} />,
    );

    await waitFor(() => {
      expect(container.querySelector("[data-report-link]")).not.toBeNull();
    });
    expect(container.querySelector("[data-report-link]")?.getAttribute("href")).toBe(
      "/deliverables/del-9",
    );
  });
});

// ───────────────────────── 三、导出（第四屏）与 409 阻断态

describe("导出客户端", () => {
  it("409 EXPORT_BLOCKED 解出被阻断的块", async () => {
    const outcome = await requestExport("del-9", "pdf", {
      fetchImpl: (async () =>
        jsonOnce(
          { code: "EXPORT_BLOCKED", message: "blocking reviews open",
            detail: { blocking_block_ids: ["b-1", "b-2"] } },
          409,
        )) as unknown as typeof fetch,
    });

    expect(outcome).toEqual({
      kind: "blocked", fmt: "pdf", blockingBlockIds: ["b-1", "b-2"], violations: [],
    });
  });

  it("503 是「暂时不可用」，NEVER 与 409 混成一种结局", async () => {
    const outcome = await requestExport("del-9", "pack", {
      fetchImpl: (async () =>
        jsonOnce({ code: "SERVICE_UNAVAILABLE", message: "pack builder not wired" }, 503)
      ) as unknown as typeof fetch,
    });

    expect(outcome.kind).toBe("unavailable");
  });

  it("错误体读不动时如实报状态码，NEVER 猜一份 detail 出来", async () => {
    const outcome = await requestExport("del-9", "pdf", {
      fetchImpl: (async () => ({
        ok: false, status: 409, headers: { get: () => "" },
        json: async () => {
          throw new Error("not json");
        },
      })) as unknown as typeof fetch,
    });

    expect(outcome).toEqual({ kind: "failed", fmt: "pdf", status: 409 });
  });

  it("成功时带回内容类型", async () => {
    const outcome = await requestExport("del-9", "markdown", {
      fetchImpl: (async () => jsonOnce("# 报告")) as unknown as typeof fetch,
    });

    expect(outcome.kind).toBe("ok");
  });
});

describe("导出屏", () => {
  it("被阻断时列出每一个挡路的块，每条都能跳回报告里那一处", async () => {
    fetchMock.mockResolvedValue(
      jsonOnce(
        { code: "EXPORT_BLOCKED", message: "blocking reviews open",
          detail: { blocking_block_ids: ["b-1", "b-2"] } },
        409,
      ),
    );
    const { container } = await renderAsync(
      <ExportPage params={Promise.resolve({ id: "del-9" })} />,
    );
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-export-format="pdf"]')?.click();
    });

    await waitFor(() => {
      expect(container.querySelector("[data-export-blocked]")).not.toBeNull();
    });
    const links = Array.from(container.querySelectorAll("[data-blocking-block]"));
    expect(links.map((a) => a.getAttribute("data-blocking-block"))).toEqual(["b-1", "b-2"]);
    expect(links[0].getAttribute("href")).toBe("/deliverables/del-9#b-1");
  });

  it("阻断的**原因**先说出来，不是只丢一串 id", async () => {
    fetchMock.mockResolvedValue(
      jsonOnce(
        { code: "EXPORT_BLOCKED", message: "blocking reviews open",
          detail: { blocking_block_ids: ["b-1"] } },
        409,
      ),
    );
    const { container } = await renderAsync(
      <ExportPage params={Promise.resolve({ id: "del-9" })} />,
    );
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-export-format="pdf"]')?.click();
    });

    await waitFor(() => {
      expect(container.querySelector("[data-export-blocked-reason]")).not.toBeNull();
    });
    const reason = container.querySelector("[data-export-blocked-reason]");
    expect(reason?.textContent).toContain("1");
    expect(reason?.className).toContain("job-failed");
  });

  it("后端没给清单时如实说，NEVER 显示一个空列表", async () => {
    fetchMock.mockResolvedValue(
      jsonOnce({ code: "EXPORT_BLOCKED", message: "blocked" }, 409),
    );
    const { container } = await renderAsync(
      <ExportPage params={Promise.resolve({ id: "del-9" })} />,
    );
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-export-format="pdf"]')?.click();
    });

    await waitFor(() => {
      expect(container.querySelector("[data-export-blocked-empty]")).not.toBeNull();
    });
    expect(container.textContent).toContain(messages["export.blocked.no_detail"]);
  });

  it("503 说「该格式暂不可用」，不转圈也不伪装下载", async () => {
    fetchMock.mockResolvedValue(
      jsonOnce({ code: "SERVICE_UNAVAILABLE", message: "pdf engine unavailable" }, 503),
    );
    const { container } = await renderAsync(
      <ExportPage params={Promise.resolve({ id: "del-9" })} />,
    );
    await act(async () => {
      container.querySelector<HTMLButtonElement>('[data-export-format="pdf"]')?.click();
    });

    await waitFor(() => {
      expect(container.querySelector("[data-export-unavailable]")).not.toBeNull();
    });
    expect(container.querySelector("[data-export-pending]")).toBeNull();
    expect(container.querySelector("[data-export-blocked]")).toBeNull();
  });

  it("五种格式都摆在面上，一个不少", async () => {
    const { container } = await renderAsync(
      <ExportPage params={Promise.resolve({ id: "del-9" })} />,
    );

    const formats = Array.from(container.querySelectorAll("[data-export-format]")).map((b) =>
      b.getAttribute("data-export-format"),
    );
    expect(formats).toEqual(["markdown", "html", "pdf", "docx", "pack"]);
  });
});
