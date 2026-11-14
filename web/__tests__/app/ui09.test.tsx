/**
 * UI-09 · 质量卡（蓝本 R3）与陈旧重核横幅（蓝本 R4）。
 *
 * 三条最要紧的判据：
 *
 * 1. **覆盖率给两个数，NEVER 给一个比例**（技术约束清单第 1 条）；
 * 2. **「没查过」NEVER 显示成 0 / 最新**；
 * 3. **陈旧不隐藏内容**——横幅够不着正文，也就藏不了。
 */
import { render, screen } from "@testing-library/react";
import { Suspense, act } from "react";
import { describe, expect, it, vi } from "vitest";

import { QualityCard, type QualityView } from "../../components/quality/QualityCard";
import { StalenessBanner, type StalenessView } from
  "../../components/quality/StalenessBanner";
import QualityPage from "../../app/deliverables/[id]/quality/page";
import zh from "../../messages/zh.json";

const quality = (over: Partial<QualityView> = {}): QualityView => ({
  blocksWithRefs: 1,
  blocksCounted: 6,
  blocksExcludedUser: 2,
  unresolved: { count: 0, ids: [] },
  gapHintRefs: [],
  blockingBlockIds: [],
  advisoryOpen: 0,
  exportable: true,
  ...over,
});

describe("UI-09 · R3 覆盖率给两个数", () => {
  it("分子与分母都在屏上，且**没有百分比**", () => {
    const { container } = render(<QualityCard quality={quality()} />);

    expect(container.textContent).toContain("6");
    expect(container.textContent).toContain("1");
    expect(container.textContent).not.toContain("%");
  });

  it("屏上每个数都是整数（出现小数就意味着有人算了商）", () => {
    const { container } = render(<QualityCard quality={quality()} />);
    const numbers = container.textContent?.match(/\d+(\.\d+)?/g) ?? [];

    expect(numbers.every((n) => !n.includes("."))).toBe(true);
  });

  it("被排除的用户块数一并报出（否则分母为什么比总块数小说不清）", () => {
    render(<QualityCard quality={quality({ blocksExcludedUser: 2 })} />);

    expect(screen.getByText(/另有 2 个块/)).toBeTruthy();
  });

  it("没查过质量卡 → 「接口未提供」", () => {
    const { container } = render(<QualityCard quality={null} />);

    expect(container.querySelector("[data-quality-state]")?.getAttribute(
      "data-quality-state")).toBe("not_provided");
    expect(screen.getByText(zh["quality.not_provided"])).toBeTruthy();
  });
});

describe("UI-09 · R3 「没查过」不是「是 0」", () => {
  it("未解引用没查过 → 说没查过，NEVER 显示 0", () => {
    const { container } = render(<QualityCard quality={quality({ unresolved: null })} />);

    expect(container.querySelector("[data-unresolved-state]")?.getAttribute(
      "data-unresolved-state")).toBe("not_checked");
    expect(screen.getByText(zh["quality.unresolved.not_checked"])).toBeTruthy();
  });

  it("查过了、确实是 0 → 说 0", () => {
    render(<QualityCard quality={quality({ unresolved: { count: 0, ids: [] } })} />);

    expect(screen.getByText(/查过了：0 处/)).toBeTruthy();
  });

  it("解不开的引用逐个列出（只报个数没法定位）", () => {
    render(<QualityCard quality={quality({
      unresolved: { count: 2, ids: ["cite-1", "cite-2"] },
    })} />);

    expect(screen.getByText("cite-1")).toBeTruthy();
    expect(screen.getByText("cite-2")).toBeTruthy();
  });
});

describe("UI-09 · R3 两级复核不混", () => {
  it("阻断级逐个点名并说明挡了导出", () => {
    render(<QualityCard quality={quality({
      blockingBlockIds: ["b-1"], exportable: false,
    })} />);

    expect(screen.getByText("b-1")).toBeTruthy();
    expect(screen.getByText(zh["quality.blocked"])).toBeTruthy();
  });

  it("建议级不挡导出", () => {
    const { container } = render(<QualityCard quality={quality({
      advisoryOpen: 3, exportable: true,
    })} />);

    expect(screen.getByText(/3 项建议级/)).toBeTruthy();
    expect(container.querySelector('[data-exportable="true"]')).toBeTruthy();
  });

  it("两级各有各的标记", () => {
    const { container } = render(<QualityCard quality={quality()} />);

    expect(container.querySelector('[data-review-level="blocking"]')).toBeTruthy();
    expect(container.querySelector('[data-review-level="advisory"]')).toBeTruthy();
  });
});

describe("UI-09 · R4 陈旧横幅", () => {
  const checked = (over: Partial<Extract<StalenessView, { status: "checked" }>> = {}):
    StalenessView => ({
    status: "checked", stale: true, severity: "blocking", factIds: ["f-1"],
    revalidatable: true, whyNot: null, ...over,
  });

  it("陈旧时只加标记，**不接收也不渲染正文**", () => {
    const { container } = render(<StalenessBanner staleness={checked()} />);

    // 组件的 props 里根本没有正文——够不着，也就藏不了。
    expect(container.textContent).not.toContain("正文");
    expect(screen.getByText(zh["staleness.stale"])).toBeTruthy();
  });

  it("陈旧时列出是哪几条事实变了", () => {
    render(<StalenessBanner staleness={checked({ factIds: ["f-9"] })} />);

    expect(screen.getByText("f-9")).toBeTruthy();
  });

  it("没判过 NEVER 说成「仍是最新」", () => {
    const { container } = render(<StalenessBanner staleness={{
      status: "not_checked", reason: "快照没记版本", revalidatable: false,
      whyNot: "无从与旧结果对比",
    }} />);

    expect(screen.getByText(zh["staleness.not_checked"])).toBeTruthy();
    expect(screen.queryByText(zh["staleness.fresh"])).toBeNull();
    expect(container.querySelector("[data-staleness-stale]")?.getAttribute(
      "data-staleness-stale")).toBe("unknown");
  });

  it("不可重核时说**为什么**，不是一个灰按钮", () => {
    const { container } = render(<StalenessBanner staleness={checked({
      revalidatable: false, whyNot: "还没到期，也没有事件触发",
    })} />);

    expect(container.querySelector("button")).toBeNull();
    expect(screen.getByText("还没到期，也没有事件触发")).toBeTruthy();
  });

  it("可重核时给按钮", () => {
    const { container } = render(<StalenessBanner staleness={checked()} />);

    expect(container.querySelector("button")).toBeTruthy();
  });

  it("没查过陈旧态时**不挂横幅**（常驻位上不留恒久噪音）", () => {
    const { container } = render(<StalenessBanner staleness={null} />);

    expect(container.innerHTML).toBe("");
  });
});

describe("UI-09 · 屏本体", () => {
  it("一个请求都不发，质量卡说「接口未提供」，横幅不挂", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(
        <Suspense fallback={null}>
          <QualityPage params={Promise.resolve({ id: "d-1" })} />
        </Suspense>,
      ));
    });

    expect(screen.getByText(zh["quality.not_provided"])).toBeTruthy();
    expect(container.querySelector(".staleness")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("两组件用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of Object.keys(zh).filter(
      (k) => k.startsWith("quality.") || k.startsWith("staleness."))) {
      expect(en[key]).toBeTruthy();
    }
  });
});
