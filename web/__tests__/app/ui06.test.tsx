/**
 * UI-06 · 外链只读查看页（v2 屏 2.18）。
 *
 * 最要紧的一条：**四种处境四句话**。
 * 全报「没有」看起来更安全，实际是让持链人无从判断下一步该做什么。
 */
import { render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { ShareViewer, type ShareOutcome } from
  "../../components/share-viewer/ShareViewer";
import SharePage from "../../app/share/[token]/page";
import zh from "../../messages/zh.json";

const state = (c: HTMLElement): string | null | undefined =>
  c.querySelector("[data-share-state]")?.getAttribute("data-share-state");

const cases: Array<[string, ShareOutcome, string]> = [
  ["not_provided", { kind: "not_provided" }, zh["share.not_provided"]],
  ["unknown", { kind: "unknown" }, zh["share.unknown"]],
  ["gone", { kind: "gone", reason: "expired" }, zh["share.gone.expired"]],
  ["password_required", { kind: "password_required" }, zh["share.password_required"]],
];

describe("UI-06 · 四种处境四句话", () => {
  it.each(cases)("%s 有自己的标记与自己的话", (mark, outcome, text) => {
    const { container } = render(<ShareViewer outcome={outcome} />);

    expect(state(container)).toBe(mark);
    expect(screen.getByText(text)).toBeTruthy();
  });

  it("「没有这个链接」与「链接失效了」NEVER 说成同一句", () => {
    const unknown = render(<ShareViewer outcome={{ kind: "unknown" }} />);
    const gone = render(
      <ShareViewer outcome={{ kind: "gone", reason: "revoked" }} />);

    expect(unknown.container.textContent).not.toBe(gone.container.textContent);
    expect(state(unknown.container)).not.toBe(state(gone.container));
  });

  it("「没查过」与「没有这个链接」也 NEVER 说成同一句", () => {
    const notProvided = render(<ShareViewer outcome={{ kind: "not_provided" }} />);
    const unknown = render(<ShareViewer outcome={{ kind: "unknown" }} />);

    expect(state(notProvided.container)).not.toBe(state(unknown.container));
  });

  it("失效时给出路：去找分享的人要一条新的", () => {
    render(<ShareViewer outcome={{ kind: "gone", reason: null }} />);

    expect(screen.getByText(zh["share.gone.hint"])).toBeTruthy();
  });
});

describe("UI-06 · 410 里的理由拿不到时 NEVER 猜", () => {
  it("后端只说 410 → 用中性那句，不说「已过期」", () => {
    const { container } = render(
      <ShareViewer outcome={{ kind: "gone", reason: null }} />);

    expect(screen.getByText(zh["share.gone.unspecified"])).toBeTruthy();
    expect(screen.queryByText(zh["share.gone.expired"])).toBeNull();
    expect(screen.queryByText(zh["share.gone.revoked"])).toBeNull();
    expect(container.querySelector("[data-share-gone-reason]")?.getAttribute(
      "data-share-gone-reason")).toBe("unspecified");
  });

  it("后端说了是撤销就说撤销", () => {
    render(<ShareViewer outcome={{ kind: "gone", reason: "revoked" }} />);

    expect(screen.getByText(zh["share.gone.revoked"])).toBeTruthy();
  });

  it("三种理由各带各的标记", () => {
    const reasons: Array<"expired" | "revoked" | null> = ["expired", "revoked", null];
    const marks = reasons.map((reason) => {
      const { container } = render(<ShareViewer outcome={{ kind: "gone", reason }} />);
      return container.querySelector("[data-share-gone-reason]")?.getAttribute(
        "data-share-gone-reason");
    });

    expect(new Set(marks).size).toBe(3);
  });
});

describe("UI-06 · 只读", () => {
  it("拿到内容时也**没有任何干预控件**", () => {
    const { container } = render(
      <ShareViewer outcome={{ kind: "ready", title: "某报告", body: "正文" }} />);

    expect(screen.getByText("某报告")).toBeTruthy();
    expect(container.querySelectorAll("button")).toHaveLength(0);
    expect(container.querySelectorAll("input")).toHaveLength(0);
    expect(container.querySelectorAll("textarea")).toHaveLength(0);
  });

  it("并且明说这是只读", () => {
    render(<ShareViewer outcome={{ kind: "ready", title: "某报告", body: "正文" }} />);

    expect(screen.getByText(zh["share.readonly"])).toBeTruthy();
  });
});

describe("UI-06 · 屏本体", () => {
  it("渲染屏头，且一个请求都不发", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <SharePage params={Promise.resolve({ token: "tk-1" })} />
        </Suspense>,
      );
    });

    expect(screen.getByText(zh["share.title"])).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("屏上说的是「接口未提供」，不是「没有这个链接」", async () => {
    await act(async () => {
      render(
        <Suspense fallback={null}>
          <SharePage params={Promise.resolve({ token: "tk-1" })} />
        </Suspense>,
      );
    });

    expect(screen.getByText(zh["share.not_provided"])).toBeTruthy();
    expect(screen.queryByText(zh["share.unknown"])).toBeNull();
  });

  it("屏上不显示 token（外链页面上不该有内部 id）", async () => {
    await act(async () => {
      render(
        <Suspense fallback={null}>
          <SharePage params={Promise.resolve({ token: "tk-secret" })} />
        </Suspense>,
      );
    });

    expect(document.body.textContent).not.toContain("tk-secret");
  });

  it("本屏用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of [
      "share.title", "share.meta", "share.not_provided", "share.unknown",
      "share.gone.expired", "share.gone.revoked", "share.gone.unspecified",
      "share.gone.hint", "share.password_required", "share.readonly",
    ]) {
      expect(zh[key as keyof typeof zh]).toBeTruthy();
      expect(en[key]).toBeTruthy();
    }
  });
});
