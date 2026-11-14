import { describe, it, expect, vi } from "vitest";
import { render, waitFor, fireEvent } from "@testing-library/react";
import { DemoFlow } from "./DemoFlow";

// TS-012 可点击 demo 流：广场→点簇→工作台→combo→主题→选主题→Gate。
// 全离线（mock fetch，S2-7）：一个 fetchImpl 按 URL 路由所有步的响应。

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const TOPIC = {
  topic_id: "tp1", seed_id: "s1", one_liner: "接地主题",
  target_user_tag: "研究团队", form_factor_tag: "SaaS",
  why_now: { claim: "有据", evidences: [], speculative: false },
  keyword_mapping: { 扩散: ["diffusion"] },
};

function routedFetch(): typeof fetch {
  const f = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const u = String(url);
    if (u.includes("/plaza/hot")) {
      return jsonRes({ clusters: [
        { cluster_id: "c1", canonical_name: "热点甲", category_id: "cat", status: "active",
          by_source: { arxiv: 0.9 }, total_heat: 0.9 },
      ] });
    }
    if (u.includes("/evidence-cards")) {
      return jsonRes({ evidence_cards: [
        { card_id: "card-a", cluster_id: "c1", keyword_ids: ["k"], flags: [], top_links: [] },
        { card_id: "card-b", cluster_id: "c2", keyword_ids: ["k"], flags: [], top_links: [] },
      ] });
    }
    if (u.includes("/projects/combo")) {
      return jsonRes({ project_id: "proj-1", topic_ids: ["tp1"], degraded: false });
    }
    if (u.includes("/topics") && u.includes("/projects/")) {
      return jsonRes({ project_id: "proj-1", chosen_topic_id: null, topics: [TOPIC] });
    }
    if (u.includes("/analysis")) {
      expect(init?.method).toBe("POST");
      return jsonRes({ job_id: "job-9" });
    }
    throw new Error(`unexpected url ${u}`);
  });
  return f as unknown as typeof fetch;
}

describe("DemoFlow 端到端可点击流", () => {
  it("广场→点簇→工作台+combo→主题→选主题→Gate（路由到进度页）", async () => {
    const opts = { fetchImpl: routedFetch() };
    const { container } = render(<DemoFlow day="2026-07-20" opts={opts} />);
    // step=plaza：加载广场
    expect(container.querySelector("[data-demo-flow]")!.getAttribute("data-step"))
      .toBe("plaza");
    fireEvent.click(container.querySelector("[data-demo-load-plaza]")!);
    await waitFor(() =>
      expect(container.querySelector("[data-cluster-id='c1']")).not.toBeNull());
    // 点簇 → workbench + combo 入口
    fireEvent.click(container.querySelector("[data-cluster-id='c1']")!);
    await waitFor(() =>
      expect(container.querySelector("[data-demo-flow]")!.getAttribute("data-step"))
        .toBe("workbench"));
    expect(container.querySelector("[data-combo-entry]")).not.toBeNull();
    // combo：选 2 卡（跨簇 c1+c2）+ 假设 → 提交
    fireEvent.click(container.querySelector("[data-combo-card='card-a']")!);
    fireEvent.click(container.querySelector("[data-combo-card='card-b']")!);
    fireEvent.change(container.querySelector("[data-combo-hypothesis]")!, {
      target: { value: "跨热点假设" },
    });
    fireEvent.click(container.querySelector("[data-combo-submit]")!);
    // → topics
    await waitFor(() =>
      expect(container.querySelector("[data-demo-flow]")!.getAttribute("data-step"))
        .toBe("topics"));
    expect(container.querySelector("[data-topic-id='tp1']")).not.toBeNull();
    // 选主题 → gate（路由到 /jobs/{id}）
    fireEvent.click(container.querySelector("[data-topic-choose='tp1']")!);
    await waitFor(() =>
      expect(container.querySelector("[data-demo-flow]")!.getAttribute("data-step"))
        .toBe("gate"));
    const link = container.querySelector("[data-demo-job-link]") as HTMLAnchorElement;
    expect(link.getAttribute("href")).toBe("/jobs/job-9");
    expect(container.querySelector("[data-demo-chosen-topic]")!.textContent).toBe("tp1");
  });
});
