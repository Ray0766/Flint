import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ComboEntryView } from "./ComboEntryView";
import { TopicListView } from "./TopicListView";
import { t } from "../../lib/i18n";
import type { EvidenceCard } from "../../lib/viewsClient";
import type { Topic } from "../../lib/topicClient";

// TS-008 combo 入口 + 主题呈现（纯呈现，mock 交互）。全离线（S2-7）。

const CARDS: EvidenceCard[] = [
  { card_id: "card-a", cluster_id: "c1", keyword_ids: ["k1"], flags: [], top_links: [] },
  { card_id: "card-b", cluster_id: "c2", keyword_ids: ["k2"], flags: [], top_links: [] },
  { card_id: "card-c", cluster_id: "c3", keyword_ids: ["k3"], flags: [], top_links: [] },
];

const TOPICS: Topic[] = [
  { topic_id: "t1", seed_id: "s1", one_liner: "接地主题",
    target_user_tag: "研究团队", form_factor_tag: "SaaS",
    why_now: { claim: "有证据", evidences: [
      { event: "e", event_date: "2026-07-01", citation_id: "cit-1" }], speculative: false },
    keyword_mapping: { 扩散: ["diffusion"] } },
  { topic_id: "t2", seed_id: "s1", one_liner: "推测主题",
    target_user_tag: "个人开发者", form_factor_tag: "插件",
    why_now: { claim: "缺证据", evidences: [], speculative: true },
    keyword_mapping: {} },
];

describe("ComboEntryView combo 入口", () => {
  it("选 2~5 卡 + 写假设 → submit 启用并回传 (跨簇允许)", () => {
    const onSubmit = vi.fn();
    const { container } = render(
      <ComboEntryView cards={CARDS} onSubmit={onSubmit} />,
    );
    const submit = container.querySelector("[data-combo-submit]") as HTMLButtonElement;
    expect(submit.disabled).toBe(true); // 初始 0 卡
    // 选 card-a(c1) + card-b(c2) = 跨簇
    fireEvent.click(container.querySelector("[data-combo-card='card-a']")!);
    fireEvent.click(container.querySelector("[data-combo-card='card-b']")!);
    expect(submit.disabled).toBe(true); // 仍缺假设
    fireEvent.change(container.querySelector("[data-combo-hypothesis]")!, {
      target: { value: "跨热点关联假设" },
    });
    expect(submit.disabled).toBe(false);
    fireEvent.click(submit);
    expect(onSubmit).toHaveBeenCalledWith(["card-a", "card-b"], "跨热点关联假设");
  });

  it("1 卡越下界 → submit 禁用 + 计数提示", () => {
    const { container } = render(<ComboEntryView cards={CARDS} onSubmit={vi.fn()} />);
    fireEvent.click(container.querySelector("[data-combo-card='card-a']")!);
    fireEvent.change(container.querySelector("[data-combo-hypothesis]")!, {
      target: { value: "有假设" },
    });
    const submit = container.querySelector("[data-combo-submit]") as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    expect(container.querySelector("[data-combo-count-error]")!.textContent).toBe(
      t("combo.count_error"));
  });
});

describe("TopicListView 主题呈现", () => {
  it("展示 one_liner/两维 tag/keywords/why_now + speculative 灰标降权", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <TopicListView topics={TOPICS} chosenTopicId={null} onSelectTopic={onSelect} />,
    );
    const items = [...container.querySelectorAll("[data-topic-id]")];
    expect(items.map((el) => el.getAttribute("data-topic-id"))).toEqual(["t1", "t2"]);
    // t1 接地：无 speculative 灰标
    const t1 = container.querySelector("[data-topic-id='t1']")!;
    expect(t1.getAttribute("data-speculative")).toBe("false");
    expect(t1.querySelector("[data-topic-speculative-mark]")).toBeNull();
    expect(t1.querySelector("[data-topic-target-user]")!.textContent).toContain("研究团队");
    expect(t1.querySelector("[data-topic-keywords]")!.textContent).toContain("diffusion");
    // t2 推测：有灰标降权
    const t2 = container.querySelector("[data-topic-id='t2']")!;
    expect(t2.getAttribute("data-speculative")).toBe("true");
    expect(t2.querySelector("[data-topic-speculative-mark]")!.textContent).toBe(
      t("topic.speculative"));
    // 选主题回传 topic_id
    fireEvent.click(t1.querySelector("[data-topic-choose='t1']")!);
    expect(onSelect).toHaveBeenCalledWith("t1");
  });

  it("chosen 高亮 + 空态", () => {
    const { container, rerender } = render(
      <TopicListView topics={TOPICS} chosenTopicId="t2" />,
    );
    expect(
      container.querySelector("[data-topic-id='t2']")!.getAttribute("data-chosen"),
    ).toBe("true");
    rerender(<TopicListView topics={[]} />);
    expect(screen.getByText(t("topic.empty"))).not.toBeNull();
  });
});
