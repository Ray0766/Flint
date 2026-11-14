/**
 * UI-04 · AI 设计工作台上屏（v2 屏 2.17）。
 *
 * 两条最要紧的判据：
 *
 * 1. **「没查过注册表」不是「注册表不可用」**——后者是替后端下的结论；
 * 2. **预览失败 NEVER 用上一次成功的顶替**（v2 2.17 原话）。
 */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DesignWorkbench, type DesignPreview } from
  "../../components/design-workbench/DesignWorkbench";
import DesignPage from "../../app/design/page";
import zh from "../../messages/zh.json";

const OK: DesignPreview = { html: "<h1>某设计</h1>", error: null };
const FAILED: DesignPreview = { html: "<h1 broken", error: "解析到一半就断了" };

// DESIGN-03 把 `registryAvailable` 从 `boolean | null` 扩成了四态
// （`not_checked` / `not_provided` / `down` / `ok`）——三态版把「这套部署根本没有
// templates 表」塞进任一已有值都是谎（`docs/blocked/
// UI-DESIGN-SCREEN-NEEDS-A-FOURTH-STATE.md` 逐条列过）。
// 下面各条**判的还是同一件事**，只是把入参换成了新的名字：
// `null → "not_checked"`、`false → "down"`、`true → "ok"`。
describe("UI-04 · 阻断的两种说法分得开", () => {
  it("没查过注册表 → 说「还没查过」，NEVER 说「不可用」", () => {
    const { container } = render(
      <DesignWorkbench preview={OK} registryAvailable="not_checked" />);

    expect(container.querySelector("[data-design-blocked]")?.getAttribute(
      "data-design-blocked")).toBe("not_checked");
    expect(screen.getByText(zh["design.solidify.not_checked"])).toBeTruthy();
    expect(screen.queryByText(zh["design.solidify.registry_down"])).toBeNull();
  });

  it("查过了、确实不可用 → 说「注册表不可用」（E6）", () => {
    const { container } = render(
      <DesignWorkbench preview={OK} registryAvailable="down" />);

    expect(container.querySelector("[data-design-blocked]")?.getAttribute(
      // DESIGN-03：判别位就是那四态本身（`down`），文案 key 仍是 registry_down。
      "data-design-blocked")).toBe("down");
    expect(screen.getByText(zh["design.solidify.registry_down"])).toBeTruthy();
  });

  it("两种阻断都置灰按钮，但说的是两句不同的话", () => {
    const unknown = render(
      <DesignWorkbench preview={OK} registryAvailable="not_checked" />);
    const down = render(
      <DesignWorkbench preview={OK} registryAvailable="down" />);

    for (const r of [unknown, down]) {
      expect(r.container.querySelector("button")?.hasAttribute("disabled")).toBe(true);
    }
    expect(
      unknown.container.querySelector("[data-design-blocked]")?.textContent,
    ).not.toBe(down.container.querySelector("[data-design-blocked]")?.textContent);
  });

  it("注册表可用时按钮能点，且不再显示阻断原因", () => {
    const onSolidify = vi.fn();
    const { container } = render(
      <DesignWorkbench preview={OK} registryAvailable="ok" onSolidify={onSolidify} />);

    // DESIGN-02 起这一屏不止一个键（生成键在固化键之前）。
    // `querySelector("button")` 取的是**第一个**，那已经不是这条判据说的那个键了——
    // 改成按类名点名。**判的仍是同一件事**：注册表可用时「固化」能点。
    expect(container.querySelector(".design__solidify")?.hasAttribute("disabled"))
      .toBe(false);
    expect(container.querySelector("[data-design-blocked]")).toBeNull();
  });

  it("阻断的是固化，探索照旧——E6 要说清还能做什么", () => {
    render(<DesignWorkbench preview={OK} registryAvailable="down" />);

    expect(screen.getByText(zh["design.explore.still_open"])).toBeTruthy();
  });
});

