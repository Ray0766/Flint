// FIX-11：三种「拿不到」在屏上说三句**互不相同**的话。
//
// 这一层只能在**渲染**上量：源码层看不出两个分支渲染出同一句——
// 而那正是改前的实况（带 `code` 的 404 掉进 `failed`，
// 屏上写「取数出错」，说的却是「这一条不存在」）。
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScreenFetchState } from "./ScreenFetchState";
import type { Fetched } from "./screenClient";
import { fetchScreen } from "./screenClient";

const NEVER_RENDERED = (): null => null;

function textOf(state: Fetched<unknown>): string {
  const { container } = render(
    <ScreenFetchState state={state}>{NEVER_RENDERED}</ScreenFetchState>,
  );
  return (container.textContent ?? "").trim();
}

function markerOf(state: Fetched<unknown>): string | null {
  const { container } = render(
    <ScreenFetchState state={state}>{NEVER_RENDERED}</ScreenFetchState>,
  );
  const node = container.querySelector("[data-screen-state]");
  return node ? node.getAttribute("data-screen-state") : null;
}

const NOT_FOUND: Fetched<unknown> = {
  kind: "not_found", code: "NOT_FOUND", detail: "unknown topic: t-9",
};
const NOT_PROVIDED: Fetched<unknown> = { kind: "not_provided" };
const FAILED: Fetched<unknown> = { kind: "failed", status: 500, detail: "boom" };

describe("FIX-11 三种拿不到", () => {
  it("三句话互不相同", () => {
    const said = [textOf(NOT_FOUND), textOf(NOT_PROVIDED), textOf(FAILED)];

    expect(new Set(said).size).toBe(3);
    for (const one of said) expect(one.length).toBeGreaterThan(0);
  });

  it("三个取证标记互不相同", () => {
    const marks = [markerOf(NOT_FOUND), markerOf(NOT_PROVIDED), markerOf(FAILED)];

    expect(marks).toEqual(["not_found", "not_provided", "failed"]);
  });

  it("后端那句说明原样带出，NEVER 改写成一句「找不到」", () => {
    // `BE-09` 把**无权**与**不存在**收进同一条路（分开说等于告诉未授权的人
    // 这个 id 存在），所以那句话得由后端来说。
    expect(textOf(NOT_FOUND)).toContain("unknown topic: t-9");
  });

  it("调用方给的 what 会用上，不给时退到通用的那一句", () => {
    const { container } = render(
      <ScreenFetchState state={NOT_FOUND} what="这份交付物">
        {NEVER_RENDERED}
      </ScreenFetchState>,
    );

    expect(container.textContent).toContain("这份交付物");
    expect(textOf(NOT_FOUND)).not.toContain("这份交付物");
  });
});

describe("FIX-11 取数层的三支", () => {
  const respond = (status: number, body: unknown): typeof fetch =>
    (async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": "application/json" },
      })) as unknown as typeof fetch;

  it("404 带 code → not_found（应用说这一条不存在）", async () => {
    const got = await fetchScreen("/x", {
      fetchImpl: respond(404, { code: "NOT_FOUND", message: "unknown topic: t-9" }),
    });

    expect(got.kind).toBe("not_found");
    if (got.kind === "not_found") {
      expect(got.code).toBe("NOT_FOUND");
      expect(got.detail).toBe("unknown topic: t-9");
    }
  });

  it("404 不带 code → not_provided（框架说这条路由不在）", async () => {
    const got = await fetchScreen("/x", {
      fetchImpl: respond(404, { detail: "Not Found" }),
    });

    expect(got.kind).toBe("not_provided");
  });

  it("500 → failed，且原样带出状态码与后端的说明", async () => {
    const got = await fetchScreen("/x", {
      fetchImpl: respond(500, { message: "boom" }),
    });

    expect(got.kind).toBe("failed");
    if (got.kind === "failed") {
      expect(got.status).toBe(500);
      expect(got.detail).toBe("boom");
    }
  });
});
