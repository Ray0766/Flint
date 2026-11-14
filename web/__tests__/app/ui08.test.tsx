/**
 * UI-08 · 账户屏（蓝本 R1）与额度计费屏（蓝本 R2）。
 *
 * 三条最要紧的判据：
 *
 * 1. **「计费未启用」不是「余额 0」**，**「没查过」也不是「未启用」**；
 * 2. **金额恒是字符串**——前端一处运算都没有；
 * 3. **余量是后端给的数**——NEVER 前端拿 limit - used 自己减。
 */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountPanel, type AccountView } from
  "../../components/account-billing/AccountPanel";
import { BillingPanel, type BillingView } from
  "../../components/account-billing/BillingPanel";
import AccountPage from "../../app/account/page";
import BillingPage from "../../app/billing/page";
import zh from "../../messages/zh.json";

const account = (over: Partial<AccountView> = {}): AccountView => ({
  principalId: "u-me",
  profile: { status: "known", displayName: "某研究者", email: "me@example.com" },
  memberships: [],
  direct: { kind: "user", id: "u-me", role: "owner" },
  ...over,
});

const billing = (over: Partial<BillingView> = {}): BillingView => ({
  billing: { status: "enabled", currency: "CNY", pricingVersion: "pb-1" },
  quota: { status: "enabled", used: 3, limit: 10, remaining: 7, exhausted: false, shortfall: 0 },
  events: [],
  reconciliation: { count: 0, total: "0", mixedPricing: false },
  ...over,
});

describe("UI-08 · R1 账户：三态照后端逐字转出", () => {
  it("没查过账户 → 「接口未提供」", () => {
    const { container } = render(<AccountPanel account={null} />);

    expect(container.querySelector("[data-account-state]")?.getAttribute(
      "data-account-state")).toBe("not_provided");
    expect(screen.getByText(zh["account.not_provided"])).toBeTruthy();
  });

  it("档案三态各说各的话", () => {
    for (const [status, text] of [
      ["not_checked", zh["account.profile.not_checked"]],
      ["no_record", zh["account.profile.no_record"]],
    ] as const) {
      const { container } = render(
        <AccountPanel account={account({ profile: { status } })} />);
      expect(container.querySelector(`[data-account-profile="${status}"]`)).toBeTruthy();
      expect(screen.getByText(text)).toBeTruthy();
    }
  });

  it("「没查过档案」NEVER 说成「没有你的档案」", () => {
    render(<AccountPanel account={account({ profile: { status: "not_checked" } })} />);

    expect(screen.queryByText(zh["account.profile.no_record"])).toBeNull();
  });

  it("没查过组织关系 NEVER 说成「不属于任何组织」", () => {
    const { container } = render(
      <AccountPanel account={account({ memberships: null })} />);

    expect(container.querySelector("[data-account-memberships]")?.getAttribute(
      "data-account-memberships")).toBe("not_checked");
    expect(screen.getByText(zh["account.memberships.not_checked"])).toBeTruthy();
    expect(screen.queryByText(zh["account.memberships.none"])).toBeNull();
  });

  it("查过了、确实不属于任何组织时才说那句话", () => {
    render(<AccountPanel account={account({ memberships: [] })} />);

    expect(screen.getByText(zh["account.memberships.none"])).toBeTruthy();
  });
});

