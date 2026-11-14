import { describe, it, expect } from "vitest";
import {
  deref,
  DEREF_PATHS,
  type DerefKind,
  type DerefResult,
} from "./derefClient";

// FB-09 解引用客户端。全离线（注入 fetchImpl，S2-7）。
//
// 这个客户端只有一条产品规则，而它是本卡的正题：
// **端点不可用时如实标「接口未提供」并把原 id 交回去**——NEVER 空白、NEVER 编造。
// 空白会让读者以为那里本来就没东西；编造出来的内容没有出处，而这套系统的三条铁律
// 头一条就是「结论必有引用」。

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const KINDS: DerefKind[] = ["fact", "price", "citation", "chart", "card", "hints"];

describe("六条通道各有各的路径", () => {
  it("六种 kind 全部有路径，且互不相同", () => {
    const paths = KINDS.map((k) => DEREF_PATHS[k]("x"));
    expect(new Set(paths).size).toBe(KINDS.length);
    expect(DEREF_PATHS.fact("f-1")).toBe("/facts/f-1");
    expect(DEREF_PATHS.citation("c-1")).toBe("/citations/c-1");
    expect(DEREF_PATHS.card("qc-1")).toBe("/cards/qc-1");
    expect(DEREF_PATHS.hints("h-1")).toBe("/hints/h-1");
    expect(DEREF_PATHS.chart("ch-1")).toBe("/charts/ch-1");
  });

  it("id 进 URL 前做转义——带斜杠的 id NEVER 变成另一条路径", () => {
    expect(DEREF_PATHS.fact("a/b")).toBe("/facts/a%2Fb");
  });

  it("price 通道必须带 quantity（后端算金额，前端 NEVER 自己乘）", () => {
    expect(DEREF_PATHS.price("p-1", 3)).toBe("/price-entries/p-1?quantity=3");
  });
});

describe("解析成功", () => {
  it("200 → resolved，内容原样交回", async () => {
    const fetchImpl = async () => jsonRes({ statement: "向量库托管月成本", value: 12.5 });
    const got = await deref("fact", "f-1", { baseUrl: "http://x", fetchImpl });

    expect(got.state).toBe("resolved");
    if (got.state === "resolved") {
      expect((got.data as { statement: string }).statement).toBe("向量库托管月成本");
    }
  });
});

describe("端点不可用：如实标注 + 交回原 id", () => {
  const cases: Array<[string, () => Promise<Response>]> = [
    ["404", async () => jsonRes({ code: "NOT_FOUND" }, 404)],
    ["500", async () => jsonRes({ code: "INTERNAL" }, 500)],
    ["501 未实现", async () => jsonRes({ code: "NOT_IMPLEMENTED" }, 501)],
  ];

  for (const [label, fetchImpl] of cases) {
    it(`${label} → unavailable，且带回原 id`, async () => {
      const got = await deref("card", "qc-demo-fixture-01", {
        baseUrl: "http://x",
        fetchImpl,
      });

      expect(got.state).toBe("unavailable");
      if (got.state === "unavailable") {
        expect(got.id).toBe("qc-demo-fixture-01");
        expect(got.status).toBeGreaterThanOrEqual(400);
      }
    });
  }

  it("网络整个打不通 → 同样是 unavailable，NEVER 抛给调用方自己处理", async () => {
    const fetchImpl = async () => {
      throw new TypeError("Failed to fetch");
    };
    const got = await deref("hints", "h-1", { baseUrl: "http://x", fetchImpl });

    expect(got.state).toBe("unavailable");
    if (got.state === "unavailable") {
      expect(got.id).toBe("h-1");
      expect(got.status).toBeNull();
    }
  });

  it("**NEVER 回空内容**：unavailable 的结果里没有 data 字段", async () => {
    const fetchImpl = async () => jsonRes({}, 404);
    const got: DerefResult = await deref("fact", "f-x", {
      baseUrl: "http://x",
      fetchImpl,
    });

    expect(got.state).toBe("unavailable");
    expect("data" in got).toBe(false);
  });
});
