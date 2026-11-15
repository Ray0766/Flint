"use client";

import { AnimeNav } from "./AnimeNav";
import type { JSX, ReactNode } from "react";
import { usePathname } from "next/navigation";

import { FROZEN, isFrozenNavHref } from "../../lib/frozen";
import { t } from "../../lib/i18n/t";

import { LocaleControls } from "./LocaleControls";
import { ThemeControl } from "./ThemeControl";
import { THEME_FIRST_PAINT_SNIPPET } from "./themeFirstPaint";

/**
 * UI-01 / S0 应用外壳：顶栏 wordmark + 导航 + 账户位。
 *
 * ## 风格来源
 *
 * `Claude design Flint 前端设计/Flint 应用 · 20 屏/Flint 批次一 · 外壳与入口.dc.html`
 * 的 `data-screen-label="S0 应用外壳"` 一节：`--surface` 底 + `--tex-paper` 纸纹 +
 * `--rule` 底边线；wordmark 用 display 字体排「Flint 燧石」**无 logo**（蓝本原话），
 * 右侧是账户位。当前项 用 `--sulfur` 下划线标出（蓝本里那条 2px 的黄条）。
 *
 * ## 三处 NEVER 照搬蓝本
 *
 * 1. **账户位里的 `X-User-Id: self` 不上产品面**。蓝本把它印在顶栏上，
 *    而 FB-10 的尺子把 `X-User-Id` 逐字列进「A 类脚手架」命中组——
 *    它是开发要看的东西。这里换成诚实态：账户 + 「接口未提供」标
 *    （蓝本自己也标着「账户端点未建」，说的是同一件事）。
 * 2. **大类筛选条不做**。蓝本 S0 带一条 `GET /categories` 的筛选条，
 *    而本仓现在没有广场屏可筛——筛不到东西的筛选条就是 A 类脚手架。
 *    它跟着广场屏一起来。
 * 3. **wordmark 不是链接**。蓝本的 wordmark 点回首页，而本仓 `/` 路由不存在
 *    （实测 404）。点了掉进 404 的入口比没有入口更坏。
 *
 * ## 导航里只有真实存在的无参路由
 *
 * `web/app/` 现有三个屏，其中两个要 id（`/jobs/[id]`、`/deliverables/[id]`），
 * 没有 id 时链不过去。所以导航只列 `/demo` 一条，**NEVER 编造一排链接**
 * 来把顶栏填满——填上去的入口点不开，那是把「还没做」伪装成「做完了」。
 *
 * ## NAV-04：顶栏只有两项，而盘上有六个无参屏
 *
 * 上面那条纪律是**「不编造点不开的入口」**，不是「少给入口」。
 * 而实际发生的是后者：`/account` `/favorites` `/design` `/settings/locale`
 * 四屏建好之后，谁也没回来加过入口——它们只能手敲 URL。
 * 「入口点不开」与「屏没有入口」是两种毛病，前一种这里一直守着，
 * **后一种这一批才被量出来**（`NAV-01` 的可达性尺子）。
 *
 * 判据 `test_shell_nav.py` 因此判**双向**：顶栏里的每一项都要点得开，
 * 且**每一个无参屏都要在顶栏里有位置**——除非写明理由（`/demo`，见下）。
 *
 * ## `/demo` 留在顶栏，理由写在这里
 *
 * 它是演示串屏、不是产品屏（屏对照表 §四 已登记它「蓝本与 v2 屏总表都没有」）。
 * 仍然留着，因为**它今天是唯一能看到整条链路怎么走的地方**：
 * 主链路的中间几屏（工作台、主题、项目）还是孤岛，`NAV-05` 之前
 * 只有这个串屏能把一次完整的走法演给人看。
 *
 * 撤它的条件写在这里，免得下一个人再判一次：**`NAV-05` 把主链路真正走通、
 * 且那条路上的每一屏都从产品入口点得到之后，`/demo` 就该从顶栏撤下**
 * （屏可以留着，撤的是常驻入口）。到那时它就成了一个与产品面并列的第二条路，
 * 而两条路会各自漂移。
 *
 * ## 账户位从「一句写死的未提供」改成真入口
 *
 * 改前：顶栏上挂一个无条件的 `NotProvided`。`WIRE-01` 把 `GET /account` 挂上之后
 * **那句话就成了假的**——端点在，账户屏真的在取数（四态各自显示）。
 * 顶栏没有任何办法知道那四态里是哪一态，写死其中一态就是说谎。
 * 所以这里改成一个真入口，**状态归屏说**。
 *
 * ## SHELL-01 / `DEC-046`：右上角多了地区与语言两个下拉
 *
 * owner 2026-08-09 原话：「地区和语言做到页面右上角，直接下拉选择」。
 * 改前这个位置是一个空的 `app-shell__spacer`（把导航推到左边的占位）。
 *
 * **是新增不是搬家**：`LocaleSettings` 只在 `/settings/locale` 那一屏，
 * 而 `RegionSwitch` 在广场页上另有一个实例；**外壳右上角两者都没有**——
 * 那才是 owner 说的那件事。三处共用同一个值（都读写 `/settings/locale`）。
 *
 * 控件本体在 `LocaleControls`，**本文件只负责把它放在右上角**：
 * 顶栏不该知道两条轴怎么写回去，那是那个组件的事。
 */

/**
 * 顶栏常驻入口。**无参可达的屏 = 这份清单**（`/demo` 例外，理由见文件头）。
 *
 * 加一条新的无参屏时同时加在这里，NEVER 让导航去猜；
 * 也 NEVER 因为后端还没数据就把入口藏起来——藏起来的话，
 * 用户不知道有这个能力，而屏自己有的是办法如实说「还没有」。
 */
