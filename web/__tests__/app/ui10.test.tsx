/**
 * UI-10 · vibe_pack 查看器（蓝本 P12）。
 *
 * 三条最要紧的判据：
 *
 * 1. **与报告长得明显不同**（技术约束清单第 31 条）——它是清单不是文章；
 * 2. **Human Digest 带着「不进 AI 上下文」的标记**；
 * 3. **「尚未生成」不是 404，也不是一个空包**。
 */
import { render, screen } from "@testing-library/react";
import { Suspense, act } from "react";
import { describe, expect, it, vi } from "vitest";

import { PackViewer, type PackView } from "../../components/pack-viewer/PackViewer";
import PackPage from "../../app/deliverables/[id]/pack/page";
import zh from "../../messages/zh.json";

const pack = (over: Partial<PackView> = {}): PackView => ({
  status: "generated",
  chapters: [
    { id: "S1", title: "Charter", body: "目标：V1 商用 MVP" },
    { id: "S2", title: "Invariants", body: "结论必有引用" },
  ],
  humanDigest: { body: "监工视图正文", forAiContext: false },
  tasks: [{ id: "M1-001", title: "建库" }],
  contracts: [{ name: "models.py", sha256: "abc123" }],
  ...over,
});

describe("UI-10 · 与报告长得明显不同（清单第 31 条）", () => {
  it("排版是**清单**，不是文章", () => {
    const { container } = render(<PackViewer pack={pack()} />);

    expect(container.querySelector('[data-pack-layout="checklist"]')).toBeTruthy();
    expect(container.querySelectorAll("ol.pack__chapters")).toHaveLength(1);
    expect(container.querySelector("table.pack__tasks")).toBeTruthy();
  });

  it("章节正文走 `<pre>`（要被逐字取走的东西，任何重排都会改到它）", () => {
    const { container } = render(<PackViewer pack={pack()} />);
    const bodies = container.querySelectorAll("pre.pack__chapter-body");

    expect(bodies).toHaveLength(2);
    expect(bodies[0]?.textContent).toBe("目标：V1 商用 MVP");
  });

  it("屏上明说这份材料是给 AI 执行者的", () => {
    render(<PackViewer pack={pack()} />);

    expect(screen.getByText(zh["pack.audience"])).toBeTruthy();
  });

  it("章节按后端给的顺序逐条列出（零计算：不排序、不合并）", () => {
    const { container } = render(<PackViewer pack={pack()} />);
    const titles = [...container.querySelectorAll(".pack__chapter-title")]
      .map((n) => n.textContent);

    expect(titles).toEqual(["S1 · Charter", "S2 · Invariants"]);
  });

  it("NEVER 合成「完整度 8/9 章」这类分值", () => {
    const { container } = render(<PackViewer pack={pack()} />);

    expect(container.textContent).not.toContain("%");
    expect(container.textContent).not.toMatch(/\d\s*\/\s*9/);
  });
});

describe("UI-10 · Human Digest 不进 AI 上下文", () => {
  it("标记被**显示出来**（不显示的话用户会连它一起复制走）", () => {
    const { container } = render(<PackViewer pack={pack()} />);

    expect(screen.getByText(zh["pack.digest.not_for_ai"])).toBeTruthy();
    expect(container.querySelector('[data-for-ai-context="false"]')).toBeTruthy();
  });

  it("Digest 与九章在结构上分开（不在同一个列表里）", () => {
    const { container } = render(<PackViewer pack={pack()} />);
    const chapters = container.querySelector("ol.pack__chapters");

    expect(chapters?.textContent).not.toContain("监工视图正文");
  });

  it("没有 digest 时不画那一块", () => {
    const { container } = render(<PackViewer pack={pack({ humanDigest: null })} />);

    expect(container.querySelector(".pack__digest")).toBeNull();
  });
});

describe("UI-10 · 三种「没有」", () => {
  it("没查过 → 「接口未提供」", () => {
    const { container } = render(<PackViewer pack={null} />);

    expect(container.querySelector("[data-pack-state]")?.getAttribute(
      "data-pack-state")).toBe("not_provided");
    expect(screen.getByText(zh["pack.not_provided"])).toBeTruthy();
  });

  it("查过了、还没生成 → 说还没生成，NEVER 画九章骨架冒充生成过", () => {
    const { container } = render(<PackViewer pack={pack({
      status: "not_generated", chapters: [], humanDigest: null, tasks: [], contracts: [],
    })} />);

    expect(container.querySelector("[data-pack-state]")?.getAttribute(
      "data-pack-state")).toBe("not_generated");
    expect(screen.getByText(zh["pack.not_generated"])).toBeTruthy();
    expect(container.querySelectorAll(".pack__chapter")).toHaveLength(0);
  });

  it("两种「没有」用不同标记", () => {
    const a = render(<PackViewer pack={null} />);
    const b = render(<PackViewer pack={pack({ status: "not_generated", chapters: [] })} />);

    expect(a.container.querySelector("[data-pack-state]")?.getAttribute("data-pack-state"))
      .not.toBe(b.container.querySelector("[data-pack-state]")?.getAttribute("data-pack-state"));
  });
});

describe("UI-10 · 冻结件指纹逐字带上", () => {
  it("每个冻结件都带 sha256（包里那份与仓里那份对不对得上，靠的就是它）", () => {
    render(<PackViewer pack={pack()} />);

    expect(screen.getByText("models.py")).toBeTruthy();
    expect(screen.getByText("abc123")).toBeTruthy();
  });

  it("任务清单逐行列出", () => {
    render(<PackViewer pack={pack()} />);

    expect(screen.getByText("M1-001")).toBeTruthy();
    expect(screen.getByText(/任务清单：1 条/)).toBeTruthy();
  });
});

describe("UI-10 · 屏本体", () => {
  it("一个请求都不发，说的是「接口未提供」而非「尚未生成」", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <PackPage params={Promise.resolve({ id: "d-1" })} />
        </Suspense>,
      );
    });

    expect(screen.getByText(zh["pack.not_provided"])).toBeTruthy();
    expect(screen.queryByText(zh["pack.not_generated"])).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of Object.keys(zh).filter((k) => k.startsWith("pack."))) {
      expect(en[key]).toBeTruthy();
    }
  });
});
