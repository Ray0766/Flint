// DESIGN-06：工具调用时间线（G8，30+ 折叠）。
//
// 一轮设计生成可能调几十次工具。全量铺开的话，用户想看的那段生成文字会被推到
// 几屏之外——工具调用是**过程**，不是他要读的东西。
//
// 但**折叠 NEVER 等于丢弃**：出了问题时「它到底做了什么」是唯一能查的线索，
// 所以展开要能回看全量，且折叠态本身要说得出**折了多少条、其中几条失败**——
// 一句「已折叠」等于什么都没说。
//
// 少量调用不折叠：三条也折起来的话，用户要多点一次才能看见本就该看见的东西。
//
// 折叠态里不渲染参数：把几十条参数塞进 DOM 只为让它们不可见，既占内存又让
// 「不可见」变成一件靠 CSS 维持的事——CSS 一改就漏出来。

import type { JSX } from "react";
import { useState } from "react";

import { t } from "../../lib/i18n/t";

/** 折叠态高度上限（px）。卡上 acceptance 写死 ≤40。 */
export const COLLAPSED_MAX_HEIGHT_PX = 40;

/** 超过这个条数才折叠。 */
export const COLLAPSE_THRESHOLD = 30;

export type ToolCallView = {
  id: string;
  tool: string;
  arguments: Record<string, unknown>;
  ok: boolean;
};

export function ToolTimeline({ calls }: { calls: ToolCallView[] }): JSX.Element | null {
  const [expanded, setExpanded] = useState(false);
  if (calls.length === 0) return null;              // 空列表什么都不该占

  const failed = calls.filter((c) => !c.ok).length;
  const collapsed = calls.length > COLLAPSE_THRESHOLD && !expanded;

  return (
    <section data-testid="tool-timeline">
      <button
        type="button"
        data-testid="tool-timeline-toggle"
        aria-expanded={!collapsed}
        onClick={() => setExpanded((prev) => !prev)}
      >
        {t("design.tools.toggle")}
      </button>
      <p
        data-testid="tool-timeline-summary"
        data-count={calls.length}
        data-failed={failed}
      >
        {t("design.tools.summary", { count: calls.length, failed })}
      </p>
      {collapsed ? (
        <div
          data-testid="tool-timeline-collapsed"
          style={{ maxHeight: `${COLLAPSED_MAX_HEIGHT_PX}px`, overflow: "hidden" }}
        />
      ) : (
        <ul data-testid="tool-timeline-expanded">
          {calls.map((call) => (
            <li
              key={call.id}
              data-testid="tool-timeline-row"
              data-call-id={call.id}
              data-tool={call.tool}
              data-ok={String(call.ok)}
            >
              <span data-testid="tool-timeline-tool">{call.tool}</span>
              <code>{JSON.stringify(call.arguments)}</code>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
