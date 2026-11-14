"use client";

// NAV-ANIME-01：顶部居中的药丸浮动条 + 跟随发光块。
//
// ## 风格来源只有一个
//
// `前端设计/Anime navbar live demo/Anime Navbar.dc.html`（owner 2026-08-11 指定）。
// **照它做，NEVER 自创一版**。蓝本的核心机制是 `measure()`：
// 逐个量 `a[data-tab]` 的 `offsetLeft` / `offsetWidth`，
// 发光块按当前项那一对数去定位——**不是靠 CSS 猜，是量出来的**。
//
// ## 三处蓝本没写、而本仓必须补
//
// | 补的 | 为什么 |
// |---|---|
// | 中文字体加载后**重测** | 蓝本也有 `document.fonts.ready.then(measure)`，但英文界面上看不出差别；中文字体（Smiley Sans / Noto Sans SC）加载慢，不重测发光块会停在旧位置 |
// | `prefers-reduced-motion` 时全停 | 蓝本没有这一条。系统说了不要动效就 NEVER 动 |
// | 亮/暗两套配色 | 蓝本只有暗底。亮底用半透明白 + 深色字 + 更轻投影（owner 2026-08-10 裁决） |
//
// **NEVER 引蓝本那条外链 Google Fonts（Manrope）**：CI 不联网，且那是第三方请求。
// 字体走本仓既有的 `--font-body` / `--font-display` 档，字号与字重照蓝本。
//
// ## 既有导航语义一条不改
//
// 6 个入口、`href`、`aria-current` 全部照旧（`ENTRY-05` 的判据一条都不许倒）。
// 这里换的只有**长相**。

