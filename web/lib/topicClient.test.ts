import { describe, it, expect, vi } from "vitest";
import {
  fetchTopic,
  fetchProjectTopics,
  createCombo,
  submitTopicAnalysis,
  topicKeywords,
  comboCountValid,
  TopicNotFound,
  type Topic,
} from "./topicClient";

// TS-008 主题客户端。全离线（mock fetch，S2-7）。

const TOPIC: Topic = {
  topic_id: "t1", seed_id: "s1", one_liner: "一句话主题",
  target_user_tag: "研究团队", form_factor_tag: "SaaS",
  why_now: { claim: "现在正当时", evidences: [], speculative: true },
  keyword_mapping: { 扩散模型: ["diffusion", "生成式"], 药物: ["diffusion"] },
};

function jsonRes(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("topicKeywords / comboCountValid", () => {
  it("keyword_mapping 键+值扁平去重", () => {
    expect(topicKeywords(TOPIC)).toEqual(["扩散模型", "diffusion", "生成式", "药物"]);
  });
  it("combo 计数 2~5 校验", () => {
    expect(comboCountValid(1)).toBe(false);
    expect(comboCountValid(2)).toBe(true);
    expect(comboCountValid(5)).toBe(true);
    expect(comboCountValid(6)).toBe(false);
  });
});

describe("fetchTopic", () => {
  it("200 → Topic", async () => {
    const f = vi.fn().mockResolvedValue(jsonRes({ topic: TOPIC }));
    const got = await fetchTopic("t1", { fetchImpl: f as unknown as typeof fetch });
    expect(got.one_liner).toBe("一句话主题");
    expect((f.mock.calls[0][0] as string)).toContain("/topics/t1");
  });
  it("404 → TopicNotFound", async () => {
    const f = vi.fn().mockResolvedValue(jsonRes({}, 404));
    await expect(
      fetchTopic("nope", { fetchImpl: f as unknown as typeof fetch }),
    ).rejects.toBeInstanceOf(TopicNotFound);
  });
});

describe("fetchProjectTopics", () => {
  it("200 → project topics + chosen", async () => {
    const f = vi.fn().mockResolvedValue(
      jsonRes({ project_id: "p1", chosen_topic_id: "t1", topics: [TOPIC] }),
    );
    const got = await fetchProjectTopics("p1", { fetchImpl: f as unknown as typeof fetch });
    expect(got.chosen_topic_id).toBe("t1");
    expect(got.topics.map((x) => x.topic_id)).toEqual(["t1"]);
  });
});

describe("createCombo", () => {
  it("2~5 卡 + 假设 → POST /projects/combo", async () => {
    const f = vi.fn().mockResolvedValue(
      jsonRes({ project_id: "p1", topic_ids: ["t1", "t2"] }),
    );
    const got = await createCombo(["card-a", "card-b"], "跨热点假设", {
      fetchImpl: f as unknown as typeof fetch,
    });
    expect(got.project_id).toBe("p1");
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/projects/combo");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      card_ids: ["card-a", "card-b"], hypothesis: "跨热点假设",
    });
  });
  it("卡数越界 → 抛，未发请求", async () => {
    const f = vi.fn();
    await expect(
      createCombo(["only-one"], "h", { fetchImpl: f as unknown as typeof fetch }),
    ).rejects.toThrow();
    expect(f).not.toHaveBeenCalled();
  });
  it("空假设 → 抛，未发请求", async () => {
    const f = vi.fn();
    await expect(
      createCombo(["a", "b"], "   ", { fetchImpl: f as unknown as typeof fetch }),
    ).rejects.toThrow();
    expect(f).not.toHaveBeenCalled();
  });
});

describe("submitTopicAnalysis", () => {
  it("POST /analysis 带 topic_id", async () => {
    const f = vi.fn().mockResolvedValue(jsonRes({ job_id: "job-1" }));
    const got = await submitTopicAnalysis("p1", "t1", 10, {
      fetchImpl: f as unknown as typeof fetch,
    });
    expect(got.job_id).toBe("job-1");
    const [url, init] = f.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/projects/p1/analysis");
    expect(JSON.parse(init.body as string)).toEqual({ topic_id: "t1", budget_cny: 10 });
  });
});
