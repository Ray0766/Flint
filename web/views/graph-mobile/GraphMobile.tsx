// GRAPH-13：移动端只读画布（F17，触摸端禁拖禁连、可看可开分析）。
//
// **不挂载**而不是「挂了再拦」：挂上再拦的话，手指按住节点时它仍然会抢走滚动手势——
// 用户想滑动页面，画布却以为他在拖节点，页面就卡住不动。触摸端最该保住的是
// **能滑能看**，而不是把桌面交互硬塞进来再逐个屏蔽。
//
// **只读不等于残废**：看得见、点得开分析，这两件在手机上恰恰是最常做的。
//
// **触摸判定由外部传入**：组件不自己嗅探 UA——UA 嗅探在平板、触屏笔记本上会判错，
// 而判错的代价是「这台机器上拖不动」，用户完全无从理解。判定归调用方
// （它可以用媒体查询、指针类型或用户设置），本组件只按拿到的那个布尔值行事。
//
// **只读态要说明白**：横幅明说此处不可编辑。让拖动与连线**静静地不生效**，
// 用户只会以为界面坏了。

import type { JSX } from "react";
import { useRef } from "react";

import { t } from "../../lib/i18n/t";

export type MobileNode = { nodeId: string; label: string; primary: boolean };

export type GraphMobileProps = {
  nodes: MobileNode[];
  /** 是否触摸端；由调用方判定（媒体查询/指针类型/用户设置），NEVER 在此嗅探 UA */
  touch: boolean;
  onOpenAnalysis: (nodeId: string) => void;
  onPersistPosition?: (nodeId: string, at: { x: number; y: number }) => void;
  onCreateEdge?: () => void;
};

export function GraphMobile({
  nodes,
  touch,
  onOpenAnalysis,
  onPersistPosition,
  onCreateEdge,
}: GraphMobileProps): JSX.Element {
  const dragging = useRef<string | null>(null);

  // 桌面端才组装拖动 handler；触摸端这几个属性根本不会出现在节点上
  const dragHandlers = touch
    ? {}
    : {
        onPointerDown: (nodeId: string) => () => {
          dragging.current = nodeId;
        },
        onPointerUp:
          (nodeId: string) =>
          (event: { clientX: number; clientY: number }) => {
            if (dragging.current !== nodeId) return;
            dragging.current = null;
            onPersistPosition?.(nodeId, { x: event.clientX, y: event.clientY });
          },
      };

  return (
    <section data-testid="graph-mobile" data-touch={String(touch)}>
      {touch ? (
        <p data-testid="graph-mobile-readonly-banner">{t("graph.mobile.readonly")}</p>
      ) : null}
      <ul>
        {nodes.map((node) => (
          <li
            key={node.nodeId}
            data-testid="graph-mobile-node"
            data-node-id={node.nodeId}
            data-draggable={String(!touch)}
            onDoubleClick={() => onOpenAnalysis(node.nodeId)}
            {...(touch
              ? {}
              : {
                  onPointerDown: dragHandlers.onPointerDown?.(node.nodeId),
                  onPointerUp: dragHandlers.onPointerUp?.(node.nodeId),
                })}
          >
            {node.label}
          </li>
        ))}
      </ul>
      {touch ? null : (
        <button
          type="button"
          data-testid="graph-mobile-connect"
          onClick={() => onCreateEdge?.()}
        >
          {t("graph.mobile.connect")}
        </button>
      )}
    </section>
  );
}