describe("UI-08 · R2 计费：未启用 ≠ 余额 0，没查过 ≠ 未启用", () => {
  it("没查过 → 「接口未提供」，NEVER 说「计费未启用」", () => {
    const { container } = render(<BillingPanel billing={null} />);

    expect(container.querySelector("[data-billing-state]")?.getAttribute(
      "data-billing-state")).toBe("not_provided");
    expect(screen.queryByText(zh["billing.not_enabled"])).toBeNull();
  });

  it("查过了、计费未启用 → 说未启用，并给出后端的理由", () => {
    const { container } = render(<BillingPanel billing={billing({
      billing: { status: "not_enabled", reason: "四项任缺其一" },
      quota: { status: "not_enabled", used: 3 },
    })} />);

    expect(container.querySelector("[data-billing-state]")?.getAttribute(
      "data-billing-state")).toBe("not_enabled");
    expect(screen.getByText(zh["billing.not_enabled"])).toBeTruthy();
    expect(screen.getByText("四项任缺其一")).toBeTruthy();
  });

  it("未启用时**不显示任何额度上限**（`limit: 0` 会被读成「免费额度 0 次」）", () => {
    const { container } = render(<BillingPanel billing={billing({
      billing: { status: "not_enabled", reason: "未定价" },
      quota: { status: "not_enabled", used: 3 },
    })} />);

    expect(container.querySelector("[data-quota-state]")?.getAttribute(
      "data-quota-state")).toBe("not_enabled");
    // 判**数字个数**而不是判词：文案里那句「还没有额度上限这回事」本身就带着
    // 「上限」二字（它正是在说没有上限），判词会被自己的文案喂饱。
    // 未启用时额度块里只该有一个数——已用次数。
    const quotaText = container.querySelector("[data-quota-state]")?.textContent ?? "";
    expect(quotaText.match(/\d+/g)).toEqual(["3"]);
  });

  it("没查过用量 → 说没查过，NEVER 显示 0", () => {
    render(<BillingPanel billing={billing({ quota: { status: "not_checked" } })} />);

    expect(screen.getByText(zh["billing.quota.not_checked"])).toBeTruthy();
  });
});

describe("UI-08 · 余量与金额都由后端给", () => {
  it("余量原样显示，不是前端相减", () => {
    // 故意给一个「不自洽」的组合：若前端自己减，会显示 7 而不是 4。
    render(<BillingPanel billing={billing({
      quota: { status: "enabled", used: 3, limit: 10, remaining: 4, exhausted: false, shortfall: 0 },
    })} />);

    expect(screen.getByText(/还剩 4 次/)).toBeTruthy();
  });

  it("超额时说还差多少", () => {
    const { container } = render(<BillingPanel billing={billing({
      quota: { status: "enabled", used: 12, limit: 10, remaining: 0, exhausted: true, shortfall: 3 },
    })} />);

    expect(container.querySelector("[data-quota-exhausted]")).toBeTruthy();
    expect(screen.getByText(/还差 3 次/)).toBeTruthy();
  });

  it("金额原样渲染（字符串），不转数字不四舍五入", () => {
    render(<BillingPanel billing={billing({
      events: [{
        jobId: "job-1", tier: "deep", at: "2026-03-04T05:06:00+00:00",
        amount: "1.250", currency: "CNY", pricingVersion: "pb-1",
      }],
    })} />);

    // "1.250" 若被转成数字会变成 1.25——那是钱，一位都不许动。
    expect(screen.getByText(/1\.250/)).toBeTruthy();
  });

  it("合计用后端算好的那个，前端不求和", () => {
    render(<BillingPanel billing={billing({
      events: [
        { jobId: "a", tier: "deep", at: "x", amount: "0.1", currency: "CNY", pricingVersion: "pb-1" },
        { jobId: "b", tier: "deep", at: "x", amount: "0.2", currency: "CNY", pricingVersion: "pb-1" },
      ],
      reconciliation: { count: 2, total: "0.3", mixedPricing: false },
    })} />);

    // 前端自己加会得到 0.30000000000000004。
    expect(screen.getByText(/合计 0\.3$/)).toBeTruthy();
  });

  it("口径混用要说出来", () => {
    const { container } = render(<BillingPanel billing={billing({
      reconciliation: { count: 2, total: "3", mixedPricing: true },
    })} />);

    expect(container.querySelector('[data-mixed-pricing="true"]')).toBeTruthy();
    expect(screen.getByText(zh["billing.mixed_pricing"])).toBeTruthy();
  });

  it("没查过账 NEVER 说成「没有计费事件」", () => {
    const { container } = render(<BillingPanel billing={billing({ events: null })} />);

    expect(container.querySelector("[data-events-state]")?.getAttribute(
      "data-events-state")).toBe("not_checked");
    expect(screen.queryByText(zh["billing.events.none"])).toBeNull();
  });
});