export const NAV_ITEMS: ReadonlyArray<{ href: string; key: string }> = [
  // UI-02 加了广场：它是主链路第一屏，也是本仓第二个无参路由。
  { href: "/plaza", key: "shell.nav.plaza" },
  // `WB-01` / `DEC-059`：计划书主工作台。`WB-07` 把它排到 `/design` **之前**——
  // 裁决那句「新增主工作台，不替换现有『AI 设计工作台』，后者改名退居次要」，
  // 「退居次要」的可见形式就是次序，「不替换」的可见形式就是它**仍在这张表里**。
  { href: "/workbench", key: "shell.nav.workbench" },
  { href: "/favorites", key: "shell.nav.favorites" },
  // 改名（`WB-07`）：文案换成「模板工具」，**href 与那一屏一个字没动**。
  // NEVER 把它摘掉——摘掉就是把一个做完的能力藏起来，
  // 而藏起来与删掉在屏上长得一模一样（`DEC-059` 逐字写着这一条）。
  { href: "/design", key: "shell.nav.design" },
  { href: "/settings/locale", key: "shell.nav.locale" },
  { href: "/account", key: "shell.nav.account" },
  { href: "/demo", key: "shell.nav.demo" },
];

/**
 * What the shell actually shows: `NAV_ITEMS` minus the entries `DEC-066` froze
 * (`NARROW-05`, switches in `lib/frozen.ts`). The table above keeps every route,
 * so unfreezing one is a switch flip, not a re-add.
 */
export const SHELL_NAV_ITEMS = NAV_ITEMS.filter((item) => !isFrozenNavHref(item.href));

/**
 * <768 时替代文字的图标（蓝本 `iconDisplay` 那一路）。
 *
 * 尺寸与描边照蓝本：18×18 · `stroke-width: 2.5` · `currentColor`。
 * 形状按各屏自己的意思挑，**NEVER 照抄蓝本那四个英文标签的图标**——
 * 蓝本的 Home/Convert/Pricing/About 与本仓六屏不是一回事。
 *
 * `aria-hidden` 由 `AnimeNav` 那一层给：文字标签仍在 DOM 里（只是被 CSS 藏了），
 * 读屏软件读到的仍是中文屏名，**可达性一条没退**。
 */
const NAV_ICONS: Record<string, JSX.Element> = {
  // 广场：网格
  "/plaza": (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
    </svg>
  ),
  // 收藏：书签
  "/favorites": (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="m19 21-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
    </svg>
  ),
  // 设计台：画笔
  "/design": (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 19l7-7 3 3-7 7-3-3z" /><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18z" />
      <path d="M2 2l7.586 7.586" /><circle cx="11" cy="11" r="2" />
    </svg>
  ),
  // 语言与地区：地球
  "/settings/locale": (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M2 12h20" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
  // 账户：人
  "/account": (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
    </svg>
  ),
  // 计划书工作台：三栏（左卡片 / 中对话 / 右预览）——屏本身的形状
  "/workbench": (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" /><path d="M15 4v16" />
    </svg>
  ),
  // 演示串屏：播放
  "/demo": (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polygon points="10 8 16 12 10 16 10 8" />
    </svg>
  ),
};

export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      {/* SHELL-02 acceptance⑥：**首帧 NEVER 闪白再变暗**。
          这一段同步执行——浏览器解析到它的那一刻就把 `data-theme` 放上去了，
          **比 React 水合早，也比第一帧早**。
          它读的是 cookie 提示（不是真相，见 `themeFirstPaint.ts` 文件头）；
          「跟随系统」那一态本来就不闪（`DARK-01` 的 CSS 通道在第一帧就生效）。 */}
      <script
        data-testid="theme-first-paint"
        dangerouslySetInnerHTML={{ __html: THEME_FIRST_PAINT_SNIPPET }}
      />
      {/* `NAV-ANIME-01`：药丸浮动条。
          **既有导航语义一条不改**——6 个入口、`href`、`aria-current` 全部照旧
          （`ENTRY-05` 的判据一条都不许倒）。换的只有长相。

          品牌字与三个控件都进条里：owner 要的是「做成一个横栏」，
          而判据量的是 6 个导航项 + 3 个控件的 `offsetTop` 相等。 */}
      <header className="app-shell__bar" data-shell="s0">
        <div className="app-shell__inner">
          <AnimeNav
            items={SHELL_NAV_ITEMS.map((item) => ({
              href: item.href,
              key: item.href,
              label: t(item.key),
              icon: NAV_ICONS[item.href] ?? null,
            }))}
            activeKey={SHELL_NAV_ITEMS.some((i) => i.href === pathname) ? pathname : null}
            brand={
              <span className="app-shell__wordmark">{t("app.name.wordmark")}</span>
            }
          >
            {/* SHELL-01：`.app-shell__spacer` 是 `flex: 1`——**它就是把后面的东西
                推到右边的那个机制**。第一版把它删了，实测控件停在 x=146 而顶栏
                右边缘在 390，「右上角」只做到了「在顶栏里」。
                药丸条里同理：没有它，三个控件会紧贴最后一个导航项。 */}
            <span className="app-shell__spacer" />
            {/* NARROW-05: region and language dropdowns are a `DEC-066` frozen entry. */}
            {FROZEN.regionsAndLanguages ? null : <LocaleControls />}
            {/* SHELL-02：三态切换排在地区/语言之后。 */}
            <ThemeControl />
          </AnimeNav>
        </div>
      </header>
      <main className="app-shell__body">{children}</main>
    </div>
  );
}
