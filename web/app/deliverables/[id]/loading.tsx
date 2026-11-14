// UIX-01：报告屏的加载态。
//
// ## 为什么在这里而不在 `page.tsx` 里
//
// `page.tsx` 是 **async 服务器组件**——它 `await fetchBlocks(...)` 完才返回 JSX，
// 组件内部**没有「正在加载」那一刻可以渲染**。
//
// App Router 的机制是：同目录的 `loading.tsx` 会被自动包成 `<Suspense fallback>`，
// 在服务端取数期间显示。这是这类页面**唯一**诚实的加载态位置。
//
// 硬要在 `page.tsx` 里写一个 `if (loading)`，写出来的是一段**永远进不去的死分支**——
// 而死分支会让下一个人以为那屏在客户端取数。
// （`A6` 规则的注释里写着同一句话：三态是给取数屏的，硬凑的死分支比没有更坏。）

import type { JSX } from "react";

import { LoadingSkeleton } from "../../../components/shell/LoadingSkeleton";

export default function Loading(): JSX.Element {
  // 报告屏是一棵 block 树，行数不定；给 6 条骨架，比一条转圈更接近它的形状。
  return <LoadingSkeleton rows={6} />;
}
