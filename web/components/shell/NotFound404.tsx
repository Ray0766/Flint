// S1 通用件④：这条资源不存在（交付包 S1 契约点名的五件之一）。
//
// ## 与「接口未提供」**NEVER 用同一个表示**
//
// 两者在屏上都是「你要的东西不在这儿」，但**说的是完全不同的两件事**：
//
// | | 说的是 | 用户该做什么 | 我们该做什么 |
// |---|---|---|---|
// | `NotFound404` | **这个能力在**，我们查了，**这一条**不存在 | 换一个 id / 回上一层 | 什么都不用做 |
// | `NotProvided` | **这个能力还没接** | 等 | 去挂路由或配后端 |
//
// 混成一句「找不到」，用户会拿一个正确的 id 反复试；
// 反过来混，用户会以为自己的数据被删了。
//
// ## 它对应的是**带 `code` 的 404**
//
// `BE-09` 的「404 不 403」口径：未知与无权收进同一条路，回
// `{"code": "NOT_FOUND", ...}`。而框架的路由未命中回的是
// `{"detail": "Not Found"}`——**没有 `code`**。
// `web/lib/screenClient.ts` 就是按这一点把两者分开的，本组件是前者的落点。
//
// **无权与不存在共用这一个表示是有意的**：分开说等于告诉未授权的人
// 「这个 id 是存在的」，那本身就是一次信息泄露。

import type { JSX, ReactNode } from "react";

import { t } from "../../lib/i18n/t";

export function NotFound404({
  what,
  id,
  action,
}: {
  /** 找的是什么（「这份交付物」「这个项目」）。**调用方给**——各屏不一样。 */
  what: string;
  /** 找的那个 id。带出来是为了让人一眼看出是不是敲错了。 */
  id?: string;
  /** 回得去的地方。**没有真去处就别给**——点了没反应比没有按钮更糟。 */
  action?: ReactNode;
}): JSX.Element {
  return (
    <div className="state state--not-found" data-screen-state="not_found">
      <p className="state__title">{t("state.not_found", { what })}</p>
      {id ? <p className="state__hint" data-not-found-id={id}>{id}</p> : null}
      {action ? <div className="state__action">{action}</div> : null}
    </div>
  );
}
