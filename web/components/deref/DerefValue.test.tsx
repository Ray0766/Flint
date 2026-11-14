import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { DerefValue } from "../DerefValue";

// FB-09：把六类 id 换成内容的呈现层。
//
// 三种态各有各的规矩：
//   resolved    → 显示内容；
//   unavailable → **「接口未提供」+ 原 id 一起显示**（NEVER 空白、NEVER 编造）；
//   loading     → 先显示原 id（读者至少看得到「这里引的是哪一条」），
//                 NEVER 显示一片空白等着——空白读起来是「这里本来就没东西」。
//
// props 全部可序列化（无函数 prop）：`BlockView` 是 Server Component，
// **函数不能跨 Server→Client 边界传**。首版用了 `render` 函数 prop，单测全绿而真页面 500——
// 那条边界在 vitest 里根本不存在，所以这里额外钉一条「props 里没有函数」。

function res(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("解析成功 → 显示内容", () => {
  it("事实通道显示陈述与数值，而不是 fact_id", async () => {
    render(
      <DerefValue
        kind="fact"
        id="fact-demo-vecdb-cost"
        fetchImpl={async () =>
          res({ statement: "向量库托管月成本", value: 12.5, unit: "美元" })
        }
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("deref-resolved").textContent).toContain(
        "向量库托管月成本",
      ),
    );
    expect(screen.getByTestId("deref-resolved").textContent).toContain("12.5美元");
    expect(screen.queryByText("fact-demo-vecdb-cost")).toBeNull();
  });

  it("价格通道显示后端算好的金额，前端不乘", async () => {
    render(
      <DerefValue
        kind="price"
        id="p-1"
        quantity={3}
        fetchImpl={async () =>
          res({
            amount_low: 300, amount_high: 450, currency: "CNY",
            stale: false, price_data_note: null,
          })
        }
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("deref-resolved").textContent).toBe("300-450 CNY"),
    );
  });

  it("过期单价照实带注记（D13：NEVER 静默用旧价）", async () => {
    render(
      <DerefValue
        kind="price"
        id="p-2"
        quantity={1}
        fetchImpl={async () =>
          res({
            amount_low: 20, amount_high: 20, currency: "USD",
            stale: true, price_data_note: "单价数据为 2023 年",
          })
        }
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("deref-resolved").textContent).toContain("2023"),
    );
  });

  it("引用通道显示文献标题与定位符", async () => {
    render(
      <DerefValue
        kind="citation"
        id="cit-1"
        fetchImpl={async () => res({ doc: { title: "RAG in production" }, locator: "p.4" })}
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("deref-resolved").textContent).toBe(
        "RAG in production p.4",
      ),
    );
  });

  it("缺口通道逐条列出缺的是什么与为什么", async () => {
    render(
      <DerefValue
        kind="hints"
        id="h-1"
        fetchImpl={async () =>
          res({ hints: [{ missing_what: "缺少单价", why: "补充以下任一即可" }] })
        }
      />,
    );

    const list = await screen.findByTestId ? await waitFor(() =>
      screen.getByTestId("deref-resolved")) : null;
    expect(list!.textContent).toContain("缺少单价");
    expect(list!.textContent).toContain("补充以下任一即可");
  });
});

describe("端点不可用 → 如实标注，原 id 仍然可见", () => {
  it("显示「接口未提供」并把原 id 留在屏上", async () => {
    render(
      <DerefValue
        kind="card"
        id="qc-demo-fixture-01"
        fetchImpl={async () => res({ code: "NOT_FOUND" }, 404)}
      />,
    );

    const node = await screen.findByTestId("deref-unavailable");
    expect(node.textContent).toContain("qc-demo-fixture-01");
    expect(node.getAttribute("data-deref-id")).toBe("qc-demo-fixture-01");
  });

  it("**NEVER 空白**：不可用时渲染出来的文字非空", async () => {
    const { container } = render(
      <DerefValue
        kind="hints"
        id="sec-04-gap-hints"
        fetchImpl={async () => res({}, 404)}
      />,
    );

    await screen.findByTestId("deref-unavailable");
    expect(container.textContent?.trim().length ?? 0).toBeGreaterThan(0);
  });

  it("**NEVER 编造**：不可用时没有 resolved 节点（没有内容就是没有内容）", async () => {
    render(
      <DerefValue
        kind="chart"
        id="chart-demo-cost-trend"
        fetchImpl={async () => res({}, 500)}
      />,
    );

    await screen.findByTestId("deref-unavailable");
    expect(screen.queryByTestId("deref-resolved")).toBeNull();
  });
});

describe("加载中 → 先显示原 id，不空白", () => {
  it("请求未落定时屏上有原 id", () => {
    render(
      <DerefValue
        kind="citation"
        id="cit-demo-arxiv-2506-06962"
        fetchImpl={() => new Promise<Response>(() => undefined)}
      />,
    );

    expect(screen.getByTestId("deref-loading").textContent).toContain(
      "cit-demo-arxiv-2506-06962",
    );
  });
});

describe("文案走 i18n key，NEVER 中文硬编码", () => {
  it("「接口未提供」这句取自词条而不是写死在组件里", async () => {
    const zh = await import("../../messages/zh.json");
    const en = await import("../../messages/en.json");
    const key = "deref.unavailable";

    expect(Object.keys(zh.default)).toContain(key);
    expect(Object.keys(en.default)).toContain(key);
    expect((zh.default as Record<string, string>)[key]).not.toBe(
      (en.default as Record<string, string>)[key],
    );
  });
});