describe("UI-08 · 两屏本体", () => {
  // WIRE-03：`BE-05/06` 的端点已由 `WIRE-01` 挂上，两屏改为真取数。
  // 原先这两条判的是「一个请求都不发」——那是**未装配期间**的正确行为
  // （`DEC-032`）。装配落地后它自动失效，改判「**发且只发一个**，
  // 且四种结果各显示各的」。

  it("账户屏发且只发一个请求，取数中说的是「正在查」而不是「接口未提供」", async () => {
    // 永不 resolve：把「正在查」那一态定住
    const fetchMock = vi.fn((_url: RequestInfo | URL) =>
      new Promise<Response>(() => {}));
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<AccountPage />);

    expect(screen.getByText(zh["account.title"])).toBeTruthy();
    expect(container.querySelector("[data-screen-state]")?.getAttribute(
      "data-screen-state")).toBe("loading");
    // 取数中 NEVER 借用「接口未提供」——那是另一件事。
    expect(screen.queryByText(zh["account.not_provided"])).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0]![0])).toContain("/account");
  });

  it("账户屏拿到 200 就渲染真数据；后端说没查过时 NEVER 说成「没有记录」", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      principal: { kind: "user", id: "demo-user" },
      profile: { status: "not_checked" },
      scopes: { direct: { principal: { kind: "user", id: "demo-user" },
                          role: "owner", via: "direct" }, memberships: null },
    }), { status: 200, headers: { "Content-Type": "application/json" } })));

    render(<AccountPage />);

    await waitFor(() =>
      expect(screen.getByText(zh["account.profile.not_checked"])).toBeTruthy());
    expect(screen.queryByText(zh["account.profile.no_record"])).toBeNull();
  });

  it("计费屏拿到 not_enabled 就说「未启用」并带后端给的理由", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      principal: { kind: "user", id: "demo-user" },
      billing: { status: "not_enabled", reason: "计费未配置（口径版本缺失）" },
      quota: { status: "not_checked" },
    }), { status: 200, headers: { "Content-Type": "application/json" } })));

    render(<BillingPage />);

    await waitFor(() => expect(screen.getByText(zh["billing.not_enabled"])).toBeTruthy());
    expect(screen.getByText("计费未配置（口径版本缺失）")).toBeTruthy();
    // 「未启用」是查过了的结论，与「接口未提供」始终不是一回事。
    expect(screen.queryByText(zh["billing.not_provided"])).toBeNull();
  });

  it("框架的 404（没带 code）才是「接口未提供」", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ detail: "Not Found" }), { status: 404 })));

    const { container } = render(<AccountPage />);

    await waitFor(() => expect(container.querySelector(
      "[data-screen-state]")?.getAttribute("data-screen-state")).toBe("not_provided"));
  });

  it("503 FAMILY_NOT_CONFIGURED 说的是「没有后端」，NEVER 说成「坏了」", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({
      code: "FAMILY_NOT_CONFIGURED", family: "account", message: "还没有后端",
    }), { status: 503, headers: { "Content-Type": "application/json" } })));

    const { container } = render(<AccountPage />);

    await waitFor(() => expect(container.querySelector(
      "[data-screen-state]")?.getAttribute("data-screen-state")).toBe("not_configured"));
    expect(container.querySelector("[data-family]")?.getAttribute("data-family"))
      .toBe("account");
  });

  it("两屏用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of Object.keys(zh).filter(
      (k) => k.startsWith("account.") || k.startsWith("billing."))) {
      expect(en[key]).toBeTruthy();
    }
  });
});
