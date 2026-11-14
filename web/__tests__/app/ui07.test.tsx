/**
 * UI-07 · 语言与地区设置屏（v2 屏 2.13）。
 *
 * 三条最要紧的判据：
 *
 * 1. **两轴正交**——`onChange` 一次只交出一根轴；
 * 2. **NEVER 用浏览器语言猜地区**——没存过就显示声明过的默认值并标「未保存」；
 * 3. **保存失败 NEVER 回滚**——保留用户选择并显示错误。
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LocaleSettings, LANGS } from
  "../../components/locale-settings/LocaleSettings";
import LocaleSettingsPage from "../../app/settings/locale/page";
import zh from "../../messages/zh.json";

const draft = { lang: "zh", region: "CN" };

// LOC-01：地区清单由端点下发，前端不再持有副本。所以整屏用例**故意只服三项**，
// 且顺序不是字母序——屏上渲染出来必须正好是这三项。
// 组件若还留着一份自带的九区，「清单只有一份」那条会当场变红。
const SERVED_REGIONS = ["JP", "CN", "FR"];

const selects = (c: HTMLElement) => ({
  lang: c.querySelector<HTMLSelectElement>('[data-locale-axis="lang"]'),
  region: c.querySelector<HTMLSelectElement>('[data-locale-axis="region"]'),
});

// WIRE-03：本屏改为真取数，所以整屏用例要先把 `GET /settings/locale` 的回包给上，
// 等它落地再断言。**NEVER 直接断言首帧**——首帧是「正在查」，
// 那一态与「查过了」说的是两件事。
const LOCALE_BODY = {
  lang: "zh",
  region: "CN",
  options: { lang: ["en", "zh"], region: SERVED_REGIONS },
};

// FIX-04：**等的是值，不是元素存在**。
//
// 改前这里 `waitFor(selects 存在)` 就返回了。但屏上到位要两拍：
// 第一拍数据 ready、下拉渲染出来（此时草稿仍是声明的默认值 zh/CN），
// 第二拍对齐草稿的 effect 冲刷、值才变成后端给的那个。
//
// `waitFor` 在第一拍就满足了 → 断言值的那条用例**在两拍之间抢跑**。
// 默认值那条用例看不出来（zh/CN 恰好就是期望值），
// 非默认值那条 5 次里红 1 次——`docs/blocked/UI07-LOCALE-TEST-IS-FLAKY.md`
// 记的正是它。实测把这一等法放进 40 次循环，**第 29 次抓到 `zh`**。
//
// 单子里怀疑的 `vi.stubGlobal` 跨用例不还原**不是本次的因**（那是另一处真实隐患，
// 由 `unstubGlobals` 一并去掉）——**怀疑不是证据**，所以先证后修。
async function renderLoadedPage(body: unknown = LOCALE_BODY) {
  const expected = body as { lang?: string; region?: string };
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), {
    status: 200, headers: { "Content-Type": "application/json" },
  })));
  const view = render(<LocaleSettingsPage />);
  await waitFor(() => {
    const lang = selects(view.container).lang;
    expect(lang).toBeTruthy();
    // 两拍都到位了才算加载完：值等于后端给的那个。
    expect(lang!.value).toBe(expected.lang ?? "zh");
    expect(selects(view.container).region!.value).toBe(expected.region ?? "CN");
  });
  return view;
}

describe("UI-07 · 两轴正交（A3）", () => {
  it("改语言时只交出 lang 这一根轴", () => {
    const onChange = vi.fn();
    const { container } = render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={draft} status="idle" onChange={onChange} />);

    fireEvent.change(selects(container).lang!, { target: { value: "en" } });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("lang", "en");
  });

  it("改地区时只交出 region 这一根轴", () => {
    const onChange = vi.fn();
    const { container } = render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={draft} status="idle" onChange={onChange} />);

    fireEvent.change(selects(container).region!, { target: { value: "JP" } });

    expect(onChange).toHaveBeenCalledWith("region", "JP");
  });

  it("屏上改一根轴，另一根原样不动", async () => {
    const { container } = await renderLoadedPage();

    fireEvent.change(selects(container).region!, { target: { value: "FR" } });

    expect(selects(container).region!.value).toBe("FR");
    expect(selects(container).lang!.value).toBe("zh");
  });

  it("每一种组合都走得通（2 语言 × 端点给的每个地区）", async () => {
    // 改前这里写死「2 × 9」并遍历前端自带的 REGIONS——那是照着抄件在验。
    // 现在遍历的是**端点这一趟真给了什么**：地区加到第十个那天，
    // 不必回来改这个数字，它自己就跟着走了。
    const { container } = await renderLoadedPage();

    for (const lang of LANGS) {
      for (const region of SERVED_REGIONS) {
        fireEvent.change(selects(container).lang!, { target: { value: lang } });
        fireEvent.change(selects(container).region!, { target: { value: region } });
        expect(selects(container).lang!.value).toBe(lang);
        expect(selects(container).region!.value).toBe(region);
      }
    }
  });
});

describe("UI-07 · 没存过就说没存过，NEVER 猜", () => {
  it("`saved === null` → 标「未保存」", () => {
    const { container } = render(
      <LocaleSettings saved={null} regions={SERVED_REGIONS} draft={draft} status="idle" />);

    expect(container.querySelector("[data-locale-unsaved]")).toBeTruthy();
    expect(screen.getByText(zh["locale.unsaved"])).toBeTruthy();
    expect(container.getAttribute("data-locale-saved")).toBe(null);
    expect(container.querySelector("[data-locale-saved]")?.getAttribute(
      "data-locale-saved")).toBe("none");
  });

  it("存过就不再标「未保存」", () => {
    const { container } = render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={draft} status="idle" />);

    expect(container.querySelector("[data-locale-unsaved]")).toBeNull();
    expect(container.querySelector("[data-locale-saved]")?.getAttribute(
      "data-locale-saved")).toBe("stored");
  });

  it("后端给的就是屏上显示的，前端 NEVER 自己猜一个默认值", async () => {
    // 后端在没存过偏好时回的是**声明过的默认值**（zh / CN），
    // 「查过了、你没改过设置」与「默认值就是当前值」是同一件事。
    const { container } = await renderLoadedPage();

    expect(selects(container).lang!.value).toBe("zh");
    expect(selects(container).region!.value).toBe("CN");
  });

  it("后端给的不是默认值时，屏上跟着变（证明不是写死的 zh/CN）", async () => {
    const { container } = await renderLoadedPage({
      ...LOCALE_BODY, lang: "en", region: "JP",
    });

    expect(selects(container).lang!.value).toBe("en");
    expect(selects(container).region!.value).toBe("JP");
  });
});

describe("UI-07 · 保存中与保存失败", () => {
  it("保存中两个下拉都置灰", () => {
    const { container } = render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={draft} status="saving" />);

    expect(selects(container).lang!.disabled).toBe(true);
    expect(selects(container).region!.disabled).toBe(true);
    expect(container.querySelector("button")?.disabled).toBe(true);
  });

  it("保存失败**保留用户选择**，NEVER 回滚成旧值", () => {
    const chosen = { lang: "en", region: "JP" };
    const { container } = render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={chosen} status="error" />);

    // 屏上仍是用户选的那两个值，不是 saved 里的 zh / CN。
    expect(selects(container).lang!.value).toBe("en");
    expect(selects(container).region!.value).toBe("JP");
  });

  it("保存失败要说出来（回滚且不报错 = 假装成功）", () => {
    const { container } = render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={draft} status="error" />);

    expect(container.querySelector("[data-locale-error]")).toBeTruthy();
    expect(screen.getByText(zh["locale.save_failed"])).toBeTruthy();
  });

  it("后端给了错误原文就显示原文", () => {
    render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={draft} status="error" error="账本已前进" />);

    expect(screen.getByText("账本已前进")).toBeTruthy();
  });

  it("idle 时不显示错误", () => {
    const { container } = render(
      <LocaleSettings saved={draft} regions={SERVED_REGIONS} draft={draft} status="idle" />);

    expect(container.querySelector("[data-locale-error]")).toBeNull();
  });
});

describe("UI-07 · 清单只有一份", () => {
  it("地区下拉的选项就是端点回的那一份，前端不自带", async () => {
    // **喂三项就只渲染三项**：前端若还留着一份九区副本，这条会红。
    // 「九区完整、无 EU」那句断言搬去了源头
    // （tests/v041/test_regions_from_backend.py 在真栈上判 options.region）——
    // 从前它判的是一份抄件。
    const { container } = await renderLoadedPage();
    const options = [...container.querySelectorAll(
      '[data-locale-axis="region"] option')].map((o) => o.getAttribute("value"));

    expect(options).toEqual(SERVED_REGIONS);
  });

  it("端点没给清单 → 说「接口未提供」，NEVER 空下拉、NEVER 退回自带副本", () => {
    const { container } = render(
      <LocaleSettings saved={null} regions={null} draft={draft} status="idle" />);

    expect(container.querySelector('select[data-locale-axis="region"]')).toBeNull();
    expect(container.querySelector('[data-locale-axis="region"]'))
      .toHaveAttribute("data-screen-state", "not_provided");
  });

  it("语言下拉恰好两项", () => {
    const { container } = render(
      <LocaleSettings saved={null} regions={SERVED_REGIONS} draft={draft} status="idle" />);
    const options = [...container.querySelectorAll(
      '[data-locale-axis="lang"] option')].map((o) => o.getAttribute("value"));

    expect(options).toEqual([...LANGS]);
  });
});

describe("UI-07 · 屏本体", () => {
  it("发且只发一个请求，取数中说的是「正在查」", async () => {
    // WIRE-03：原先判的是「一个请求都不发」——那是**未装配期间**的正确行为
    // （`DEC-032`）。装配落地后它自动失效。
    const fetchMock = vi.fn((_url: RequestInfo | URL) =>
      new Promise<Response>(() => {}));
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<LocaleSettingsPage />);

    expect(screen.getByText(zh["locale.title"])).toBeTruthy();
    expect(container.querySelector("[data-screen-state]")?.getAttribute(
      "data-screen-state")).toBe("loading");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(String(fetchMock.mock.calls[0]![0])).toContain("/settings/locale");
  });

  it("本屏用到的 key 在 zh 与 en 里都有", async () => {
    const en = (await import("../../messages/en.json")).default as Record<string, string>;
    for (const key of [
      "locale.title", "locale.meta", "locale.lang", "locale.lang.zh",
      "locale.lang.en", "locale.region", "locale.save", "locale.saving",
      "locale.save_failed", "locale.unsaved",
    ]) {
      expect(zh[key as keyof typeof zh]).toBeTruthy();
      expect(en[key]).toBeTruthy();
    }
  });
});
