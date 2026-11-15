/**
 * UI-01：S0 应用外壳 —— 按蓝本重做，但**三处不照搬**。
 *
 * 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/Flint 批次一 · 外壳与入口.dc.html`
 * 的 `data-screen-label="S0 应用外壳"` 一节。
 *
 * ## 这一组判据守的是「不照搬」那三处
 *
 * 蓝本是**原型**，它的顶栏上印着 `X-User-Id: self`。FB-10 的尺子把 `X-User-Id`
 * 逐字列进「A 类脚手架」命中组——开发要看的东西跑到了产品面。
 * 照搬会让 FB-10 那把已 verified 的尺子当场变红，而更重要的是：
 * 用户看着一行 HTTP 头，会以为这产品还没做完。
 *
 * 另两处：大类筛选条（筛不到东西的筛选条 = 脚手架）、wordmark 点回首页
 * （`/` 路由不存在，实测 404——点了掉进 404 的入口比没有入口更坏）。
 *
 * ## 为什么判 NAV_ITEMS 而不只判渲染结果
 *
 * 导航里 NEVER 出现点不开的链接。判据既查渲染出来的每个 href 都在
 * `web/app/` 下有对应的无参路由，也查 `NAV_ITEMS` 本身——
 * 只判渲染结果的话，把 NAV_ITEMS 清空会得到一个「零个坏链接」的绿。
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell, NAV_ITEMS, SHELL_NAV_ITEMS } from "../../components/shell/AppShell";
import { NotProvided } from "../../components/shell/NotProvided";
import { Screen } from "../../components/shell/Screen";
import zh from "../../messages/zh.json";

const messages = zh as Record<string, string>;

let pathname = "/demo";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

function renderShell(at = "/demo") {
  pathname = at;
  return render(
    <AppShell>
      <p>内容</p>
    </AppShell>,
  );
}

describe("S0 外壳", () => {
  it("顶栏排着 wordmark，用的是词条里的那串字", () => {
    renderShell();

    expect(screen.getByText(messages["app.name.wordmark"])).toBeInTheDocument();
  });

  it("外壳把每一屏包起来——内容在外壳里面，不是并排", () => {
    const { container } = renderShell();
    const shell = container.querySelector(".app-shell");

    expect(shell).not.toBeNull();
    expect(shell?.querySelector(".app-shell__body")?.textContent).toContain("内容");
  });

  it("导航里只有真实存在的无参路由，一个都不多", () => {
    renderShell();
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>(".app-shell__nav-link"));

    // NARROW-05: the shell renders `SHELL_NAV_ITEMS` (NAV_ITEMS minus the DEC-066
    // frozen entries). Every rendered link is still a real route from the table.
    expect(links.length).toBe(SHELL_NAV_ITEMS.length);
    expect(links.map((a) => a.getAttribute("href"))).toEqual(SHELL_NAV_ITEMS.map((i) => i.href));
    expect(SHELL_NAV_ITEMS.every((i) => NAV_ITEMS.includes(i))).toBe(true);
    expect(SHELL_NAV_ITEMS.length).toBeGreaterThan(0);
  });

  it("当前那一项标出来了，别的没有", () => {
    renderShell("/demo");
    const current = document.querySelectorAll('[aria-current="page"]');

    expect(current.length).toBe(1);
    expect(current[0].getAttribute("href")).toBe("/demo");
  });

  it("不在导航里的屏上，一项都不标当前", () => {
    renderShell("/jobs/job-1");

    expect(document.querySelectorAll('[aria-current="page"]').length).toBe(0);
  });

  // NAV-04：这条判据**改过一次**，改因记在这里。
  //
  // 改前它判「账户位说的是『接口未提供』」。`WIRE-01` 把 `GET /account` 挂上之后，
  // 顶栏那句写死的「未提供」就成了假话——端点在，账户屏真的在取数（四态各自显示），
  // 而顶栏没有任何办法知道那四态里是哪一态。**它红的是自己的前提过期，
  // 不是事情坏了。**
  //
  // 不变的那一半原样留着：顶栏 NEVER 印 `X-User-Id`（FB-10 的 A 类）。
  // 变的那一半改成实况：账户是导航里的一项，状态归屏说。
  it("账户是导航里的一项，而顶栏 NEVER 印 X-User-Id", () => {
    const { container } = renderShell();
    const hrefs = Array.from(
      document.querySelectorAll<HTMLAnchorElement>(".app-shell__nav-link"),
    ).map((a) => a.getAttribute("href"));

    expect(hrefs).toContain("/account");
    expect(container.textContent).toContain(messages["shell.nav.account"]);
    // 顶栏自己 NEVER 替账户屏说状态：写死四态里的任何一态都是说谎。
    expect(container.querySelector("[data-not-provided]")).toBeNull();
    expect(container.textContent).not.toContain("X-User-Id");
    expect(container.textContent).not.toContain("self");
  });

  it("顶栏上没有大类筛选条——本仓还没有可筛的屏", () => {
    const { container } = renderShell();

    expect(container.querySelector("[data-category-filter]")).toBeNull();
    expect(container.textContent).not.toContain("/categories");
  });

  it("wordmark 不是链接：/ 路由不存在，点了会掉进 404", () => {
    const { container } = renderShell();
    const wordmark = container.querySelector(".app-shell__wordmark");

    expect(wordmark?.tagName).toBe("SPAN");
    expect(wordmark?.closest("a")).toBeNull();
    expect(wordmark?.closest("button")).toBeNull();
  });
});

describe("S1 通用件", () => {
  it("「接口未提供」标带机器可查的属性，文案取自词条", () => {
    render(<NotProvided />);
    const mark = document.querySelector("[data-not-provided]");

    expect(mark).not.toBeNull();
    expect(mark?.textContent).toContain(messages["shell.not_provided"]);
  });

  it("记号是内联几何形，NEVER 用 emoji 或图标字体", () => {
    const { container } = render(<NotProvided />);
    const mark = container.querySelector(".not-provided__mark");

    expect(mark).not.toBeNull();
    expect(mark?.textContent).toBe("");
    // 蓝本 Assets 一节原话：无位图/图标字体/emoji。
    expect(/\p{Extended_Pictographic}/u.test(container.textContent ?? "")).toBe(false);
  });

  it("屏头给出标题与 mono 副标", () => {
    const { container } = render(
      <Screen title="分析进度" meta="实时事件流">
        <p>正文</p>
      </Screen>,
    );

    expect(container.querySelector(".screen__title")?.textContent).toBe("分析进度");
    expect(container.querySelector(".screen__meta")?.textContent).toBe("实时事件流");
    expect(container.querySelector(".screen__body")?.textContent).toBe("正文");
  });

  it("没有副标时不留一个空行——空标签在页面上是一段说不清的留白", () => {
    const { container } = render(
      <Screen title="报告">
        <p>正文</p>
      </Screen>,
    );

    expect(container.querySelector(".screen__meta")).toBeNull();
  });
});
