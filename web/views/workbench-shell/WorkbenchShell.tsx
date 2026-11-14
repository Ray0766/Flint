// GRAPH-01：工作台容器与路由（对 F15 两案**中立**）。
//
// J4 定名：`/workbench` 路由归 **F 组**（热点工作台·图谱）；
// 原 2.2「工作台（证据卡）」更名「证据卡面板」，作为图谱内的抽屉面板。
//
// ## 为什么容器里不能有 mode
//
// F15（页签 vs 模式切换）是**隔离带卡 GRAPH-16** 的议题，owner 可整体划掉。
// 容器若现在就引入 `mode` 概念，等于替 owner 先选了一案——
// 而且划掉 GRAPH-16 时容器要跟着改，隔离带就不成其为隔离带了。
//
// 所以本容器只做三件事：**认路由、给插槽、不决定布局**。
// 「默认 / AI」这类词只能是**预设组合的文案**，NEVER 成为状态树里的键。

import type { JSX, ReactNode } from "react";

/** F 组工作台的规范路由（J4 定名）。 */
export const WORKBENCH_ROUTE = "/workbench";

export type WorkbenchShellProps = {
  /** 主区：图谱画布或任何 F 组视图。容器不关心它是什么。 */
  children: ReactNode;
  /** 侧栏插槽：证据卡面板 / AI 栏。给不给、给什么由上层决定。 */
  aside?: ReactNode;
};

export function WorkbenchShell({ children, aside }: WorkbenchShellProps): JSX.Element {
  return (
    <div className="workbench-shell" data-testid="workbench-shell" data-route={WORKBENCH_ROUTE}>
      <main data-testid="workbench-main">{children}</main>
      {aside ? <aside data-testid="workbench-aside">{aside}</aside> : null}
    </div>
  );
}
