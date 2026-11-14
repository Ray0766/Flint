// S1 通用件②：空态（交付包 S1 契约点名的五件之一）。
//
// ## 这个组件**只用于「查过了，确实没有内容」**
//
// `WIRE-03` 登记过这条，本文件是它的落地处。三种「看起来像空」的情形里，
// **只有一种**该用它：
//
// | 情形 | 用哪个 | 为什么不能混 |
// |---|---|---|
// | 请求还在路上 | `LoadingSkeleton` | 用户会以为**已经查过了** |
// | 接口没挂上 / 这一族没有后端 | `NotProvided` | 要人去挂路由或配后端，不是去创建内容 |
// | **查过了，一条都没有** | **`EmptyState`** | ✔ |
//
// 混用的代价不是「不好看」，是**把一句系统没有依据说出口的话说了出来**。
//
// ## 空态要给出路
//
// 一句「暂无数据」把人钉在原地。空态该说清**这里本来会有什么**，
// 以及**怎么让它有**——所以 `hint` 与 `action` 是这个组件的正文，不是装饰。
//
// 而 `hint` **NEVER 由本组件编**：调用方知道那一屏空着意味着什么，
// 这里编一句通用的，等于替每一屏说了同一句没用的话。

import type { JSX, ReactNode } from "react";

export function EmptyState({
  title,
  hint,
  action,
}: {
  /** 这一屏空着时该说的那句话。**调用方给**——各屏不一样。 */
  title: string;
  /** 这里本来会有什么。不给就不画，NEVER 编一句通用的。 */
  hint?: string;
  /** 让它有内容的那个入口。没有真去处就别给——点了没反应比没有按钮更糟。 */
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="state state--empty" data-screen-state="empty">
      <p className="state__title">{title}</p>
      {hint ? <p className="state__hint">{hint}</p> : null}
      {action ? <div className="state__action">{action}</div> : null}
    </div>
  );
}
