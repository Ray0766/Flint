"use client";

// DS-01：把 `_ds` 的 **JS 那一半**接进应用。
//
// ## 改前是什么样
//
// `FB-01` 接的是 CSS 那一半（`layout.tsx` 里那条 `<link>`），于是 token 生效了、
// 而 `_ds_bundle.js` 里的 15 个组件**一个都没进过运行时**。`StickerTag` 与
// `StatusMark` 就在那个 bundle 里，全仓 grep 两个名字零命中——
// 「素材没用上」这句话的机械根因就是这一条。
//
// ## 为什么是运行时注入，不是 import
//
// bundle 是**供应商资产**（终检 C6 的口径），走 `public/` 按 URL 取，
// NEVER 搬进构建面。它也不是 ES module——里面是浏览器全局写法：
// 一个 IIFE，读 `React` 这个**全局名字**，把组件挂到 `window.<namespace>` 上。
// 所以顺序是死的：
//
//   1. 先把应用自己的 React 实例喂到 `window.React`；
//   2. 再插 `<script>`。
//
// 反过来的话，bundle 里每个组件都会在自己的 `try/catch` 里抛「React is not defined」，
// 被吞进 `__errors`，**页面不报错、组件不存在**——判据要认得出这一形状，
// 所以 `__errors` 也一并暴露给取证（`tests/v041/test_ds_bundle_wired.py`）。
//
// 喂的必须是**应用这一份 React 实例**：另喂一份的话，bundle 产出的元素会带着
// 另一个 dispatcher，hook 一调就崩。
//
// ## 只在客户端跑
//
// bundle 认 `window`，服务端没有。所以组件在服务端与**首次客户端渲染**都交出
// 「还没到」那一态（`data-ds-pending`），等 effect 里加载完再换成真组件——
// 两侧首帧一致，不会有水合错位。

import * as React from "react";

/** 导出包目录名里的哈希段随导出包变。写错的路径静默 404，判据盯着它必须解析得到真文件。 */
export const DS_BUNDLE_SRC =
  "/_ds/flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724/_ds_bundle.js";

/** bundle 把自己挂在 `window[DS_NAMESPACE]` 上（`_ds_manifest.json` 的 namespace 字段）。 */
export const DS_NAMESPACE = "FlintDesignSystem_8fd95b";

/** bundle 自己吞下的加载错误：**有它就等于这个组件不存在**，取证要看得见。 */
export type DsBundleError = { path: string; error: string };

type DsScope = Record<string, unknown> & { __errors?: DsBundleError[] };

type WindowWithDs = Window & {
  React?: typeof React;
  [DS_NAMESPACE]?: DsScope;
};

/** 加载只做一次：十几个组件同时要它的话，插十几个 script 标签等于跑十几遍 IIFE。 */
let inFlight: Promise<DsScope> | null = null;

function scope(): DsScope | null {
  if (typeof window === "undefined") return null;
  return (window as WindowWithDs)[DS_NAMESPACE] ?? null;
}

export function loadDsBundle(): Promise<DsScope> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("_ds bundle runs in the browser only"));
  }
  const already = scope();
  if (already) return Promise.resolve(already);
  if (inFlight) return inFlight;

  inFlight = new Promise<DsScope>((resolve, reject) => {
    // 顺序不可倒：bundle 读的是全局 `React`。
    (window as WindowWithDs).React = React;

    const existing = document.querySelector<HTMLScriptElement>(
      `script[src="${DS_BUNDLE_SRC}"]`,
    );
    const el = existing ?? document.createElement("script");
    const done = (): void => {
      const ns = scope();
      if (ns) resolve(ns);
      // 脚本 200 了而命名空间不在 = 包换了名字。这句话说的是**接线错了**，
      // 与「网络失败」是两件事，所以两条消息不共用一句。
      else reject(new Error(`${DS_BUNDLE_SRC} loaded, but window.${DS_NAMESPACE} is absent`));
    };
    el.addEventListener("load", done);
    el.addEventListener("error", () =>
      reject(new Error(`${DS_BUNDLE_SRC} failed to load — check the hashed path first`)),
    );
    if (!existing) {
      el.src = DS_BUNDLE_SRC;
      el.async = true;
      document.head.appendChild(el);
    }
  });
  return inFlight;
}

/**
 * 全站挂一次，让 bundle **不等第一个用它的组件出现**就开始加载。
 *
 * 不挂的话，加载是懒的：一屏上没有贴纸标签就不会去取，等到有卡片的那一屏才现取，
 * 于是卡片会先秃一帧再变成设计系统的样子。它自己不画任何东西（回 `null`），
 * 所以 NEVER 影响任何一屏的布局。
 */
export function DsBundleMount(): null {
  React.useEffect(() => {
    loadDsBundle().catch((err: unknown) => {
      console.error("[_ds] bundle failed to load", err);
    });
  }, []);
  return null;
}

/**
 * 取 bundle 里的某个组件。**还没到位时回 `null`**——由调用方交出「还没到」那一态，
 * NEVER 由本模块画一个像 `_ds` 的东西顶上。
 */
export function useDsComponent<P>(name: string): React.ComponentType<P> | null {
  const [component, setComponent] = React.useState<React.ComponentType<P> | null>(null);

  React.useEffect(() => {
    let live = true;
    loadDsBundle()
      .then((ns) => {
        if (live) setComponent(() => ns[name] as React.ComponentType<P>);
      })
      // 取不到就停在「还没到」那一态。这里 NEVER 吞成静默：
      // 控制台留一行，探针的 console error 计数看得见（EYE-03 的判据之一）。
      .catch((err: unknown) => {
        console.error(`[_ds] ${name} unavailable`, err);
      });
    return () => {
      live = false;
    };
  }, [name]);

  return component;
}
