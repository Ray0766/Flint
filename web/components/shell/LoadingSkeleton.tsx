// S1 通用件①：加载态（交付包 S1 契约点名的五件之一）。
//
// ## 「请求在路上」是一种**独立的状态**
//
// 它既不是「查过了、没有内容」，也不是「出错了」，更不是「接口未提供」。
// 四者要人做的事完全不同：等一等 / 去创建内容 / 去查日志 / 去挂路由。
//
// 第 2 批与第 3 批一路在治的就是这件事。加载期渲染成空态，
// 是这个病最常见的形态——**用户会以为已经查过了**。
//
// ## 为什么是骨架而不是转圈
//
// 骨架把**将要出现的东西的形状**先画出来，内容到达时布局不跳。
// 转圈只说「在忙」，说不出在忙什么，而且内容一到页面整个重排。
//
// `rows` 是**调用方按那一屏的真实行数给的**——NEVER 在这里猜一个默认值
// 然后画出一屏与真实内容对不上的灰条。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export function LoadingSkeleton({
  rows = 3,
  label,
}: {
  /** 画几条骨架。按那一屏真实的行数给。 */
  rows?: number;
  /** 读屏软件念的那句话。不给就用通用的「正在查」。 */
  label?: string;
}): JSX.Element {
  return (
    <div
      className="state state--loading"
      data-screen-state="loading"
      // 读屏软件要知道这里在等东西；`aria-busy` 是那句话。
      aria-busy="true"
      aria-live="polite"
    >
      <span className="state__label">{label ?? t("state.loading")}</span>
      {Array.from({ length: rows }, (_, index) => (
        <span key={index} className="state__skeleton-row" aria-hidden="true" />
      ))}
    </div>
  );
}