import type { JSX, ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";

import { t as translate } from "../../lib/i18n/t";

/** 蓝本 `isMobile` 那一路的断点：<768 收成图标。 */
const MOBILE_MAX = 768;

/** 发光块与吉祥物都按这一对数定位——**它们量的是同一个矩形**。 */
export type TabRect = { left: number; width: number };

export type AnimeNavProps = {
  /** 每一项：`key` 用作 `data-tab`，`href` 与 `label` 照既有导航。 */
  items: ReadonlyArray<{ href: string; key: string; label: string; icon: ReactNode }>;
  /** 当前项的 `key`。没有匹配项时发光块不显示（`opacity: 0`），NEVER 乱指一个。 */
  activeKey: string | null;
  /** 药丸条右侧的控件（地区 / 语言 / 主题）——它们与导航项在**同一行**。 */
  children?: ReactNode;
  /** 条最左边的品牌字。放左边是因为读者从左往右找「这是哪个产品」。 */
  brand?: ReactNode;
  /** 量到当前项矩形时回调——`NAV-ANIME-02` 的吉祥物用它跟过去。 */
  onActiveRect?: (rect: TabRect | null) => void;
};

export function AnimeNav({
  items,
  activeKey,
  children,
  brand,
  onActiveRect,
}: AnimeNavProps): JSX.Element {
  const navRef = useRef<HTMLElement | null>(null);
  const [rects, setRects] = useState<Record<string, TabRect>>({});
  const [isMobile, setIsMobile] = useState(false);
  /** 鼠标停在哪一项上。吉祥物的四种交互动画全看它（蓝本 `hoveredTab`）。 */
  const [hovered, setHovered] = useState<string | null>(null);

  const measure = useCallback(() => {
    const nav = navRef.current;
    if (!nav) return;
    const next: Record<string, TabRect> = {};
    nav.querySelectorAll<HTMLElement>("a[data-tab]").forEach((el) => {
      const tab = el.dataset.tab;
      if (tab) next[tab] = { left: el.offsetLeft, width: el.offsetWidth };
    });
    setRects((prev) =>
      JSON.stringify(prev) === JSON.stringify(next) ? prev : next);
  }, []);

  useEffect(() => {
    const onResize = (): void => {
      setIsMobile(window.innerWidth < MOBILE_MAX);
      measure();
    };
    onResize();
    window.addEventListener("resize", onResize);

    // **中文字体加载后重测**（本仓补的那一条，`NAV-ANIME-01` acceptance④）。
    //
    // 字体换了，每个 tab 的宽度就变了；不重测的话发光块停在**用后备字体量出来的**
    // 那个位置上，而那在中文界面上是必现的错位——英文蓝本上看不出来。
    if (document.fonts?.ready) void document.fonts.ready.then(() => measure());

    // 观察尺寸变化：字体之外还有别的东西会改 tab 宽度（语言切换、缩放）。
    // `ResizeObserver` 比轮询准，也比「猜一个延时再测一次」诚实。
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(() => measure());
    if (observer && navRef.current) observer.observe(navRef.current);

    return () => {
      window.removeEventListener("resize", onResize);
      observer?.disconnect();
    };
  }, [measure]);

  // 项目变了（语言切换换了文案）也要重测。
  useEffect(() => {
    measure();
  }, [items, measure]);

  const active = activeKey ? rects[activeKey] ?? null : null;

  useEffect(() => {
    onActiveRect?.(active);
  }, [active, onActiveRect]);

  return (
    <nav
      ref={navRef}
      className="anime-nav"
      data-testid="anime-nav"
      data-mobile={isMobile ? "true" : "false"}
      // 走既有词条（改前 `AppShell` 用的就是它）。
      // 我换组件时把它写死成了中文——英文界面下会出现一句中文标签，
      // 而读屏软件读的正是它。
      aria-label={translate("shell.nav.label")}
    >
      {/* 跟随发光块。五层模糊照蓝本（inset 0 / -4 / -8 / -12 + shine 扫光）。
          `left` / `width` 直接用量到的数——**判据会拿它与 offsetLeft 逐一比对**。 */}
      <span
        className="anime-nav__glow"
        data-testid="anime-nav-glow"
        aria-hidden="true"
        style={{
          left: active ? `${active.left}px` : "0px",
          width: active ? `${active.width}px` : "0px",
          opacity: active ? 1 : 0,
        }}
      >
        <span className="anime-nav__glow-layer anime-nav__glow-layer--1" />
        <span className="anime-nav__glow-layer anime-nav__glow-layer--2" />
        <span className="anime-nav__glow-layer anime-nav__glow-layer--3" />
        <span className="anime-nav__glow-layer anime-nav__glow-layer--4" />
        <span className="anime-nav__glow-shine-clip">
          <span className="anime-nav__glow-shine" />
        </span>
      </span>

      {brand ? <span className="anime-nav__brand">{brand}</span> : null}

      {items.map((item) => {
        const isActive = item.key === activeKey;
        return (
          <a
            key={item.href}
            href={item.href}
            data-tab={item.key}
            // 两个类名一起挂：`anime-nav__tab` 是新长相，
            // **`app-shell__nav-link` 是既有判据认的那个钩子**。
            // 换掉它等于把「6 个入口一个都不多」那条判据变成空转——
            // 它会因为找不到元素而红，而红的原因与导航语义无关。
            // 本卡换的是长相，判据认的那个名字**一个字都不该动**。
            className="anime-nav__tab app-shell__nav-link"
            data-active={isActive ? "true" : "false"}
            aria-current={isActive ? "page" : undefined}
            onMouseEnter={() => setHovered(item.key)}
            onMouseLeave={() => setHovered(null)}
          >
            {/* 文字与图标**两个都在 DOM 里**，靠 CSS 断点切显示——
                蓝本 `labelDisplay` / `iconDisplay` 那一路。
                只渲染其中一个的话，切换视口要等一次 React 重渲，
                而中间那一帧屏上什么都没有。 */}
            <span className="anime-nav__label">{item.label}</span>
            <span className="anime-nav__icon" aria-hidden="true">
              {item.icon}
            </span>
          </a>
        );
      })}

      {children ? <span className="anime-nav__controls">{children}</span> : null}

      {/* 吉祥物照蓝本第 56~71 行做全（owner 2026-08-10：**要，照蓝本做全**）。
          `left = 当前项中心 - 24`（蓝本 `mascotLeft` 逐字）——
          它与发光块**量的是同一个矩形**，所以两者恒对齐。

          `pointer-events: none` 是蓝本原话：它浮在导航项上方，
          能点的必须仍然是导航项。判据会真去点它下面那一项。 */}
      <span
        className="anime-nav__mascot"
        data-testid="anime-nav-mascot"
        data-hovered={hovered ? "true" : "false"}
        aria-hidden="true"
        style={{
          left: active ? `${active.left + active.width / 2 - 24}px` : "0px",
          opacity: active ? 1 : 0,
        }}
      >
        <span className="anime-nav__mascot-head">
          <span className="anime-nav__mascot-eye anime-nav__mascot-eye--l" />
          <span className="anime-nav__mascot-eye anime-nav__mascot-eye--r" />
          <span className="anime-nav__mascot-blush anime-nav__mascot-blush--l" />
          <span className="anime-nav__mascot-blush anime-nav__mascot-blush--r" />
          <span className="anime-nav__mascot-mouth" />
          {/* 星星只在 hover 时冒（蓝本 `sc-if hovered`）。
              恒渲染再靠 opacity 藏的话，`sparklePop` 那个入场动画只会播一次。 */}
          {hovered ? (
            <>
              <span className="anime-nav__mascot-sparkle anime-nav__mascot-sparkle--a">
                ✨
              </span>
              <span className="anime-nav__mascot-sparkle anime-nav__mascot-sparkle--b">
                ✨
              </span>
            </>
          ) : null}
        </span>
        <span className="anime-nav__mascot-tail">
          <span className="anime-nav__mascot-tail-tip" />
        </span>
      </span>
    </nav>
  );
}
