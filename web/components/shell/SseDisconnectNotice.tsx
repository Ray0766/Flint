// S1 通用件⑤：长连接断了（交付包 S1 契约点名的五件之一）。
//
// ## 这一条治的病：**屏上什么都不说，静静停在旧数据上**
//
// `WIRE-06` 实测：`openJobStream` 只赋了 `es.onmessage`，
// **`onerror` 从未被赋值**，`JobStreamState` 也没有一个字段能表示「连接断了」。
// 后端挂掉、网断掉、反代超时——`data-job-status` 停在最后一次收到的值，
// **用户把停住的旧数据读成「还在跑」**。
//
// 单子：`docs/blocked/SSE-DISCONNECT-IS-SILENT.md`（本卡关闭）。
//
// ## 断线 ≠ 作业失败
//
// `failedReason` 是**后端明确发来的** failed 事件；断线是**我们收不到消息了**。
// 挤进同一个表示，「作业跑挂了」与「你的网断了」会显示成同一句话，
// 而两者该做的事完全相反：一个去看失败原因，一个刷新页面。
//
// ## 断线是**可恢复态**，不是终态
//
// 原生 `EventSource` 断线会自动重连。所以这条提示说的是
// 「**正在重连**，下面的内容可能不是最新的」——
// NEVER 说成「连接已断开」那种终局口吻，也 NEVER 把旧内容藏起来：
// 旧内容仍然是真的，只是可能过时了。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export function SseDisconnectNotice({
  since,
}: {
  /** 从哪一刻起断的。给了就显示，NEVER 由本组件去取当前时间。 */
  since?: string;
}): JSX.Element {
  return (
    <div
      className="state state--disconnected"
      data-screen-state="disconnected"
      // 状态变化要被念出来，但不该打断用户正在做的事——所以是 status 不是 alert。
      role="status"
      aria-live="polite"
    >
      <p className="state__title">{t("state.disconnected")}</p>
      <p className="state__hint">{t("state.disconnected_hint")}</p>
      {since ? <p className="state__hint" data-disconnected-since={since} /> : null}
    </div>
  );
}