describe("UI-04 · 预览", () => {
  it("零构建预览走 iframe srcdoc，且关掉脚本", () => {
    const { container } = render(
      <DesignWorkbench preview={OK} registryAvailable="ok" />);
    const frame = container.querySelector("iframe");

    expect(frame?.getAttribute("srcdoc")).toContain("某设计");
    expect(frame?.getAttribute("sandbox")).toBe("");
  });

  it("失败时显示**原始产物与错误**，NEVER 顶替成上一次成功的预览", () => {
    const { container, rerender } = render(
      <DesignWorkbench preview={OK} registryAvailable="ok" />);
    expect(container.querySelector("iframe")).toBeTruthy();

    rerender(<DesignWorkbench preview={FAILED} registryAvailable="ok" />);

    // 上一版的 iframe 必须消失——留着它，用户会以为那是刚生成的这一版。
    expect(container.querySelector("iframe")).toBeNull();
    expect(container.querySelector("[data-design-preview-failed]")).toBeTruthy();
    expect(screen.getByText("<h1 broken")).toBeTruthy();
    expect(screen.getByText("解析到一半就断了")).toBeTruthy();
    expect(screen.queryByText("某设计")).toBeNull();
  });

  it("还没有产物 → 「接口未提供」，不是一张空预览", () => {
    const { container } = render(
      <DesignWorkbench preview={null} registryAvailable="not_checked" />);

    expect(container.querySelector("iframe")).toBeNull();
    expect(screen.getByText(zh["design.preview.not_provided"])).toBeTruthy();
    expect(container.getAttribute("data-design-state")).toBe(null);
    expect(container.querySelector("[data-design-state]")?.getAttribute(
      "data-design-state")).toBe("no_artifact");
  });
});

describe("UI-04 · 屏本体", () => {
  // `DESIGN-02/03` 把这条有意翻过来了：三条端点里两条真通了，不发就等于晾着；
  // 提交那条虽然没有，也照样发——「能不能提交」的真相在服务端。
  // 改判**更硬的那一件**：进屏只**查**，NEVER 提交作业（提交了的话，
  // 用户每刷新一次就多开一个作业，而他看到的只是「又从头开始了」）。
  it("渲染屏头；进屏只查注册表，NEVER 提交作业", async () => {
    const seen: string[] = [];
    const fetchMock = vi.fn((url: unknown) => {
      seen.push(String(url));
      return Promise.resolve({
        ok: true, status: 200, json: async () => ({ items: [] }),
      } as Response);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<DesignPage />);

    expect(screen.getByText(zh["design.title"])).toBeTruthy();
    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen.some((u) => u.includes("/design/templates"))).toBe(true);
    expect(seen.some((u) => u.includes("design_generate"))).toBe(false);
  });

  it("屏上两处都说「没查过」，NEVER 说成「坏了」", () => {
    render(<DesignPage />);

    expect(screen.getByText(zh["design.preview.not_provided"])).toBeTruthy();
    expect(screen.getByText(zh["design.solidify.not_checked"])).toBeTruthy();
    expect(screen.queryByText(zh["design.solidify.registry_down"])).toBeNull();
  });

  it("副标不写端点路径（FB-10 A 类）", () => {
    render(<DesignPage />);

    const meta = document.querySelector(".screen__meta")?.textContent ?? "";
    expect(meta).not.toContain("/design");
    expect(meta).not.toContain("POST");
  });
});

describe("UI-04 · 文案全部走 i18n key", () => {
  it("本屏用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of [
      "design.title", "design.meta", "design.preview.title",
      "design.preview.not_provided", "design.preview.failed",
      "design.solidify.label", "design.solidify.not_checked",
      "design.solidify.registry_down", "design.explore.still_open",
    ]) {
      expect(zh[key as keyof typeof zh]).toBeTruthy();
      expect(en[key]).toBeTruthy();
    }
  });
});
